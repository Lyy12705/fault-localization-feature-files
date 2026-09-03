# SWE-bench Fault Localization Dataset

This directory is generated from the public `princeton-nlp/SWE-bench` dataset.
It is prepared for file-level fault-localization evaluation.

Source:
- Dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench
- Project: https://github.com/SWE-bench/SWE-bench
- License: MIT

Generated files:
- `<split>_tickets.jsonl`: bug reports for localization input.
- `<split>_gold.jsonl`: file-level ground truth parsed from developer patches.
- `<split>_repos.jsonl`: unique GitHub repositories referenced by the split.
- `<split>_manifest.json`: source, license, and preparation metadata.

Important evaluation note:
SWE-bench gives repository and base commit per instance. To evaluate localization,
checkout each `repo` at its `base_commit`, run localization for that ticket, then evaluate
against `<split>_gold.jsonl` with `scripts/evaluate_fault_localization.py`.
