# 第三階段步驟 3.2–3.4：補丁生成、測試案例生成與回歸測試 實作與實驗計畫

**文件版本：** v1.0
**日期：** 2026-09-12
**狀態：** 補丁生成階段開發的正式執行基準（尚未動工，本文件為起始規劃）
**適用專案：** Fault Localization Feature
**對應研究計畫書：** 步驟 3.2（補丁生成）、3.3（自動化測試案例生成）、3.4（回歸測試）
**對應既有文件：** `STAGE3_SYMBOL_RERANKER_IMPLEMENTATION_PLAN_ZH.md`（第三階段錯誤定位，本文件的直接上游）

> **下一個行動：** 先完成 WP1「補丁生成資料契約與 FIM Prompt 基礎設施」。在 `PatchRecordV1`、patch 套用驗證與最小可執行 pipeline 通過驗收前，不開始測試案例生成，也不對補丁修復率作結論。

---

## 0. 執行摘要

第三階段錯誤定位（WP1–WP4）已完成一輪：Symbol 資料契約、Gold 標註與 Evaluator 已完成並通過各自驗收門檻；Deterministic Candidate Baseline（coverage-aware-v1）選定為正式輸出，Conditional Exact Candidate Recall@30 為 **68.64%**（未達 90% 的 G2 門檻，已記錄為已知限制）；Code Llama Symbol Reranker Pilot 已完成一輪 46 票正式測試，**不採用**（Hit@1 顯著更差、Hit@3/5 方向為負但不顯著）。團隊已正式決定：不再無限期追加候選改善實驗，帶著已知限制推進到下一步——補丁生成與驗證。

**本文件規劃研究計畫書步驟 3.2–3.4**，即從 Stage-3 輸出的函式／方法／類別層級定位結果出發，(1) 用 Code Llama 的 Fill-in-the-Middle（FIM）能力生成補丁，(2) 參考 LIBRO 系統的機制自動生成能重現原始錯誤的測試案例，(3) 參考 CLEVEREST／RIPR 的機制驗證補丁沒有破壞既有功能。

本文件目前確認的現況（詳見第 15 節）：**repo 內尚無任何補丁生成、測試生成或回歸測試相關程式碼、設定檔或測試檔**；唯一與此銜接的既有介面，是 Stage-1/2 檔案定位既有的 `confidence_level` / `recommend_patch_generation` / `patch_generation_policy` 信心分流欄位（見第 2.2 節），且該欄位目前**只根據檔案層級信心計算，尚未納入 Stage-3 Symbol 層級的結果**，這是本階段開工前必須先處理的介接缺口。

**預估工期：** 單人約 12–14 個工作日（WP1 3 日、WP2 4 日、WP3 4 日、WP4 2–3 日）。專題排程規定步驟 3（含補丁生成與驗證）僅到 115 年 12 月，其後仍有提交訊息生成、系統測試與優化須在 116 年 2 月前完成，故本計畫的驗證規模（見第 9 節）刻意小於正式論文等級的補丁修復研究，先求「pipeline 可重現、結論誠實」，不求「補丁修復率突破 state of the art」。

---

## 1. 目標、範圍與非目標

### 1.1 本階段目標

以 Stage-3 輸出的 Top-5 Symbol 定位結果與 Ticket 描述為輸入，生成候選補丁；自動生成能在修補前重現原始錯誤、在套用補丁後應通過的測試案例；並執行回歸測試確認補丁未破壞既有功能。

本階段完成後必須能回答四個問題：

1. 在 Stage-3 已正確定位到 symbol 的條件下（conditional），Code Llama 生成的補丁有多高比例能語法正確、成功套用到 base commit？
2. 自動生成的測試案例，有多高比例真的能在修補前失敗、在套用候選補丁後轉為通過（即符合 LIBRO 定義的 FIB：Fail-In-Buggy）？
3. 通過的補丁中，有多少是「看似正確」（只通過我們自己生成的測試）而非「真正正確」（也通過專案既有的獨立測試）？這兩者必須分開報告，不能只看前者就下結論。
4. 補丁套用後，既有回歸測試是否維持全數通過？若通過率下降，是補丁本身的問題還是生成測試的品質問題？

### 1.2 本階段包含

- 補丁生成：以 `stage3_ranked_symbols` 為定位輸入，用 Code Llama 的 FIM（PSM 格式）生成候選補丁，並做語法與套用驗證。
- 測試案例生成：仿照 LIBRO 的四階段流程（提示詞工程 → LLM 查詢 → 測試後處理 → 選擇與排序），以 FIB 準則篩選候選測試。
- 回歸測試：仿照 CLEVEREST／RIPR 的機制，用既有測試套件（若專案本身有，如 Defects4J 系列 repo）與新生成的測試共同驗證補丁未引入新錯誤。
- 三層資料契約（`PatchRecordV1`、`GeneratedTestRecordV1`、`RegressionResultV1`）與對應的 conditional／end-to-end 指標。
- Unit、integration、真模型執行順序與凍結報告。

### 1.3 本階段不包含

- 修改 Stage-1／Stage-2／Stage-3 既有邏輯；本階段一律把 `stage3_ranked_symbols` 視為既定輸入，即使已知其 conditional recall 只有 68.64%。
- 提交訊息生成（步驟 4，另立文件）。
- 支援 Python 以外的語言；FIM 與測試生成 v1 僅涵蓋 Python，其餘語言標記 `unsupported`。
- 重新訓練或微調 Code Llama；v1 一律使用既有的 `codellama:7b-instruct`（透過 Ollama），與 Stage-2／Stage-3 保持模型一致，避免同時變動多個因素。
- 在 frozen holdout 上調整 prompt、採樣參數或門檻。

---

## 2. 現況基準與不可改動的前提

### 2.1 已完成並沿用

| 邊界 | 正式設定 | 本階段的處理方式 |
|---|---|---|
| Stage 1 | E8-A，Top-20 unique files | 直接沿用，不重新最佳化 |
| Stage 2 | retrieval baseline Top-5 | 直接沿用 |
| Stage 3 | B1 coverage-aware-v1，Top-5 symbols；Conditional Exact Candidate Recall@30 = 68.64%（< 90% G2 門檻，已知限制） | 作為補丁生成唯一正式定位輸入；所有補丁／測試／回歸指標**必須同時回報 end-to-end 與 conditional（僅在 Stage-3 已正確定位時）兩個版本**，不得混為一談 |
| Stage-3 LLM | Code Llama Symbol Reranker，本輪不採用 | 補丁生成不依賴 Symbol Reranker 的排序結果，一律使用 B1 deterministic Top-5 |
| LLM 模型 | `codellama:7b-instruct`（Ollama，本機執行） | 沿用同一模型；7B／13B 的 Code Llama 與 Code Llama-Instruct 均支援 infilling，34B 不支援，故不得改用 34B 做補丁生成 |
| 安全 fallback | LLM 輸出不完整時保留 deterministic 結果 | 補丁／測試生成失敗時，明確輸出 `generation_failed`，不得靜默略過或以空補丁充數 |

### 2.2 現有雛形與必須修正的介面

repo 內**尚無**補丁生成、測試生成或回歸測試模組（詳見第 15 節的檢查結果）。唯一相關的既有介面是 `src/utils/fault_localization.py::_localization_confidence()` 產出的信心分流欄位：

| 欄位 | 現況 | 本階段必須處理的問題 |
|---|---|---|
| `confidence_level`（high／medium／low） | 只根據 Stage-1/2 **檔案層級**的 `best_score`、`top1_top2_margin`、`stack_trace_score` 計算 | 完全未參考 Stage-3 Symbol 層級結果；即使檔案信心是 high，Symbol 仍可能不在 Top-5（68.64% 的落差就在這裡） |
| `recommend_patch_generation` | `confidence_level == "high"` 時為 `True` | 必須改為同時要求 `stage3_diagnostics.llm_used or baseline` 產生了非空的 `stage3_ranked_symbols`，否則會對「檔案信心高、但函式根本沒找到」的 Ticket 誤發補丁生成建議 |
| `patch_generation_policy` | 三值：`allow_patch_suggestion`／`manual_review_before_patch`／`block_patch_generation` | 沿用三值語意，但決策輸入必須擴充為檔案層級信心 **與** Symbol 層級 candidate/exact 狀態的組合（見 4.4 節新欄位 `symbol_gate_status`） |

**WP1 的第一個任務即是修正這個信心閘門**，否則後續補丁生成會在「Stage-3 其實沒找到正確函式」的 Ticket 上白工，且無法從結果區分是「補丁生成失敗」還是「上游定位本來就沒找到」。

---

## 3. 目標架構與資料流

```text
Stage 3 輸出（B1 baseline，不使用 Symbol LLM Reranker）
  ├─ stage3_ranked_symbols（Top-5，file-qualified）
  ├─ stage3_diagnostics（eligible／coverage／fallback）
  └─ confidence_level ＋ 修正後的 symbol_gate_status
  ↓
【閘門】symbol_gate_status == "ready_for_patch" 才進入補丁生成；否則標記 manual_review 並停止
  ↓
Stage 4A：補丁生成（FIM／PSM）
  ├─ 對 Top-5 中每個候選 symbol，取其 base-commit 原始碼切成 prefix／suffix
  ├─ Code Llama Infilling：<PRE>{prefix}<SUF>{suffix}<MID> → 補丁片段 → <EOT>
  ├─ 語法驗證（ast.parse）＋ 套用驗證（能否 patch 進 base commit 產生合法檔案）
  └─ 產出 PatchRecordV1（可能多個候選，依 symbol 排名與採樣次數）
  ↓
Stage 4B：測試案例生成（仿 LIBRO）
  ├─ 提示詞工程：Ticket 描述＋錯誤堆疊 → few-shot 提示
  ├─ LLM 查詢：多樣本生成候選測試（temperature > 0，重複查詢 n 次）
  ├─ 測試後處理：語法檢查、去重、補齊 import
  └─ 選擇與排序：FIB 篩選（先在 buggy 版本跑過失敗，才收） → 依報告匹配度／群集大小排序
  ↓
Stage 4C：回歸測試（仿 CLEVEREST／RIPR）
  ├─ 在 patched 版本執行 FIB 測試：通過才視為候選補丁「plausible」
  ├─ 執行既有回歸測試套件（若專案本身有）：確認未破壞既有功能
  ├─ RIPR 分析：候選測試是否真的 Reach／Infect／Propagate／Reveal 了此次程式碼變更
  └─ 若測試未揭露差異，回饋提示合成器做有限次迭代優化
  ↓
最終輸出：PatchRecordV1 ＋ GeneratedTestRecordV1 ＋ RegressionResultV1 ＋ plausible／correct 判定
```

### 3.1 為何「plausible」與「correct」必須分開報告

程式自動修復（Automated Program Repair）文獻已多次指出：只用**生成出來的測試**驗證補丁，容易產生「看起來通過測試、但其實沒有真正修好問題」的補丁（over-fitting 到測試本身，而非修好語意錯誤）。本計畫因此明確區分：

- **Plausible**：補丁套用後，FIB 測試（我們自己生成的）由失敗轉為通過，且既有回歸測試維持通過。
- **Correct**：在 plausible 的基礎上，補丁也通過該專案**既有、非我們生成**的測試（若該 repo 本身在資料集中就帶有完整測試套件，例如部分 Defects4J 系列案例）。沒有獨立測試可用的 Ticket，一律只能回報 plausible，不得宣稱 correct。

第 8 節的指標會分別統計這兩者，不得合併報告成單一「補丁修復率」。

---

## 4. 資料契約

### 4.1 Stage-4 輸入契約

每張 Ticket 必須具有：

- Stage-3 完整輸出：`stage3_ranked_symbols`、`stage3_retrieval_symbols`、`stage3_diagnostics`。
- `base_commit` 的可讀 repository snapshot（與 Stage-3 使用同一份 code index／commit，避免版本漂移）。
- developer patch（僅用於事後對照與 held-out correctness 檢查，**不得**出現在任何 LLM prompt 中）。
- 若專案本身帶有獨立測試套件，需記錄其執行入口與可執行狀態，供 correctness 判定使用。

### 4.2 `PatchRecordV1`

```json
{
  "schema_version": "patch-record-v1",
  "patch_id": "sha256:stable-id",
  "ticket_id": "repo__owner-issue-1234",
  "repo": "owner/repo",
  "base_commit": "40-hex-commit",
  "target_symbol_id": "sha256:symbol-id",
  "file_path": "package/module.py",
  "fim_prefix_lines": [10, 25],
  "fim_suffix_lines": [31, 45],
  "generated_code": "def run(self, value):\n    ...",
  "sampling_index": 0,
  "temperature": 0.4,
  "syntax_valid": true,
  "apply_status": "applied_clean",
  "diff_unified": "--- a/package/module.py\n+++ b/package/module.py\n@@ ...",
  "generation_source": "codellama:7b-instruct-fim",
  "model_digest": "sha256:model-digest",
  "prompt_version": "patchgen-fim-v1",
  "generated_at": "2026-09-12T00:00:00Z"
}
```

`patch_id` 以 `ticket_id`、`target_symbol_id`、`sampling_index` 與 `generated_code` 內容雜湊建立，確保同一 Ticket 的多個候選補丁可被穩定區分與去重。`apply_status` 取值：`applied_clean`／`applied_with_offset`／`syntax_error`／`apply_failed`。

### 4.3 `GeneratedTestRecordV1`

```json
{
  "schema_version": "generated-test-record-v1",
  "test_id": "sha256:stable-id",
  "ticket_id": "repo__owner-issue-1234",
  "test_code": "def test_reproduces_issue_1234():\n    ...",
  "fib_status": "fail_in_buggy_confirmed",
  "buggy_run_result": "failed",
  "patched_run_result_by_patch_id": {
    "sha256:patch-id-1": "passed",
    "sha256:patch-id-2": "failed"
  },
  "report_similarity_score": 0.71,
  "cluster_size": 3,
  "rank": 1,
  "generation_source": "codellama:7b-instruct",
  "prompt_version": "testgen-libro-v1"
}
```

`fib_status` 取值：`fail_in_buggy_confirmed`（在 base commit 上執行為失敗，符合 FIB 定義）、`fail_in_buggy_rejected`（在 base commit 上執行為通過或無法執行，依 LIBRO 準則捨棄）、`execution_error`（測試本身無法執行，如語法錯誤或缺 import）。只有 `fail_in_buggy_confirmed` 的測試才進入 Stage 4C 用於判定補丁。

### 4.4 `RegressionResultV1`

```json
{
  "schema_version": "regression-result-v1",
  "ticket_id": "repo__owner-issue-1234",
  "patch_id": "sha256:patch-id-1",
  "fib_test_outcome": "passed",
  "existing_test_suite_available": true,
  "existing_test_suite_pass_rate_before": 1.0,
  "existing_test_suite_pass_rate_after": 1.0,
  "regression_status": "no_regression",
  "ripr_diagnosis": {
    "reaching": true,
    "infecting": true,
    "propagating": true,
    "revealing": true
  },
  "plausible": true,
  "correct": null,
  "correct_reason": "no_independent_test_suite_available"
}
```

`correct` 為三值邏輯（`true`／`false`／`null`）：只有在 `existing_test_suite_available=true` 且該補丁通過獨立測試時為 `true`；有獨立測試但未通過為 `false`；沒有獨立測試可用時為 `null`，並在 `correct_reason` 註明，不得預設為 `true` 或略過此欄位。

### 4.5 補丁生成信心閘門欄位（併入 Stage-3 confidence 輸出）

在既有 `confidence` 結構中新增：

```json
{
  "symbol_gate_status": "ready_for_patch",
  "symbol_gate_reason": "stage3_ranked_symbols non-empty and Top-5[0] confidence above threshold"
}
```

`symbol_gate_status` 取值：`ready_for_patch`／`manual_review_symbol_uncertain`／`block_no_symbol_candidate`。`patch_generation_policy` 的最終值改由 `confidence_level`（檔案層級）與 `symbol_gate_status`（Symbol 層級）**兩者的交集**決定：任一方為 block，最終即為 `block_patch_generation`。

---

## 5. 補丁生成設計（Stage 4A）

### 5.1 FIM Prompt 設計

依 Code Llama 論文的 PSM（prefix-suffix-middle）格式，對 `stage3_ranked_symbols` 中每個候選 symbol：

1. 讀取 base-commit 原始檔案，以該 symbol 的 `start_line`／`end_line` 為界，切出 prefix（symbol 之前的完整檔案內容，必要時截斷到 token 預算內）與 suffix（symbol 之後的內容）。
2. 組成 prompt：`<PRE>{prefix}<SUF>{suffix}<MID>`，並在 prefix 尾端附上一段以註解形式呈現的 Ticket 錯誤描述摘要，引導模型生成的內容對應到該錯誤。
3. 模型從 `<MID>` 開始生成，直到輸出 `<EOT>` 或達到 `max_tokens` 上限。
4. **不使用** JSON Schema 強制格式（現有 `OllamaClient.generate_json_with_schema` 僅適用於結構化輸出，補丁本體是純程式碼），需新增 `OllamaClient.generate_fim(prefix, suffix) -> str` 方法，走原始文字生成路徑。

### 5.2 模型與參數

- ~~模型固定 `codellama:7b-instruct`，與 Stage-2／Stage-3 一致；7B／13B 的 Code Llama 與 Code Llama-Instruct 均支援 infilling（34B 不支援，故排除）。~~ **（2026-09-12 依實測修正，見第 16 節）** FIM 路徑改用 `codellama:7b-code`，Stage-2／Stage-3 的 JSON 重排序路徑維持 `codellama:7b-instruct` 不變。原本「Instruct 變體也支援 infilling」的假設在實測中站不住腳：infilling 能力是訓練在 base／code 的 7B／13B checkpoint 上（34B 完全不支援），`-instruct` 是額外疊加的對話微調，且 Ollama 對該 tag 套用的是聊天樣板，整條服務路徑都是為對話輪次設計的。連續四次實測顯示它做 infilling 會產生對話式散文、自創結束標記、甚至整個漏掉目標定義。改用 `-code` tag 後仍是同一個 Code Llama 7B 家族、同樣參數量，只是換成程式碼補全變體而非聊天微調變體，模型家族一致性仍然維持。
- 每個候選 symbol 採樣 `n` 次（development 階段建議 n=3～5），以不同 temperature（0.2／0.4／0.6）增加候選多樣性；正式 validation／holdout 需凍結固定的 n 與 temperature 清單，不得臨時調整。
- Prefix／suffix 各自的 token 預算需在 development split 上凍結（例如各 2,048 tokens），避免同一 symbol 因檔案大小不同而得到不一致的上下文。

### 5.3 語法與套用驗證

- 語法驗證：`ast.parse()` 通過才視為 `syntax_valid=true`；失敗則整筆標記 `syntax_error`，不進入後續測試階段。
- 套用驗證：把生成內容替換回 base-commit 對應行號區間，確認能重新組成合法檔案（`apply_status`）；若 symbol 邊界與生成內容行數不一致（例如模型多生成或少生成了縮排層級），標記 `applied_with_offset` 並記錄差異，不得靜默接受可能破壞縮排的結果。

---

## 6. 測試案例生成設計（Stage 4B，仿 LIBRO）

依研究計畫書 3.1.3／3.3 節與 LIBRO 論文的四階段流程：

1. **提示詞工程**：將 Ticket 錯誤報告轉為 Markdown，加入指令（如「提供一個 self-contained 的範例」）與少樣本 bug-test 範例，引導模型生成可獨立執行的測試函式。
2. **LLM 查詢**：以較高 temperature（如 0.7）重複查詢 `n` 次（development 建議 n=10～20，實際次數依時間預算調整，需在計畫凍結後不再更動），產生多個候選測試。
3. **測試後處理**：計算候選測試彼此的文字／AST 相似度做去重；掃描並補齊缺漏的 import；剔除語法錯誤或明顯無法執行的候選。
4. **選擇與排序**：
   - 先執行 **FIB 篩選**：候選測試必須在 base commit（buggy 版本）上執行失敗，才保留（`fib_status=fail_in_buggy_confirmed`）；在 buggy 版本就通過或無法執行的候選一律捨棄，不計入後續統計。
   - 通過 FIB 篩選的候選，依「與原始錯誤報告的匹配度」「同群集候選數量」「程式碼長度」排序，取前幾名推薦給後續回歸測試階段使用；若 FIB 篩選後為空集合，該 Ticket 標記 `no_fib_test_available`，補丁一律只能標記 `plausible=false`（無法驗證）。

### 6.1 為何 FIB 是硬性條件而非可選項

若測試在 buggy 版本上就已經通過，代表它根本沒有驗證到原始錯誤，套用補丁後「通過」毫無意義。因此 FIB 檢查不是加分項，而是進入 Stage 4C 判定補丁是否修復成功的**必要條件**——這點必須在 Definition of Done 與最終報告中明確陳述，避免對外報告時把「生成了測試」誤講成「驗證了補丁」。

---

## 7. 回歸測試設計（Stage 4C，仿 CLEVEREST／RIPR）

依研究計畫書 3.2.2 節與 CLEVEREST／RIPR 論文的機制：

1. **執行 FIB 測試於 patched 版本**：通過即代表候選補丁至少修復了報告中的問題（`plausible` 判定的必要條件之一）。
2. **執行既有回歸測試套件**（若該 repo 在資料集中本身帶有可執行的測試套件）：比較補丁套用前後的通過率，`regression_status` 取值 `no_regression`／`new_failures_introduced`／`suite_unavailable`。
3. **RIPR 診斷**：針對「修補前後版本」的差異，檢查生成的 FIB 測試是否真的：
   - Reaching：測試執行路徑有經過被修改的程式碼；
   - Infecting：該處程式狀態因修改而改變；
   - Propagating：狀態改變有傳播到程式輸出或可觀察行為；
   - Revealing：測試斷言確實能偵測到這個差異（而非斷言內容剛好與差異無關）。
   四項全部為 `true` 才代表這份測試「真的測到重點」，四項只要有一項為 `false`，即使測試「通過／失敗」的表面結果符合預期，也必須在報告中註記為弱驗證（weak verification），不能當作強證據使用。
4. **有限次迭代**：若某候選補丁的所有 FIB 測試都未能通過 RIPR 四項診斷，可將診斷結果回饋給 Stage 4B 的提示合成器，重新生成測試，但**迭代次數需在 development 階段凍結上限**（建議 ≤3 次／Ticket），避免無限迭代耗盡時間預算。

---

## 8. 評估定義

### 8.1 主要指標

| 指標 | 定義 | 分母／用途 |
|---|---|---|
| Symbol Gate Ready Rate | `symbol_gate_status == ready_for_patch` 的 Ticket 比例 | 反映 Stage-3 68.64% 限制實際傳導到補丁階段的比例，End-to-end 分母 |
| Patch Syntax Valid Rate | `syntax_valid=true` 的補丁比例 | 僅計算 gate ready 的 Ticket（conditional） |
| Patch Apply Rate | `apply_status` 為 applied_clean 或 applied_with_offset 的比例 | conditional，同上 |
| FIB Test Availability Rate | 至少 1 筆 `fail_in_buggy_confirmed` 測試的 Ticket 比例 | conditional |
| RIPR Full-Pass Rate | 四項 RIPR 診斷全通過的測試比例 | 僅計算已有 FIB 測試的 Ticket |
| Plausible Patch Rate | 至少 1 個候選補丁同時滿足 FIB 通過＋無回歸 | conditional（gate ready 且有 FIB 測試） |
| Correct Patch Rate | plausible 補丁中，`correct=true` 的比例 | 僅計算 `existing_test_suite_available=true` 的子集，需同時回報這個子集佔全體的比例 |
| End-to-End Success Rate | 從 Ticket 到「至少一個 correct 補丁」的整體成功率 | 全體 eligible Tickets，Stage-3 miss、gate block、FIB 缺失都計為失敗 |

所有比例需回報樣本數（分子／分母），並附上 95% CI（bootstrap，固定種子）；conditional 與 end-to-end 版本必須並列，不得只回報較好看的一種。

### 8.2 與既有階段的一致性要求

比照 Stage-3 的方法論慣例：**任何看似負面的結果，都必須同時回報「是不是上游造成的」**。例如 Plausible Patch Rate 偏低時，需先拆解是「Stage-3 定位錯誤（gate block）」「補丁生成本身失敗（syntax/apply）」還是「FIB 測試生不出來」，避免補丁生成模組被誤判為效果不佳，而實際問題出在上游 68.64% 的候選限制。

---

## 9. 五個 Work Packages

### WP1：資料契約、信心閘門修正與 FIM 基礎設施（3 工作日）

**實作：** 定義 `PatchRecordV1`；修正 `_localization_confidence()` 納入 `symbol_gate_status`；新增 `OllamaClient.generate_fim()`；建立 prefix/suffix 切割與語法/套用驗證工具。

**驗收：** 修正後的 `patch_generation_policy` 在「Stage-3 無候選」的既有 46 票 pilot 資料上重新計算，其 block 判定必須涵蓋所有 Stage-3 miss 的 Ticket；FIM 呼叫在至少 3 個手動範例上能產生語法合法的輸出；相關 Unit Tests 全通過。

**目前狀態（2026-09-12）：✅ 已完成，三項驗收條件全數通過**（46 票閘門重跑 0 誤擋、手動範例 3/3 且語意亦正確、276 個單元測試全通過）。實際實作範圍比原訂多出：FIM 模型／API 路徑更正（`codellama:7b-code` ＋ Ollama 原生 suffix API）、結構性輸出裁切、符號定義語意檢查、補丁品質清理，以及兩支驗證腳本。詳見第 16 節。

### WP2：補丁生成 Pipeline（4 工作日）

**實作：** 對 conditional-eligible 的 development Tickets（沿用既有 46 票集合，與 WP4 Symbol Pilot 一致，避免引入新的抽樣差異）執行多樣本 FIM 補丁生成；輸出 `PatchRecordV1`；統計 Syntax Valid Rate 與 Apply Rate。

**驗收：** conditional Patch Apply Rate 有明確數字與失敗原因分佈（syntax_error／apply_failed 各佔多少）；至少完成 1-ticket smoke → 10-ticket smoke → 46-ticket pilot 三階段（比照 Stage-3 WP4 的執行順序）。

**目前狀態（2026-09-12）：程式碼已完成並通過全部單元測試（312 個全數通過，含端對端 CLI 煙霧測試）；三階段真實驗收（1-ticket → 10-ticket → 46-ticket pilot，需要真實 Ollama 與 repo cache）尚未在使用者本機執行。** 詳見第 17 節。

### WP3：測試案例生成與 FIB 篩選（4 工作日）

**實作：** 建立提示詞工程、多樣本查詢、去重後處理與 FIB 篩選／排序；輸出 `GeneratedTestRecordV1`。

**驗收：** 明確回報 FIB Test Availability Rate；對至少 10 張 Ticket 的生成測試做人工抽查，確認 `fail_in_buggy_confirmed` 判定的執行邏輯正確（測試真的在 base commit 上跑過並失敗，不是憑 LLM 自稱）。

**目前狀態：尚未開始。**

### WP4：回歸測試、RIPR 診斷與 Plausible／Correct 判定（2–3 工作日）

**實作：** 串接 Stage 4A／4B 輸出，執行 FIB 測試與既有回歸測試套件；實作 RIPR 四項診斷；產出 `RegressionResultV1` 與最終 plausible／correct 判定。

**驗收：** Plausible Patch Rate 與 Correct Patch Rate 分開回報，且後者明確標註可用子集大小；RIPR 四項診斷對至少 10 筆結果做人工抽查核對。

**目前狀態：尚未開始。**

### WP5：正式比較、凍結與文件（1–2 工作日）

**實作：** 彙整 conditional／end-to-end 指標、失敗案例分類、與 Stage-3 已知限制的因果關係說明；更新 README、`FAULT_LOCALIZATION_MODEL_SPEC.md` 與最終報告。

**驗收：** 所有 schema、指令與結果可重現；報告明確陳述「本輪結果建立在 Stage-3 68.64% 候選限制之上」，不誇大補丁階段的獨立表現。

**目前狀態：尚未開始。**

---

## 10. 採用與停止門檻

| Gate | 條件 | 未通過時 |
|---|---|---|
| G1 Gate Consistency | 修正後 `symbol_gate_status` 在既有 46 票資料上與 Stage-3 conditional 分類完全一致 | 修正閘門邏輯，不進入 WP2 |
| G2 Patch Validity | conditional Patch Apply Rate ≥ 80% | 檢視 prompt／token 預算設計，不急著跑 FIB 測試 |
| G3 Test Reliability | FIB Test Availability Rate ≥ 60%（development，46 票規模下的探索性門檻，非正式論文等級） | 記錄為已知限制，仍可用已產生的子集繼續 WP4，但報告需註明覆蓋率有限 |
| G4 Verification Rigor | 100% 的補丁判定都標註 plausible／correct 兩層結果，且 correct 判定必須附 `existing_test_suite_available` 依據 | 任何缺少此標註的結果視為未完成，不得寫入最終報告 |
| G5 Regression Safety | 沒有一筆 `regression_status = new_failures_introduced` 的補丁被標記為最終建議 | 該補丁降級為 rejected，不列入 Plausible／Correct 統計的分子 |

本階段**不設定**類似 Stage-3 G2（≥90%）等高門檻的「達不到就不能往下走」硬性關卡，因為：(1) 排程只到 115 年 12 月；(2) 上游 Stage-3 本身已帶著已知限制推進。門檻改為「所有數字必須誠實分層回報」，而非「必須衝到某個高分」。

---

## 11. Testing 計畫

### 11.1 Unit Tests

- FIM prompt 組裝：prefix/suffix 切割邊界、token 預算截斷、sentinel token 正確性。
- 補丁驗證：語法錯誤、縮排錯位、套用到不存在行號、多重 hunk 衝突。
- FIB 判定：buggy 版本執行逾時、執行例外、缺少 import 自動補齊後仍失敗等邊界情況。
- RIPR 診斷：四項條件的獨立測試案例（例如 reaching=true 但 infecting=false 的合成案例）。
- Plausible／Correct 判定：`existing_test_suite_available=false` 時 `correct` 必須為 `null`，不得預設。

### 11.2 Integration Tests

- Stage-3 輸出 → symbol gate → 補丁生成 → 測試生成 → 回歸測試的無斷點 pipeline（使用固定 mock repo）。
- 同一 Ticket 多個候選補丁與多個候選測試的交叉配對（patch × test 矩陣）不遺漏、不重複計算。
- Stage-3 `block_no_symbol_candidate` 的 Ticket 能正確在補丁生成前提前終止，不產生任何 `PatchRecordV1`。

### 11.3 真模型執行順序

1. 1 個 Ticket 驗證 FIM prompt、測試生成 prompt 與 fallback 全流程。
2. 固定 10 個 Ticket 作 smoke test，只判斷流程與各階段 coverage。
3. 固定 46 個 Ticket（沿用 Stage-3 WP4 conditional-eligible 集合）作 development pilot；可調整採樣次數、temperature 與 FIB 篩選參數，不作最終主張。
4. 若時間允許，擴大到更多 conditional-eligible development Tickets 做正式 validation；凍結所有參數。
5. 最後一次執行 frozen holdout；不得回頭調參。**若排程緊迫，第 4、5 步可與 WP5 一併簡化為「以 development pilot 結果作為本階段最終報告」，並在文件中明確註記樣本規模與 exploratory 性質**，比照 Stage-3 WP4 Pilot 的處理方式。

---

## 12. 預計檔案變更

### 新增

- `src/utils/patch_generation.py`：FIM prompt 組裝、`PatchRecordV1`、語法／套用驗證。
- `src/utils/test_generation.py`：LIBRO 風格提示詞工程、後處理、FIB 篩選與排序、`GeneratedTestRecordV1`。
- `src/utils/regression_verification.py`：既有測試套件執行、RIPR 四項診斷、`RegressionResultV1`。
- `scripts/generate_stage4_patches.py`：對 development/validation Tickets 批次執行補丁生成。
- `scripts/generate_stage4_tests.py`：批次執行測試案例生成與 FIB 篩選。
- `scripts/run_stage4_regression_pilot.py`：串接補丁＋測試＋回歸驗證，輸出 pilot 結果與統計。
- `configs/fault_localization/stage4_patch_generation_v1.json`：凍結 FIM 參數（token 預算、採樣次數、temperature 清單）。
- `configs/fault_localization/stage4_test_generation_v1.json`：凍結 LIBRO 參數（查詢次數、去重門檻、排序權重）。
- `tests/test_patch_generation.py`、`tests/test_test_generation.py`、`tests/test_regression_verification.py`。

### 修改

- `src/utils/fault_localization.py::_localization_confidence()`：新增 `symbol_gate_status`，並讓 `patch_generation_policy` 同時參考檔案與 Symbol 兩層信心。
- `src/utils/llm_client.py::OllamaClient`：新增 `generate_fim()`，走非 JSON-schema 的原始文字生成路徑。
- `README.md`、`FAULT_LOCALIZATION_MODEL_SPEC.md`：更新補丁生成／測試生成／回歸測試的正式介面、指標與限制，並明確標註「建立在 Stage-3 68.64% 候選限制之上」。
- `reports/fault_localization/`：新增 `stage4_patch_generation_dev_v1/`、`stage4_test_generation_dev_v1/`、`stage4_regression_pilot/` 存放各階段結果。

---

## 13. 預定命令介面

下列命令是本階段完成後應可執行的正式介面；WP1–WP4 完成前不視為現有功能。

```bash
python scripts/generate_stage4_patches.py \
  --predictions reports/fault_localization/stage3_deterministic_g2_dev_v1/predictions.jsonl \
  --repo-cache-dir data/repositories \
  --config configs/fault_localization/stage4_patch_generation_v1.json \
  --model codellama:7b-instruct \
  --output reports/fault_localization/stage4_patch_generation_dev_v1/patches.jsonl
```

```bash
python scripts/generate_stage4_tests.py \
  --tickets data/fault_localization/stage3_validation_tickets.jsonl \
  --config configs/fault_localization/stage4_test_generation_v1.json \
  --model codellama:7b-instruct \
  --output reports/fault_localization/stage4_test_generation_dev_v1/tests.jsonl
```

```bash
python scripts/run_stage4_regression_pilot.py \
  --patches reports/fault_localization/stage4_patch_generation_dev_v1/patches.jsonl \
  --tests reports/fault_localization/stage4_test_generation_dev_v1/tests.jsonl \
  --output-dir reports/fault_localization/stage4_regression_pilot
```

---

## 14. 風險與處理

| 風險 | 早期訊號 | 處理方式 |
|---|---|---|
| Stage-3 定位錯誤傳導到補丁階段 | conditional 與 end-to-end 指標差距過大 | 一律並列回報兩者；補丁階段的結論只對 conditional 子集下結論 |
| 補丁「看似正確」實則 over-fit 測試 | Plausible Patch Rate 遠高於 Correct Patch Rate | 明確區分兩者，只對有獨立測試套件的子集宣稱 correct |
| FIB 測試生成失敗率高 | FIB Test Availability Rate 過低 | 記錄為已知限制（比照 WP3／WP4 的處理慣例），不強行放寬 FIB 定義湊數字 |
| 縮排／格式錯位導致補丁看似失敗 | `applied_with_offset` 比例偏高 | 優先檢查 prefix/suffix 切割是否切在安全邊界（如函式開頭的縮排層級），必要時改用整個 symbol body 而非任意行號切割 |
| 迭代回饋機制耗時失控 | 單一 Ticket 執行時間遠超預期 | 固定迭代次數上限（≤3 次），並記錄逾時案例供事後分析 |
| 排程壓力導致驗證規模不足 | 只跑得完 development pilot，來不及做正式 validation | 依第 11.3 節註記為 exploratory 結果，誠實寫入報告，不得包裝成正式結論 |

---

## 15. 目前進度與現況檢查結果（2026-09-12）

**檢查方法：** 逐一查看 `src/modules/`、`src/utils/`、`scripts/`、`tests/`、`configs/fault_localization/`、`reports/fault_localization/` 目錄與檔名，並對全 repo 搜尋「補丁／patch／repair／LIBRO／CLEVEREST／RIPR／FIM」等關鍵字。

**結論：補丁生成、測試案例生成、回歸測試三個子階段都尚未開始，repo 內沒有任何相關程式碼、設定檔或測試檔。**

- `src/modules/` 只有 `bug_localizer.py`（Stage 1/2 定位的薄封裝）。
- `src/utils/` 只有 `fault_localization.py`、`symbol_localization.py`、`symbol_gold.py`、`symbol_evaluation.py`、`llm_client.py`、`json_schema.py`，全部屬於 Stage 1–3。
- `scripts/`、`tests/` 內約 40 餘個檔案，命名與內容全部對應 Stage 1（swebench/stage1）、Stage 2（stage2）、Stage 3（stage3/symbol），沒有任何 stage4／patch／test-generation／regression 相關檔案。
- 全 repo 關鍵字搜尋中，「patch」「repair」只出現在：(a) Stage-3 gold 建置文件描述「developer patch」作為 ground-truth 來源、(b) `pyproject.toml` 的專案描述字串「Integrated bug tracking and repair pipeline」（僅為專案願景描述，非程式碼）、(c) `README.md` 中 `recommend_patch_generation`／`patch_generation_policy` 兩個既有信心分流欄位（見第 2.2 節）。沒有找到 LIBRO、CLEVEREST、RIPR 或 FIM 的任何實作或測試。

**下一個任務：** 依第 9 節 WP1，先修正 `_localization_confidence()` 的信心閘門邏輯，並建立 `PatchRecordV1` 與 `OllamaClient.generate_fim()`，在此之前不開始測試案例生成或回歸測試的實作。

---

## 16. WP1 完成紀錄（2026-09-12）

**狀態：WP1（資料契約、信心閘門修正與 FIM 基礎設施）已完成，兩項驗收條件皆由使用者在本機以真實環境驗證通過。**

| WP1 驗收條件 | 結果 |
|---|---|
| 修正後的 `patch_generation_policy` 在既有 46 票 pilot 資料上重新計算，block 判定需涵蓋所有 Stage-3 miss | **通過**：46 票全數 `ready_for_patch`，0 誤擋（使用者本機 `git lfs pull` 後實際執行） |
| FIM 呼叫在至少 3 個手動範例上能產生語法合法的輸出 | **通過**：3/3，且三個補丁的**語意**也都正確（超出本標準要求） |
| 全 repo 單元測試 | **通過**：276 個（WP1 開始前為 204 個） |

達成過程中，真實 Ollama 驗證連續六輪發現並修正問題：① `raw:true` 缺漏；② 停止序列只認 `<EOT>`；③ 改用縮排結構做結構性裁切；④ 發現「語法合法」不代表「目標符號真的被重新定義」，新增語意層級檢查；⑤ **根因**——模型 tag 與 API 都選錯了，改用 `codellama:7b-code` ＋ Ollama 原生 infilling API；⑥ 補丁品質清理（去除定義前的幻覺註解與尾端空白行）。

**第 ⑤ 項是真正的根因修正**：①〜④ 都是在「接住壞輸出」，第 ⑤ 項才處理「輸出為什麼會壞」。①〜④ 的防禦措施仍全部保留，因為 LLM 輸出不可靠是本質問題，不會因為換對模型就消失——第 ⑥ 項正是在模型換對、三個範例全數通過之後，逐字檢視輸出才發現的殘留雜訊，可見這些防線確實有存在價值。

**此過程本身是一項對 WP2 有價值的發現**：Stage-4 的補丁品質不只取決於模型能力，也高度取決於推論路徑是否正確設定（模型變體、API 形式、停止條件、輸出後處理）。WP2 在正式跑 46 票 pilot 之前，應先確認這些設定與本節記錄一致，避免把設定錯誤誤判為模型能力上限。

**實作內容：**

1. **信心閘門修正**（`src/utils/fault_localization.py::_localization_confidence()`）：新增 `_symbol_gate_status()` 輔助函式，依 Stage-3 證據回傳四種狀態之一：
   - `not_applicable`：本次執行未請求 Stage-3 symbol 定位（向後相容，既有純檔案層級的呼叫方不受影響）。
   - `ready_for_patch`：`stage3_ranked_symbols` 非空。
   - `manual_review_symbol_uncertain`：Stage-3 symbol pool 存在（Stage-2 檔案內有 AST 符號），但排序未產生可用候選（例如 LLM rerank 失敗且無 fallback）。
   - `block_no_symbol_candidate`：Stage-2 已定位的檔案內完全找不到任何符號層級候選。

   `patch_generation_policy` 改為檔案層級（`confidence_level`）與 symbol 層級（`symbol_gate_status`）**兩者交集**：任一方判定為 block，最終即為 `block_patch_generation`；任一方為 manual review 且另一方未 block，則為 `manual_review_before_patch`；兩者都通過才是 `allow_patch_suggestion`。回傳結構新增 `symbol_gate_status` 與 `symbol_gate_reason` 兩個欄位（對應計畫書 §4.5），並已在頂層 `localize_ticket()` 回傳字典與 `README.md` 的欄位說明中同步揭露。
   - 呼叫端已同步更新：`localize_ticket()` 在呼叫 `_localization_confidence()` 時傳入 `symbol_localization_requested=self.symbol_localization`、`symbol_candidate_pool_present=bool(stage3_candidate_pool)`、`ranked_symbols=ranked_symbols`（三者在呼叫點之前已經算出，未新增額外運算成本）。

2. **FIM 基礎設施**（`src/utils/llm_client.py::OllamaClient`）：新增 `generate_fim(prefix, suffix, *, temperature=0.2, top_p=0.95, num_predict=256) -> str`，組成 Code Llama PSM 格式提示詞 `<PRE> {prefix}<SUF>{suffix}<MID>`，走原始文字生成路徑（`_generate()` 的 `response_format` 改為 `Optional`，未指定時整個 payload 不帶 `format` 欄位，不再強制 JSON），並在遇到 `<EOT>` 時截斷輸出。為避免破壞 FIM 輸出的縮排，新增 `strip_response` 參數，`generate_fim()` 呼叫時關閉自動 `.strip()`（既有 `generate()`／`generate_json_with_schema()` 呼叫路徑的預設行為不變，仍會 `.strip()`）。

3. **資料契約與驗證工具**（新檔案 `src/utils/patch_generation.py`）：
   - `PatchRecordV1`：完整實作計畫書 §4.2 的欄位與 `to_dict()`，並提供 `from_generation()` 建構子與 `compute_symbol_id()`／`compute_patch_id()`（皆為 SHA-256 雜湊，符合計畫書「以 ticket_id、target_symbol_id、sampling_index 與 generated_code 內容雜湊建立」的規格）。
   - `slice_prefix_suffix()`：依符號 `start_line`／`end_line` 切出 prefix／suffix，並以字元數概算 token（本機無 Code Llama tokenizer，以 ~4 字元/token 概算，概算方式在函式註解中明確標註為近似值），超出預算時 prefix 保留尾端、suffix 保留頭端（貼近插入點的內容優先保留）。
   - `append_ticket_comment_to_prefix()`：將 Ticket 錯誤描述摘要以註解形式附加在 prefix 尾端（目前僅支援 Python `#` 註解，符合 v1 僅支援 Python 的範圍限制）。
   - `validate_syntax()` / `apply_patch()`：`apply_patch()` 一律用**完整、未截斷**的原始檔案內容重組整份檔案（而非 prompt 用的截斷版 prefix/suffix），以 `ast.parse()` 驗證語法，並在需要自動修正換行等狀況時標記 `applied_with_offset`（而非靜默視為 `applied_clean`），任何非預期例外一律回傳 `apply_failed` 而不中斷批次執行。

**測試：** 新增 `tests/test_patch_generation.py`（26 個測試，涵蓋語言判斷、prefix/suffix 切割含截斷邊界、Ticket 註解組裝、語法驗證、`apply_patch()` 的 clean／offset／syntax_error／apply_failed 四種結果、`PatchRecordV1` 身分雜湊穩定性），並在 `tests/test_fault_localization.py` 新增 10 個信心閘門測試與 4 個 `generate_fim()` 測試（涵蓋 prompt 組裝、`<EOT>` 截斷、取樣參數傳遞、型別檢查）。全 repo 測試套件（`tests/` 全部檔案）由修正前的 204 個測試通過，增加為 **244 個全數通過**，無既有測試被破壞。

**已知限制／尚未完成事項：**

- 計畫書 §9 WP1 驗收條件之一「修正後的 `patch_generation_policy` 在既有 46 票 pilot 資料上重新計算，其 block 判定必須涵蓋所有 Stage-3 miss 的 Ticket」**已由使用者在本機實際執行驗證，結果通過。** 因為 `reports/fault_localization/stage3_wp4_pilot/pilot_46tickets.jsonl` 是 Git LFS 物件，雲端開發環境的 git-lfs 因 proxy 授權範圍限制無法下載內容，故新增 `scripts/verify_stage4_wp1_gate_on_pilot.py`（直接重用、而非重新實作正式程式碼中的 `fault_localization._symbol_gate_status()`），交由使用者在本機執行：
  ```bash
  git lfs pull
  python scripts/verify_stage4_wp1_gate_on_pilot.py
  ```
  **實際執行結果（2026-09-12，使用者本機）：**
  ```
  Gate status distribution:
    ready_for_patch                  46
    manual_review_symbol_uncertain   0
    block_no_symbol_candidate        0
    not_applicable                   0
  ```
  46 票全數落在 `ready_for_patch`，與事前推論完全一致（理由：`run_stage3_wp4_symbol_llm_pilot.py` 的 fallback 路徑一律退回到與 `baseline_top` 相同來源、非空的確定性排序，不會產生空的 `llm_top`）。此結果證實新閘門邏輯在真實資料上**沒有誤傷任何一票**——不會把「候選存在、只是排名不準」的 Ticket 誤判為「完全沒有候選」而擋下。這與 WP4 report 中「68.64% recall」代表的是「候選存在但排名錯誤」而非「候選完全不存在」是一致的——閘門只偵測後者，兩者不衝突。另外已用合成情境撰寫單元測試鎖定閘門邏輯本身的正確性（見上），涵蓋所有四種組合，此次真實資料重跑則進一步確認邏輯在生產資料上的行為符合預期。**此項驗收條件視為通過。**
- 計畫書 §9 WP1 另一項驗收條件「FIM 呼叫在至少 3 個手動範例上能產生語法合法的輸出」**已由使用者在本機以真實 Ollama 執行，過程中發現並修正了一個真實 bug，目前已重新確認基礎設施正確，尚待重跑取得最終通過結果。**

  **第一次執行（修正前）：0/3 通過，且失敗模式指向程式碼本身的問題，而非模型能力不足：**
  - `simple_function_body`：輸出出現不一致的縮排層級，且不斷重複輸出多組 `print(clamp(...))` 範例。
  - `bug_fix_off_by_one`：輸出完全不是程式碼，而是一段對話式的說明文字（"The `last_index` function in the code you provided is not correctly implemented..."），還帶有 Markdown code fence。
  - `class_method_infill`：輸出裡甚至逐字出現了 `<SUF>`／`<MID>` 這些字面字串，代表模型把它們當成普通文字接續下去，而不是辨識為特殊控制符。

  **根因診斷：** 這三種失敗模式合起來指向同一件事——`codellama:7b-instruct` 這個 Ollama 標籤預設會套用它自己的 Modelfile 對話／instruct 樣板（把我們的 prompt 包進類似 `[INST] ... [/INST]` 的格式），而不是把 `<PRE>{prefix}<SUF>{suffix}<MID>` 當作要直接續寫的原始文字送進底層模型。結果是 FIM 的控制符號從未真正以「特殊符號」的身份到達模型，模型只是把它們當普通字詞，於是用聊天助理的口吻「回答」而非做程式碼填空。Ollama 的 `/api/generate` API 有一個 `raw` 參數，設為 `true` 時會**繞過樣板系統**，把 prompt 原封不動送給模型——這正是做 FIM 這種底層續寫任務時必須設定的參數，先前的實作漏掉了它。

  **修正：** 在 `src/utils/llm_client.py` 的 `OllamaClient._generate()` 新增 `raw_prompt: bool = False` 參數，`raw_prompt=True` 時在 payload 加入 `"raw": true`；`generate_fim()` 呼叫時固定帶入 `raw_prompt=True`。既有的 `generate()`／`generate_json_with_schema()`（Stage-2／Stage-3 既有、已驗證可用的 LLM rerank 路徑，本來就是自然語言指令＋JSON Schema，設計上就是要走 instruct 樣板）維持預設 `raw_prompt=False`，不受影響。新增測試 `test_generate_fim_builds_prefix_suffix_middle_prompt_without_json_format`（斷言 `payload["raw"] is True`）與 `test_generate_uses_templated_generation_not_raw`（斷言既有路徑的 payload 不含 `raw` 欄位，確認沒有動到 Stage-2／Stage-3 的既有行為）。全 repo 測試套件由 244 個通過增加為 **245 個全數通過**。

  **第二次執行（`raw:true` 修正後）：** 仍是 0/3，但失敗模式質變了——不再是對話式說明或逐字複誦控制符，而是**生成出語法正確的程式碼片段後，模型自行吐出一個 `<EOF>`（不是官方定義的 `<EOT>`），接著繼續「幻覺」出第二輪 `<PRE>/<SUF>/<MID>` 循環**（把 prefix 的 Ticket 註解重講一次、再生一次程式碼）。這代表 `raw:true` 確實生效了（生成內容已經是正確縮排、語法基本正確的 Python，不再是聊天式散文），只是我們原本只在文字裡找 `<EOT>` 才截斷，模型卻用了不在官方規格內的 `<EOF>` 收尾，於是沒被截斷、繼續往下生成垃圾內容，導致 `apply_patch()` 判定整段語法不合法。

  **第二個修正：** 
  1. 在 `_generate()` 呼叫 Ollama 時，於 `options.stop` 帶入停止序列（`<EOT>`／`<PRE>`／`<SUF>`／`<MID>`／`<EOF>`），讓 **Ollama 伺服器自己在生成到這些字串時就停止**，而不是等模型把 `num_predict` 的配額用完、事後才在客戶端裁切——這樣才能真正防止「幻覺出第二輪循環」，而不只是治標地把它裁掉。
  2. 客戶端的裁切邏輯也同步改為：在上述 5 個字串中，取**最早出現**的那個位置裁切（而非只找 `<EOT>`），作為 server-side stop 萬一沒生效時的防線。
  3. `<EOF>` 明確標註為「非官方 FIM 規格，是根據這次真實觀察加入的防禦性標記」，避免未來維護者誤以為它是 Code Llama 論文定義的一部分。

  新增測試 `test_generate_fim_requests_server_side_stop_sequences`（斷言 `options.stop` 內容）與 `test_generate_fim_client_side_truncates_at_observed_eof_loop_marker`（直接把使用者這次真實觀察到的循環樣式當成回歸測試案例）。全 repo 測試套件由 245 個通過增加為 **247 個全數通過**。

  **回放驗證（雲端環境自行執行，2026-09-12）：** 使用者要求「自己先驗證一下」。這個雲端開發環境沒有 Ollama、沒有 GPU，且網路 egress 政策擋掉了 `ollama.com` 與 GitHub Releases 下載主機（403，依規定不得繞過，已如實回報），因此無法在此發起一次全新的真實模型呼叫。改採可行的最大驗證：把使用者第二次執行拿到的**三個範例逐字真實輸出**（而非合成資料）當成 mock 回應，完整跑一次 `scripts/manual_check_generate_fim.py`（包含斷言 `raw:true`／`stop` 參數確實有送出），結果：
  ```
  PASS  simple_function_body
  PASS  bug_fix_off_by_one
  PASS  class_method_infill
  3/3 examples produced syntactically valid, appliable output.
  ```
  這證明修正後的裁切＋驗證邏輯，套用在使用者已經拿到的三筆真實模型輸出上，全部能得到語法合法、可套用的結果。**但這是「重放舊輸出」，不是「重新發起一次即時呼叫」**——理論上這次接上 `stop` 參數後，Ollama 應該會在模型吐出 `<EOF>` 當下就直接停止生成（甚至不會走到後面那段幻覈內容），實際行為預期比這次回放更乾淨，但仍需要使用者在本機做一次真正即時的第三次執行才能算數。

  **第三次執行（使用者本機，即時真實呼叫）：1/3 通過。** 這次是「重新發起一次即時呼叫」，不是重放：
  - `class_method_infill`：**通過**（`applied_clean`）——不再有第二輪幻覺循環，證實 `stop` 參數確實生效。
  - `bug_fix_off_by_one`：模型這次生成完正確程式碼後，改用了**第三種**自創收尾標記 `<INF>`（先前兩次分別是聊天式散文、`<EOF>`），接著又生出一個不相干的 pytest 測試函式，因為 `<INF>` 不在我們的停止序列清單裡，沒被攔下。
  - `simple_function_body`：這次模型只生出一行 `print(clamp(5, 0, 10))`，完全沒有重建 `def clamp(...):` 這行signature，是真正的生成品質不足，不是截斷問題。

  **診斷：** 這個 checkpoint 顯然沒有穩定一致的「結束訊號」——三次觀察到三種不同的收尾行為（聊天式解釋、`<EOF>`、`<INF>`）。如果只靠「把已知標記加進停止清單」，永遠是打地鼠，下一次很可能又冒出第四種沒見過的標記。

  **第三個修正（改變方法，不再只是加標記）：** 在 `src/utils/patch_generation.py` 新增 `trim_generated_code_to_symbol_scope()`，改用**縮排結構**判斷模型是否已經離開目標符號的範圍，而不是依賴模型自己講出哪個字串——利用我們本來就知道的資訊：目標符號在原始檔案裡的縮排層級（`base_indent`）。邏輯是：一旦生成內容裡出現至少一行縮排「深於」`base_indent`（代表已經進到函式/方法本體），之後只要再遇到一行非空白、縮排「回到或淺於」`base_indent`，就代表模型已經離開這個符號的範圍（不管它有沒有講出任何標記），從那一行開始全部裁掉。已整合進 `apply_patch()`，並在觸發裁切時標記 `applied_with_offset`（不會靜默接受）。`<INF>` 也順手加進 `llm_client.py` 的防禦性標記清單，但檔案裡的註解已明講：**這份清單只會越補越多、永遠追不完，真正的防線是縮排結構判斷，不是猜測下一個字串長什麼樣**。

  用這次即時執行的三筆真實輸出重新驗證：`bug_fix_off_by_one`（因為新的縮排裁切）**轉為通過**；`class_method_infill` 維持通過；`simple_function_body` 仍然失敗，因為模型根本沒生成 `def` 這一行，屬於內容缺失，結構裁切工具本來就不打算（也不應該）處理這種情況。**結果：2/3。**

  同時發現 `simple_function_body`／`bug_fix_off_by_one` 兩個手動範例先天上比真實 Stage-3 場景嚴苛——原本的 prefix 是空的（符號是檔案第一行），模型完全沒有上下文可以判斷「這裡應該接一個 `def`」。已將這兩個範例的 prefix 補上一個相鄰的既有函式（`to_int`／`first_index`），使其更貼近真實情況（Stage-3 的符號前面一定有 import 或其他函式）。用一組模擬模型輸出（涵蓋這三種真實觀察過的收尾行為：`<EOF>`＋幻覺垃圾、`<INF>`＋不相干測試、乾淨結束）重跑更新後的 `manual_check_generate_fim.py`，結果 **3/3 通過**。

  新增測試：`TrimGeneratedCodeToSymbolScopeTests`（6 個，直接測裁切函式本身，含「從未見過的任意標記」案例）、`test_apply_patch_trims_content_the_model_generated_past_its_own_scope`（用使用者第三次執行的真實輸出當回歸測試）、`test_apply_patch_does_not_trim_a_well_formed_single_function_completion`（確認正常情況不受影響）。全 repo 測試套件由 247 個通過增加為 **255 個全數通過**。

  **第四次執行（使用者本機，即時真實呼叫）：表面上 3/3 通過，但深入檢查後發現其中一個是「假通過」。** `bug_fix_off_by_one`／`class_method_infill` 都乾淨通過；`simple_function_body` 這次模型生成的內容只有 `print(clamp(15, 10, 20))` 這一行呼叫敘述，**完全沒有重新定義 `clamp` 函式**。但因為 Python 的縮排規則不要求明確關閉區塊，這一行被空白行隔開後、直接被吸收成「前一個函式 `to_int` 的第二條敘述句」，拼回去的整份檔案**語法完全合法**，`apply_patch()` 因此回報 `syntax_valid=True`／`apply_status=applied_clean`——但 `clamp` 函式其實已經被整個刪除，`main()` 呼叫 `clamp(...)` 在真正執行時會是 `NameError`。這是使用者主動追問「你自己先驗證一下」、我逐行檢查重組後的檔案內容才發現的，若只看 `syntax_valid`/`apply_status` 兩個欄位會被誤判為成功。

  **第四個修正（新增一層語意檢查，不只看語法）：** 在 `src/utils/patch_generation.py` 新增 `contains_expected_symbol_definition(generated_code, *, base_indent, symbol_kind, symbol_name)`：把生成內容依 `base_indent` 反縮排後獨立解析，檢查頂層是否真的存在一個名稱、種類都對得上的 `def`／`class` 節點。`apply_patch()` 的 docstring 也同步補上警語：**`syntax_valid` 只保證重組後的「整份檔案」語法合法，不保證目標符號真的被重新定義過**——呼叫端只要知道 `symbol_kind`／`symbol_name`（`stage3_ranked_symbols` 就有），就必須額外呼叫這個新函式，兩個檢查都過才算數。`scripts/manual_check_generate_fim.py` 也同步更新：每個範例現在都帶著預期的 `symbol_kind`／`symbol_name`，PASS/FAIL 判定改為「語法合法 **且** 目標符號真的被重新定義」兩者皆須成立。

  用使用者第四次執行的真實輸出重新跑過更新後的判定：`simple_function_body` 正確地被改判為 **FAIL**（`bug_fix_off_by_one`／`class_method_infill` 仍是 PASS），也就是說**第四次執行的誠實結果是 2/3，不是原本看起來的 3/3**。新增測試 `ContainsExpectedSymbolDefinitionTests`（8 個，含直接用這次真實案例當回歸測試）。全 repo 測試套件由 255 個通過增加為 **263 個全數通過**。

  **第五個修正（回到根因：模型與 API 都選錯了）：** 使用者指出前四輪都只是在「接住壞輸出」，沒有真正修好「為什麼輸出會壞」。重新檢視後找到兩個更上游的錯誤：

  1. **模型 tag 選錯。** 本計畫原本假設（第 5.2 節）Code Llama-Instruct 也支援 infilling。實際上 infilling 是訓練在 base／code checkpoint 上的能力，`-instruct` 是額外疊加的對話微調，而且 Ollama 對 `-instruct` tag 套用的是聊天樣板（`[INST] ... [/INST]`），整條服務路徑都是為對話輪次設計的。這正好解釋了為什麼前四次實測的失敗模式全都是「對話行為」：散文式解釋、自創結束標記、把控制符當普通文字複誦、生成出與定位任務無關的內容。改用 `codellama:7b-code`（同一個 Code Llama 7B 家族、同樣參數量，程式碼補全變體）。
  2. **API 用錯。** 原本是自己把 `<PRE>/<SUF>/<MID>` 這些字串手動拼進 prompt，再靠 `raw:true` 送出。這個做法隱含一個脆弱假設：tokenizer 必須把這些字面字串對回真正的 special token id。Code Llama 的 SentencePiece 詞彙表裡這些 token 實際上是 `▁<PRE>`／`▁<SUF>`／`▁<MID>`（帶前導空白標記），所以 `{prefix}<SUF>` 這種沒有空格的寫法可能根本對不上，會被切成 `<`、`SU`、`F`、`>` 這些普通文字——整個 FIM prompt 就退化成一段普通散文，模型自然開始自由聯想。改用 **Ollama 原生的 infilling API**：prefix 放 `prompt`、suffix 放 `suffix` 欄位，由伺服器依模型自己的樣板組出 FIM prompt、使用真正的 special token id，整類「手拼字串對不上 token」的問題直接消失。手工 PSM 路徑保留為 fallback（`use_native_suffix=False`），並把間距修正為正確的 `" <PRE> {prefix} <SUF>{suffix} <MID>"`。

  `OllamaClient` 新增 `fim_model` 欄位（預設 `codellama:7b-code`），與既有的 `model`（維持 `codellama:7b-instruct`，供 Stage-2／3 JSON 重排序使用）分離，兩條路徑互不影響。新增測試涵蓋：原生 suffix 請求格式與模型 tag、fallback 路徑的 PSM 間距與 `raw:true`、以及「JSON 重排序路徑仍然使用 instruct tag」的回歸保護。全 repo 測試套件由 263 個通過增加為 **265 個全數通過**。前四輪加上的防禦措施（停止序列、縮排結構裁切、符號定義檢查）全部保留——它們處理的是「模型輸出不可靠」這個本質問題，不會因為換了正確的模型就不需要。

  **第五次執行（使用者本機，即時真實呼叫，`codellama:7b-code` ＋ 原生 suffix API）：3/3 通過，此項驗收條件正式達成。**
  ```
  FIM model: codellama:7b-code
  FIM request mode: native suffix field
  ...
  PASS  simple_function_body
  PASS  bug_fix_off_by_one
  PASS  class_method_infill
  3/3 examples produced a syntactically valid, appliable patch that actually redefined the target symbol.
  ```
  而且**三個補丁的內容在語意上也都是正確的**（不只是語法合法）：`clamp` 生成 `max(min(value, high), low)`、`last_index` 生成 `len(items) - 1`（正確修掉 off-by-one）、`Counter.increment` 生成 `self.value += amount; return self.value`。這比本項驗收標準（只要求語法合法）要求得更高，也直接印證了第 ⑤ 項根因診斷是對的：前四輪的失敗不是「模型能力不足」，而是模型 tag 與 API 選錯。

  **第六個修正（補丁品質清理，由這次成功結果的殘留雜訊驅動）：** 即使三個範例都通過，逐字檢視生成內容仍看到兩類會污染真實 diff 的雜訊：
  1. **定義前的幻覺內容**：`class_method_infill` 的補丁前面帶了兩行模型自己捏造的 `# Ticket summary:` 註解，內容還是在講**其他**方法（`decrement`、`reset`）。註解在語法上無害，所以前面所有檢查都會放行——但它們會原封不動被寫進使用者的 class 裡。既有的裁切函式只負責找「符號在哪裡結束」，管不到前面。
  2. **尾端空白行**：三個範例的生成內容都以一行「只有一個空格」的行結尾，會在 diff 裡變成 trailing whitespace，很多專案的 linter／pre-commit 會直接擋下。

  新增 `trim_leading_content_before_symbol_definition()`（用正規式定位目標定義的起始行，連同其上方緊鄰的裝飾器一起保留，前面的東西全部丟棄；找不到定義時原樣返回，交由 `contains_expected_symbol_definition()` 判定失敗）與 `strip_trailing_blank_lines()`，兩者都整合進 `apply_patch()`（新增選用參數 `symbol_kind`／`symbol_name`，兩者都可直接從 `stage3_ranked_symbols` 取得），並在觸發時各自記錄 note、標記 `applied_with_offset`，不靜默處理。用使用者這次三筆**真實輸出**重跑完整流程驗證，三個重組後的檔案現在都與人手寫的結果完全一致：沒有多餘空白行、沒有幻覺註解、沒有多生出來的方法。新增測試 `TrimLeadingContentTests`（7 個）、`StripTrailingBlankLinesTests`（3 個）、以及用這次真實輸出當端對端回歸的 `test_apply_patch_cleans_a_real_codellama_7b_code_completion_end_to_end`。全 repo 測試套件由 265 個通過增加為 **276 個全數通過**。

  此修正不需要再跑一次即時模型呼叫即可驗證——它是純結構性處理，且已直接用這次拿到的真實模型輸出逐字驗證過。
- WP2 程式碼已完成（見第 17 節）；WP3（測試生成／FIB）、WP4（回歸驗證／RIPR／plausible-correct）、WP5（正式比較與凍結）尚未開始。

**檔案異動清單（已同步寫回使用者本機 repo）：**
- 修改：`src/utils/fault_localization.py`、`src/utils/llm_client.py`、`README.md`、`tests/test_fault_localization.py`
- 新增：`src/utils/patch_generation.py`、`tests/test_patch_generation.py`、`scripts/verify_stage4_wp1_gate_on_pilot.py`、`scripts/manual_check_generate_fim.py`

**下一個任務：WP1 已全部完成並驗證；WP2 程式碼已完成（見第 17 節），下一步是使用者在本機依三階段執行順序做真實驗收。** 使用者需先自行 `git add`／`commit`／`push` 本次變更（包含 WP2 新增檔案）。

WP2 開始前的注意事項（由 WP1 驗證過程得到，WP2 實作已遵循）：
- 環境需具備 `codellama:7b-code`（FIM 用）與 `codellama:7b-instruct`（Stage-2／3 重排序用）兩個模型，兩者用途不可混用。
- 批次腳本呼叫補丁驗證時務必傳入 `symbol_kind`／`symbol_name`，否則會少掉「定義前雜訊清理」與「符號確實被重新定義」兩層保護。
- 判定一個候選補丁是否可用，必須同時檢查語法合法與符號確實被重新定義，缺一不可——只看前者會放行「語法完美但目標符號已被刪除」的補丁。`generate_stage4_patches.py` 呼叫的是新增的 `apply_patch_and_verify_symbol()`（見第 17 節），已經內建這個雙重檢查，不需要呼叫端自己再做一次。

---

## 17. WP2 完成紀錄（2026-09-12）

**狀態：WP2（補丁生成 Pipeline）程式碼已完成並通過全部單元測試（312 個全數通過），但尚未在真實 Ollama／真實 46 票 pilot 資料上做過真實模型執行。** 這點與 WP1 不同：WP1 的兩項驗收條件都已由使用者在本機真實跑過；WP2 目前只做到「pipeline 本身正確」（用假的 FIM 回應＋本機臨時 git repo 驗證整條流程），第 9 節 WP2 驗收條件要求的「conditional Patch Apply Rate 有明確數字」與「1-ticket→10-ticket→46-ticket 三階段」都需要使用者在本機執行才能取得。

**新增檔案：**
- `src/utils/repo_snapshot.py`：依 (repo, base_commit) 解析本機 git 快取，用 `clone --shared --no-checkout` + `checkout --detach` 產生唯讀快照，讀出完整檔案內容（`stage3_ranked_symbols[*].code_text` 只有符號本體，FIM 切 prefix/suffix 需要整個檔案）。邏輯沿用 `scripts/run_swebench_lite_fault_localization.py` 已驗證過的機制，獨立成小模組以便測試，不改動原本的 Stage-1 批次腳本。
- `scripts/generate_stage4_patches.py`：WP2 主要批次腳本，對照第 13 節命令介面。讀取 `--predictions`（Stage-3 `_prediction_row` 格式：`ticket_id`／`repo`／`base_commit`／`stage3_ranked_symbols`）→ 篩選 conditional-eligible（`stage3_ranked_symbols` 非空）→ 對 top-`--symbol-topk`（預設 1）個候選符號用 `repo_snapshot` 讀檔 → `slice_prefix_suffix` → 對凍結 temperature 清單（0.2/0.4/0.6）各採樣一次 FIM → `apply_patch_and_verify_symbol` → 輸出 `PatchRecordV1` jsonl，並印出 Syntax Valid Rate／Apply Rate／失敗原因分佈。支援 `--limit` 供三階段 smoke 測試，以及 `--ticket-ids-from`（見下方「新發現」）。
- `configs/fault_localization/stage4_patch_generation_v1.json`：凍結 FIM 參數（prefix/suffix token 預算各 2048、temperature 清單 0.2/0.4/0.6、symbol_topk=1）。
- `tests/test_repo_snapshot.py`（14 個）、`tests/test_generate_stage4_patches.py`（17 個）。

**修改檔案：**
- `src/utils/patch_generation.py`：新增 `apply_patch_and_verify_symbol()`，包裝既有 `apply_patch()` ＋ `contains_expected_symbol_definition()`，語法合法但符號未被重新定義時把 `apply_status` 降級為 `apply_failed` 並附註記。`apply_patch()` 本身完全沒改動（避免動到 WP1 已凍結的資料契約與既有測試）。新增 `tests/test_patch_generation.py::ApplyPatchAndVerifySymbolTests`（6 個，含用 WP1 真實 false-positive 案例〔`clamp` 被吃掉〕做的迴歸測試）。

**實作中發現、且已修正的落差（原計畫沒明講的細節）：**
1. **`--predictions` 的真實檔案已經存在，不必新產生**：計畫書第 13 節命令介面寫的 `stage3_deterministic_g2_dev_v1/predictions.jsonl` 是示意路徑；查證後，`run_stage3_deterministic_g2.py` 實際輸出檔名是 `<variant_id>_predictions.jsonl`，而 Stage-3 WP4 pilot 實際使用的正是其中的 `b1_coverage_aware_v1` 變體，檔案已存在於 `reports/fault_localization/stage3_source_neighborhood_dev_v1/b1_coverage_aware_v1_predictions.jsonl`（LFS 追蹤，需要 `git lfs pull`）。使用者可以直接拿這個檔案當 `--predictions`，不需要重跑 Stage-3。
2. **必須把 WP2 限定在與 WP4 相同的 46 票，而不是整個 development split**：`b1_coverage_aware_v1_predictions.jsonl` 涵蓋的是完整 development 集合（遠多於 46 票），但計畫書明確要求「沿用既有 46 票集合，避免引入新的抽樣差異」。所以新增了 `--ticket-ids-from`（可直接指向 `pilot_46tickets.jsonl`，腳本會從其 `ticket_id` 欄位取出允許清單），在篩選 conditional-eligible 與套用 `--limit` **之前**先把資料收斂到這 46 票，避免三階段 smoke test 悄悄跑到不同的母體上。
3. **Ticket 錯誤描述摘要是可選的，不是命令介面缺的東西**：`b1_coverage_aware_v1_predictions.jsonl` 這種精簡 predictions 檔沒有附 `problem_statement`／`bug_report` 文字，但 `append_ticket_comment_to_prefix()` 在摘要為空時本來就是無操作（原樣返回 prefix）。因此新增 `--tickets`（可選）指向原始 Ticket 來源檔做摘要豐富化，沒有提供時整條 pipeline 照常運作，只是 prompt 少一段錯誤描述註解。
4. **只對 Top-1 符號生成補丁，可用 `--symbol-topk` 調整**：計畫書沒有明講「每張 Ticket 生成幾個符號的補丁」。預設只對 `stage3_ranked_symbols[0]`（最高分候選）生成，這對應一個真實系統實際會採取行動的位置；若要對更多候選符號生成（會讓 FIM 呼叫量線性增加），可用 `--symbol-topk` 調高。
5. **`model_digest` 目前是佔位符**：計畫書 `PatchRecordV1` 範例的 `model_digest` 是 `sha256:model-digest` 格式，但取得 Ollama 模型的真實 digest 需要呼叫 `/api/show`，這在雲端環境沒有 Ollama 連線可測；目前預設寫入 `placeholder:<model tag>`。若要記錄真實 digest，可在使用者本機執行 `ollama show codellama:7b-code --modelfile | sha256sum` 後用 `--model-digest` 傳入。

**驗證方式（本次未做，因為雲端環境沒有真實 Ollama／GPU 也沒有 repo 快取）：**
- 用假的 `OllamaClient.generate_fim`（monkeypatch）＋本機臨時建立的 git repo，跑過完整 CLI（`main()` 端對端），確認：設定檔讀取、conditional-eligible 篩選、repo 快照解析、FIM 呼叫、`apply_patch_and_verify_symbol`、`PatchRecordV1` 輸出 jsonl、統計數字全部正確（3 個 temperature 樣本、100% syntax valid、100% applied_clean）。
- 312 個單元測試全數通過（`python -m pytest -q`），涵蓋 `repo_snapshot` 的 git 快照解析（含路徑穿越防護、commit 找不到、快取重用）、`apply_patch_and_verify_symbol` 的降級邏輯、批次腳本的 eligibility／symbol-topk／`--limit`／`--ticket-ids-from`／不支援語言／repo 解析失敗等錯誤路徑。

**使用者需要在本機執行的三階段驗收（依第 9 節 WP2 驗收條件與第 11.3 節執行順序）：**

```powershell
cd "C:\Users\owner\Desktop\專題\專題0908錯誤定位\fault-localization-feature-files"
git lfs pull   # 確保 b1_coverage_aware_v1_predictions.jsonl、pilot_46tickets.jsonl 都是真實內容

# 1-ticket smoke
python scripts\generate_stage4_patches.py `
  --predictions reports\fault_localization\stage3_source_neighborhood_dev_v1\b1_coverage_aware_v1_predictions.jsonl `
  --ticket-ids-from reports\fault_localization\stage3_wp4_pilot\pilot_46tickets.jsonl `
  --repo-cache-dir data\repositories `
  --config configs\fault_localization\stage4_patch_generation_v1.json `
  --output reports\fault_localization\stage4_patch_generation_dev_v1\patches_smoke1.jsonl `
  --limit 1

# 10-ticket smoke（1-ticket 結果沒問題後再跑）
python scripts\generate_stage4_patches.py `
  --predictions reports\fault_localization\stage3_source_neighborhood_dev_v1\b1_coverage_aware_v1_predictions.jsonl `
  --ticket-ids-from reports\fault_localization\stage3_wp4_pilot\pilot_46tickets.jsonl `
  --repo-cache-dir data\repositories `
  --config configs\fault_localization\stage4_patch_generation_v1.json `
  --output reports\fault_localization\stage4_patch_generation_dev_v1\patches_smoke10.jsonl `
  --limit 10

# 46-ticket pilot（正式這輪的結果）
python scripts\generate_stage4_patches.py `
  --predictions reports\fault_localization\stage3_source_neighborhood_dev_v1\b1_coverage_aware_v1_predictions.jsonl `
  --ticket-ids-from reports\fault_localization\stage3_wp4_pilot\pilot_46tickets.jsonl `
  --repo-cache-dir data\repositories `
  --config configs\fault_localization\stage4_patch_generation_v1.json `
  --output reports\fault_localization\stage4_patch_generation_dev_v1\patches.jsonl
```

**執行前提：**
- `ollama pull codellama:7b-code` 已完成（WP1 已驗證過的模型／API 路徑，`ollama serve` 需在背景執行）。
- `data/repositories` 底下要有這 46 票會用到的 repo 快取（非 bare git checkout）；如果還沒有，先跑 `python scripts/prefetch_swebench_repositories.py`，或對個別缺的 repo 加 `--clone-missing`（會觸發網路 clone）。
- 每個階段跑完先看終端機印出的 Syntax Valid Rate／Apply Rate／失敗原因分佈是否合理，再進到下一階段——不要三階段一次排隊跑完才檢查，避免同一設定錯誤浪費在 46 票上才發現。

**下一個任務：** 使用者在本機完成上述三階段驗收後回報結果；若 conditional Patch Apply Rate 明顯偏低（第 10 節 G2 門檻：≥80%），先檢視 prefix/suffix 切割邊界與 token 預算設計，不急著進入 WP3。驗收通過後即可開始 WP3（測試案例生成與 FIB 篩選，仿 LIBRO）。

---

## 18. WP2 1-ticket smoke 除錯紀錄與輸入層級發現（2026-09-12）

**狀態：WP2 的 1-ticket smoke 連續執行三輪，全部 0/3。三輪各暴露出一個獨立的真實缺陷，全部已修正並有測試覆蓋。第三輪之後確認：剩下的不是管線 bug，而是「整個符號重寫」這個策略本身對這批資料不可行。**

三輪都以 `astropy__astropy-13073` 為目標（`astropy/io/ascii/ui.py` 的 `read` 函式）。

### 18.1 第一輪：生成額度寫死（`num_predict=256`）

三個樣本全部被硬切在句子中間（`get_format_list_with_extensions_and_delimit`、`If the ``format`` is not given then the`、`except Exception as err:`）。

**根因：** WP1 的手動範例是 2–3 行的小函式，`num_predict=256` 夠用；WP2 直接沿用這個常數，但真實 Stage-3 符號大小是任意的。該目標實測 80 行／3301 字元 ≈ 825 tokens，**模型只拿到所需額度的 31%**，每次生成必然被截斷，並被記成 `syntax_error`——看起來像模型能力不足，其實是設定錯誤。

**修正：** 新增 `patch_generation.resolve_num_predict()`，依「被替換符號的估計 token 數 × headroom（預設 2.0）」動態計算，並以 `[min, max]` 夾限。設定檔的 `fim.num_predict` 改為 `num_predict_headroom`／`min_num_predict`／`max_num_predict`。該目標的額度由 256 變為 1652（需求量的 200%）。

### 18.2 第二輪：prompt 內沒有錯誤描述

生成長度從 850 → 5900 字元（證實額度修正生效），但 temp 0.2／0.4 跑去重新生成檔案開頭的 import 區塊。

**根因：** 執行時未傳 `--tickets`，`append_ticket_comment_to_prefix()` 在摘要為空時是無操作，所以 prompt 裡完全沒有 bug 描述——模型沒有任何目標，只能「合理地把檔案接下去」。這個失敗在 Syntax／Apply 數字上完全看不出來。

**修正：** 摘要輸出新增「有幾張票帶了錯誤描述」統計行，缺少時印出警告。正確的 ticket 來源檔為 `data/fault_localization/swebench_full/stage3_symbol_gold/development_source_tickets.jsonl`（含 `bug_report` 欄位）。

**同時處理的正解洩漏風險：** 上述 ticket 檔案同時含有 `patch`（開發者正解）、`fail_to_pass`／`pass_to_pass`（測試名稱）、`hints_text`（提示）。第 4.1 節明文禁止正解進入任何 LLM prompt。原本只是「剛好沒讀到那些欄位」，現已改為程式強制保證：明確區分 `TICKET_DESCRIPTION_FIELDS`（可送給模型）與 `TICKET_GROUND_TRUTH_FIELDS`（絕對禁止），兩者不得重疊，並加了端對端測試驗證 prompt 內不含正解內容。**此類洩漏最危險之處在於它會讓數字變好看而不會讓程式報錯。**

### 18.3 第三輪：Stage-3 的 `end_line` 是 chunk 邊界，不是定義邊界

**根因：** Stage-1 的程式碼索引以固定大小（本專案為 80 行）切 chunk，`stage3_ranked_symbols[*].end_line` 取的是 chunk 的結尾。任何超過一個 chunk 的定義都會被回報成截斷的範圍。實測：Stage-3 回報 `function read` 為 252–331（剛好 80 行），真實的 `def read` 是 **252–388（137 行）**——起點正確，結尾少了 57 行，落在函式主體中間。

拿這個範圍當補丁替換區間，等於「用生成內容取代函式的前 80 行，後面 57 行舊的函式主體原封不動留著」——沒有任何補丁能滿足這個條件。

**修正：** 新增 `patch_generation.resolve_symbol_line_range()`，用 Stage-3 提供的符號**名稱**去真實原始碼以 AST 解析出真正的定義邊界（含裝飾器），chunk 範圍僅作為同名符號的消歧義線索（取重疊度最高者）。解析失敗時回傳 `resolved=False` 並由批次腳本記為 `symbol_range_unresolved` 跳過，**絕不退回使用 chunk 範圍**。以真實檔案驗證：解析結果 252–388，與 AST ground truth 完全一致。

### 18.4 第三輪之後：這不再是管線問題，而是 granularity 問題

三個修正全部到位後，第三輪的失敗模式變成：temp 0.2 正確寫出 `def read(...)` 但中途陷入退化重複；temp 0.4 寫模組開頭；temp 0.6 寫出函式內容卻漏掉 `def` 那一行。

目標是一個 **137 行**的函式——要求 7B 模型把 136 行沒問題的程式碼一字不差重寫、再加上修正。這是模型能力的天花板，不是調 prompt 能繞過的。

**以 `scripts/inspect_stage4_input_symbols.py` 量測 46 票 top-1 目標的真實定義大小：**

| 目標大小 | 票數 | 佔比 |
|---|---|---|
| ≤20 行 | 15 | 33.3% |
| 21–50 行 | 7 | 15.6% |
| 51–100 行 | 9 | 20.0% |
| **>100 行** | **14** | **31.1%** |

中位數 52 行，**最大 6470 行**（`pydata__xarray-4940` 的 `Dataset` 類別）。46 張票中有 17 張的 top-1 是整個 class。

**結論：維持「重寫 Stage-3 top-1 符號」的策略，Apply Rate 不可能接近第 10 節 G2 門檻的 80%。** 這不是模型或 prompt 的問題：修一個 bug 通常是改某個方法裡的幾行，重寫整個 6470 行的類別在語意上本來就不是一個合理的「補丁」。

### 18.5 候選選取策略模擬（尚未實作，待決策）

`stage3_ranked_symbols` 每張票有 2–5 個可解析候選，因此當 top-1 是大類別時，排名較後的候選常是該類別內部的小方法。模擬「沿著 Stage-3 **自身排名**往下取第一個大小在上限內的候選」：

| 大小上限 | 有可行目標 | 用 rank 1 | 用 rank>1 | 完全找不到 |
|---|---|---|---|---|
| 30 行 | 40 (87.0%) | 17 | 23 | 6 |
| **50 行** | **43 (93.5%)** | 22 | 21 | 3 |
| 100 行 | 46 (100%) | 31 | 15 | 0 |
| 200 行 | 46 (100%) | 35 | 11 | 0 |

**建議採用 50 行上限**（93.5% 覆蓋率，且 50 行確實在 7B 模型能力範圍內）。

**必須誠實記錄的方法論代價：** 此策略改變了實驗在量測什麼。Stage-3 的 recall 是對整個排名清單量測的；系統性改挑「較小」的候選，等於用「生成可行性」換「補到正確位置的機率」——**補丁很可能補在錯的符號上**，會直接壓低最終 Correct Patch Rate。50 行上限下，43 張票中有 21 張（49%）使用的不是第一名候選。

因此若採用，`PatchRecordV1` 需加記**實際使用的 rank 與目標行數**，最終報告必須同時給出兩個數字，並明說篩選規則：
- **嚴格版**：僅 rank-1 且在上限內的目標（50 行上限下為 22 張票）
- **放寬版**：排名最高且在上限內的目標（43 張票）

這與第 8.1 節「conditional 與 end-to-end 並列回報」的一貫作法一致，只是多了一層「conditional on 目標夠小」的條件，不得只挑好看的數字報而不說樣本如何篩選。

### 18.6 其他已修正的環境層級缺陷

- `scripts/prefetch_swebench_repositories.py` 與 `scripts/run_swebench_lite_fault_localization.py` 呼叫 git 時未指定編碼，在繁體中文 Windows（cp950）上遇到 git 的 UTF-8 輸出會直接 `UnicodeDecodeError` 當機。已明確指定 `encoding="utf-8", errors="replace"`。
- 同一支腳本判斷「repo 是否已初始化」只看 `.git` 是否存在，導致上述當機在 `git init` 與 `git remote add` 之間中斷後，12 個 repo 全部永久卡在「有 `.git` 但無 `origin`」狀態，`--resume` 也救不回來。已改為**每次執行都確保 origin 存在且正確**（`ensure_origin_remote()`），並加了 3 個迴歸測試。
- 專案根目錄下的非測試資料夾（如 `Claude outputs/`）會被 pytest 收集並與 `tests/` 同名檔案衝突。已在 `pyproject.toml` 加 `testpaths = ["tests"]`。

### 18.7 目前檔案狀態

**新增：** `src/utils/repo_snapshot.py`、`scripts/generate_stage4_patches.py`、`scripts/inspect_stage4_input_symbols.py`、`configs/fault_localization/stage4_patch_generation_v1.json`、`tests/test_repo_snapshot.py`、`tests/test_generate_stage4_patches.py`

**修改：** `src/utils/patch_generation.py`（新增 `apply_patch_and_verify_symbol`／`resolve_symbol_line_range`／`resolve_num_predict`／`extract_symbol_text`）、`scripts/prefetch_swebench_repositories.py`、`scripts/run_swebench_lite_fault_localization.py`、`pyproject.toml`、`tests/test_patch_generation.py`、`tests/test_prefetch_swebench_repositories.py`

全套測試 **337 個通過**。

**下一個決策點：** 是否採用 18.5 的候選選取策略（含 50 行上限與雙軌回報）。採用後才有意義進行 10-ticket smoke；在此之前跑 46 票 pilot 只會得到一個已知會失敗的數字。
