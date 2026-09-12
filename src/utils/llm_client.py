from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from utils.json_schema import repair_json_object

# Code Llama Fill-In-the-Middle (FIM) sentinel tokens, PSM (prefix-suffix-middle)
# format: " <PRE> {prefix} <SUF>{suffix} <MID>" -> generation resumes from <MID>
# and is expected to stop at <EOT>.
#
# The spacing above is not cosmetic. Code Llama's SentencePiece vocabulary
# stores these as "_<PRE>" / "_<SUF>" / "_<MID>" (leading space marker), which
# is why Meta's and HuggingFace's reference implementations emit them with the
# separating spaces shown. Writing "...{prefix}<SUF>..." with no space can
# fail to match the special token and get tokenized as ordinary text ("<",
# "SU", "F", ">"), which silently turns the whole FIM prompt into plain prose
# the model then free-associates from -- exactly the confused, mis-indented
# output observed in the 2026-09-12 manual runs.
#
# These constants are only used by the MANUAL fallback path. The default path
# is Ollama's native infilling API (the "suffix" request field), which builds
# the FIM prompt server-side from the model's own template -- see
# OllamaClient.generate_fim().
FIM_PREFIX_TOKEN = "<PRE>"
FIM_SUFFIX_TOKEN = "<SUF>"
FIM_MIDDLE_TOKEN = "<MID>"
FIM_EOT_TOKEN = "<EOT>"

# Default model for the FIM/infilling path. This is deliberately NOT the
# "-instruct" tag the Stage-2/3 JSON rerank uses:
#
#   * Code Llama's infilling ability is trained into the base/code 7B and 13B
#     checkpoints (34B has no infilling at all). "-instruct" is an additional
#     chat fine-tune layered on top, and Ollama ships it with a chat template
#     ("[INST] ... [/INST]"), so its whole serving path is built around
#     conversational turns rather than raw continuation.
#   * Empirically (2026-09-12 manual runs against a real server), asking
#     "codellama:7b-instruct" to infill produced conversational prose, echoed
#     sentinels, self-invented end markers ("<EOF>", "<INF>"), and completions
#     that dropped the target definition entirely.
#
# The "-code" tag is the same Code Llama 7B family at the same size -- the
# code-completion variant rather than the chat-tuned one -- so model-family
# consistency with Stage-2/3 is preserved while using the checkpoint that
# actually supports this task.
DEFAULT_FIM_MODEL = "codellama:7b-code"

# Observed against a real Ollama "codellama:7b-instruct" server across
# separate manual_check_generate_fim.py runs on 2026-09-12: instead of
# reliably stopping at <EOT>, this checkpoint has used at least two different
# non-standard "end" markers on different runs -- "<EOF>" once, "<INF>" on a
# later run -- before continuing to generate past the intended completion.
# Neither is part of Code Llama's documented FIM format; they are listed here
# purely as defensive stop markers for observed failure modes, on top of the
# four canonical sentinels. This checkpoint clearly has no single reliable
# stop signal, so treat this list as a lower bound, not a closed set: expect
# to see new variants and add them here as they turn up. Because an unknown
# future variant WILL slip past this list, structural (indentation-based)
# trimming in utils.patch_generation.trim_generated_code_to_symbol_scope() is
# the actual backstop patch generation relies on -- this list only trims the
# request/response a little earlier for markers already known.
FIM_OBSERVED_LOOP_MARKERS = ("<EOF>", "<INF>")

# Every sequence generation should stop at: the four canonical FIM sentinels
# (seeing another <PRE>/<SUF>/<MID> means the model started hallucinating a
# new cycle instead of stopping) plus the observed loop markers above.
FIM_STOP_SEQUENCES = (
    FIM_EOT_TOKEN,
    FIM_PREFIX_TOKEN,
    FIM_SUFFIX_TOKEN,
    FIM_MIDDLE_TOKEN,
    *FIM_OBSERVED_LOOP_MARKERS,
)


def _truncate_at_first_stop_sequence(text: str, stop_sequences: tuple[str, ...]) -> str:
    """Cut ``text`` at the earliest occurrence of any string in ``stop_sequences``.

    This is a client-side safety net: ``generate_fim()`` also asks Ollama to
    stop generation server-side at these sequences (see ``_generate``'s
    ``stop_sequences`` option), but that depends on the Ollama version/server
    honoring ``options.stop``. If it doesn't (or a sequence spans a token
    boundary the server-side matcher misses), this ensures the returned text
    still never carries a hallucinated second FIM cycle into the caller.
    """

    earliest = len(text)
    for marker in stop_sequences:
        index = text.find(marker)
        if index != -1 and index < earliest:
            earliest = index
    return text[:earliest]


@dataclass(slots=True)
class OllamaClient:
    """Minimal client for the optional local Ollama reranking stage."""

    url: str = "http://localhost:11434/api/generate"
    model: str = "codellama:7b-instruct"
    fim_model: str = DEFAULT_FIM_MODEL
    timeout: int = 180

    def generate(self, prompt: str) -> str:
        return self._generate(prompt, response_format="json")

    def generate_fim(
        self,
        prefix: str,
        suffix: str,
        *,
        temperature: float = 0.2,
        top_p: float = 0.95,
        num_predict: int = 256,
        use_native_suffix: bool = True,
    ) -> str:
        """Infill the code between ``prefix`` and ``suffix`` (Stage-4 patch generation).

        Two request shapes are supported:

        ``use_native_suffix=True`` (default) uses Ollama's own infilling API:
        the prefix goes in ``prompt``, the suffix in the ``suffix`` request
        field, and the server assembles the FIM prompt from the model's own
        template with the real special-token ids. This is the correct way to
        infill with Ollama and avoids the whole class of bugs that come from
        hand-writing sentinel strings into a prompt and hoping the tokenizer
        maps them back to special tokens (see FIM_PREFIX_TOKEN's comment).

        ``use_native_suffix=False`` hand-builds the PSM prompt
        (" <PRE> {prefix} <SUF>{suffix} <MID>") and sends it with ``raw:
        true`` so no chat template wraps it. Kept as a fallback for servers
        or model tags without native suffix support; the canonical spacing
        matters here and is not optional.

        Either way the request is sent to ``fim_model`` -- NOT ``model``,
        which stays on the "-instruct" tag the Stage-2/3 JSON rerank needs.

        Generation should end at ``<EOT>``. Because that cannot be relied on
        (real runs produced ``<EOF>``, ``<INF>``, or nothing at all), the
        request also carries ``options.stop`` and the response is cut
        client-side at the earliest known sentinel. Neither is a complete
        guarantee -- ``utils.patch_generation`` does structural trimming and
        symbol-definition checking on top. Leading/trailing whitespace is
        otherwise preserved, since FIM output needs to line up with the
        indentation the prefix ends on.
        """

        if not isinstance(prefix, str) or not isinstance(suffix, str):
            raise TypeError("FIM prefix and suffix must both be strings.")

        if use_native_suffix:
            raw = self._generate(
                prefix,
                response_format=None,
                temperature=temperature,
                top_p=top_p,
                num_predict=num_predict,
                strip_response=False,
                stop_sequences=FIM_STOP_SEQUENCES,
                suffix=suffix,
                model=self.fim_model,
            )
        else:
            prompt = f" {FIM_PREFIX_TOKEN} {prefix} {FIM_SUFFIX_TOKEN}{suffix} {FIM_MIDDLE_TOKEN}"
            raw = self._generate(
                prompt,
                response_format=None,
                temperature=temperature,
                top_p=top_p,
                num_predict=num_predict,
                strip_response=False,
                raw_prompt=True,
                stop_sequences=FIM_STOP_SEQUENCES,
                model=self.fim_model,
            )
        return _truncate_at_first_stop_sequence(raw, FIM_STOP_SEQUENCES)

    def _generate(
        self,
        prompt: str,
        *,
        response_format: str | dict[str, Any] | None,
        temperature: float = 0.0,
        top_p: float = 1.0,
        num_predict: int = 768,
        strip_response: bool = True,
        raw_prompt: bool = False,
        stop_sequences: tuple[str, ...] | list[str] | None = None,
        suffix: str | None = None,
        model: str | None = None,
    ) -> str:
        if self.timeout <= 0:
            raise ValueError("Ollama timeout must be positive.")
        payload: dict[str, Any] = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "top_p": top_p, "num_predict": num_predict},
        }
        if response_format is not None:
            payload["format"] = response_format
        if suffix is not None:
            # Ollama's native infilling field: the server builds the model's
            # own FIM prompt from prompt (= prefix) + suffix, using the real
            # special-token ids rather than sentinel strings we spell out and
            # hope the tokenizer recognizes.
            payload["suffix"] = suffix
        if stop_sequences:
            # Ask Ollama to stop generation server-side as soon as any of
            # these sequences is produced, instead of only truncating
            # client-side after the full num_predict budget has been spent.
            payload["options"]["stop"] = list(stop_sequences)
        if raw_prompt:
            # Bypass Ollama's Modelfile chat/instruct template: without this,
            # an "-instruct" tagged model wraps our prompt in its own
            # [INST]...[/INST] template, so the literal <PRE>/<SUF>/<MID>/<EOT>
            # sentinel tokens never reach the underlying model as the raw text
            # they need to be for FIM -- they get treated as ordinary words
            # inside a chat turn, and the model responds conversationally
            # (prose explanations, markdown code fences, or an echo of the
            # sentinels themselves) instead of infilling. "raw: true" sends
            # the prompt to the model exactly as constructed.
            payload["raw"] = True
        data = json.dumps(payload).encode("utf-8")
        timeout = float(self.timeout)
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--fail-with-body",
            "--max-time",
            f"{timeout:g}",
            "--connect-timeout",
            f"{min(timeout, 10.0):g}",
            "--header",
            "Content-Type: application/json",
            "--data-binary",
            "@-",
            self.url,
        ]
        try:
            completed = subprocess.run(
                command,
                input=data,
                capture_output=True,
                check=False,
                timeout=timeout + 5.0,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Ollama reranking requires the curl executable.") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Ollama request exceeded the {timeout:g}s hard deadline.") from exc
        if completed.returncode == 28:
            raise TimeoutError(f"Ollama request exceeded the {timeout:g}s hard deadline.")
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Ollama request failed: {detail or f'curl exit {completed.returncode}'}")
        try:
            body = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Ollama returned an invalid JSON response envelope.") from exc
        text = str(body.get("response", ""))
        return text.strip() if strip_response else text

    def generate_json(self, prompt: str) -> dict[str, Any]:
        return repair_json_object(self.generate(prompt))

    def generate_json_with_schema(
        self,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Request an Ollama response constrained by a JSON Schema."""

        return repair_json_object(self._generate(prompt, response_format=schema))
