# Stage-4 WP2 補丁生成：實作指南

日期：2026-09-12
狀態：規格草案，待實作
前置文件：`STAGE4_PATCH_GENERATION_IMPLEMENTATION_PLAN_ZH.md` 第 16–18 節（除錯紀錄與實測數據）

---

## 0. 這份文件要解決什麼

WP2 的第一版實作（整個符號用 FIM 重寫）在真實 46 票上連續三輪 0/3，已確認**策略本身不可行**，不是參數問題。這份文件規定第二版要怎麼做。

**一句話的架構改變：把「重寫整個符號」改成「產出精準的局部修改」。**

理由來自實測數據（46 票 top-1 目標的真實定義大小）：

| 目標大小 | 票數 | 佔比 |
|---|---|---|
| ≤20 行 | 15 | 33.3% |
| 21–50 行 | 7 | 15.6% |
| 51–100 行 | 9 | 20.0% |
| >100 行 | 14 | 31.1% |

中位數 52 行，最大 6470 行（`pydata__xarray-4940` 的 `Dataset` 類別），46 張票中 17 張的 top-1 是整個 class。

**只要輸出是「符號的新版本」，輸出長度就正比於符號大小**，7B 模型不可能把 136 行程式碼一字不差重寫再加修正。改成局部修改後，輸出長度正比於**修改量**（通常 1–10 行），與符號多大無關。

---

## 1. 編輯格式：SEARCH/REPLACE 區塊

### 1.1 為什麼不用 unified diff

unified diff 需要模型正確產生行號與上下文行數（`@@ -252,7 +252,8 @@`）。小模型算錯行號的機率很高，而算錯之後 patch 會套用失敗或套到錯的位置，且錯誤難以歸因。

### 1.2 採用的格式

要求模型輸出一或多個區塊：

```
<<<<<<< SEARCH
    if not isinstance(argument, str):
        return argument
=======
    if argument is None:
        return ""
    if not isinstance(argument, str):
        return argument
>>>>>>> REPLACE
```

**套用方式：在目標符號的文字範圍內做精確字串比對取代，完全不涉及行號。**

這個格式的好處：

- 輸出長度 ∝ 修改量，與符號大小無關（解決根本問題）
- 沒有行號算術，就沒有 off-by-one 這整類錯誤
- 失敗是**可偵測且明確的**：SEARCH 區塊找不到 → 直接拒絕，不猜測、不模糊比對
- 失敗原因具體，天然適合回饋給模型重試（見第 4 節）

### 1.3 硬性規則

- SEARCH 文字必須在目標符號範圍內**恰好出現一次**。出現 0 次 → `search_not_found`；出現 2 次以上 → `search_ambiguous`。兩者都直接拒絕該候選，**不得**退而求其次用第一個匹配或模糊比對。
- 比對前不做任何正規化（不去空白、不轉換縮排）。縮排就是語意，模糊比對會產生語法正確但縮排錯誤的補丁。
- 允許一次輸出多個區塊（一個 bug 可能要改兩處），逐一套用，任一個失敗則整筆候選失敗。

---

## 2. 目標選取：大小上限 + 沿排名往下找

### 2.1 規則

```
對每張 conditional-eligible 的票：
  for cand in stage3_ranked_symbols:            # 依 Stage-3 自己的排名
      resolved = resolve_symbol_line_range(...)  # 解出真實定義邊界
      if not resolved.resolved:      continue    # 記 symbol_range_unresolved
      if size(resolved) > max_target_lines: continue
      return cand, resolved                      # 取第一個符合的
  return None                                    # 記 no_target_within_size_limit
```

**不得**在解析失敗時退回使用 Stage-3 的 `start_line`/`end_line`——那是 chunk 邊界不是定義邊界（見第 3.1 節）。

### 2.2 上限選擇

模擬結果（每張票有 2–5 個可解析候選）：

| 上限 | 有可行目標 | 用 rank 1 | 用 rank>1 |
|---|---|---|---|
| 30 行 | 40 (87.0%) | 17 | 23 |
| **50 行** | **43 (93.5%)** | 22 | 21 |
| 100 行 | 46 (100%) | 31 | 15 |

**建議 50 行**：93.5% 覆蓋率，且 50 行的符號完整放進 prompt 不會擠壓上下文預算。

### 2.3 必須誠實處理的方法論代價

系統性改挑較小的候選，等於**用「生成可行性」換「補到正確位置的機率」**。50 行上限下，43 張票裡有 21 張（49%）用的不是 Stage-3 第一名——這些很可能補在錯的符號上，會直接壓低 Correct Patch Rate。

**因此強制要求**：

1. `PatchRecordV1` 必須記錄實際使用的 `target_rank` 與 `target_lines`（見第 5 節）
2. 最終報告必須**同時**給出兩個數字，並明說篩選規則：
   - **嚴格版**：僅 `target_rank == 1` 的票（50 行上限下為 22 張）
   - **放寬版**：排名最高且符合上限的票（43 張）

只報放寬版而不揭露篩選方式，等同於選樣後隱藏覆蓋損失。這與計畫書第 8.1 節「conditional 與 end-to-end 並列回報」是同一個原則。

---

## 3. 必須沿用的既有元件

以下都已實作、有測試、且與生成方式無關，**直接用，不要重寫**。

### 3.1 `utils.patch_generation.resolve_symbol_line_range()` — 最關鍵

Stage-3 的 `end_line` 是 **80 行 chunk 的結尾**，不是定義的結尾。實測 `astropy__astropy-13073`：

| | 行號 | 行數 |
|---|---|---|
| Stage-3 回報的 `read` | 252–331 | 80（= chunk 大小）|
| 真實的 `def read` | 252–388 | 137 |

用 chunk 範圍當替換區間 → 取代函式前 80 行、後面 57 行舊主體留在原地 → 沒有任何補丁能滿足 → 被記成 `syntax_error`，**看起來像模型不行，其實是輸入邊界錯誤**。

```python
resolved = resolve_symbol_line_range(
    file_text,
    symbol_qualified_name=cand["symbol_qualified_name"],
    symbol_name=cand["symbol_name"],
    hint_start_line=cand["start_line"],   # chunk 範圍只當「在哪附近」的線索
    hint_end_line=cand["end_line"],
)
# -> ResolvedSymbolRange(start_line, end_line, resolved: bool, reason: str)
```

以名稱在真實原始碼用 AST 解析定義邊界（含裝飾器）；同名符號以與 chunk 範圍的重疊度消歧義。

### 3.2 `utils.repo_snapshot`

```python
source_repo = resolve_repository_path({"repo": repo}, repo_cache_dir=...)
snapshot    = materialize_commit_snapshot(source_repo, repo=..., base_commit=..., snapshot_cache_dir=...)
file_text   = read_file_text(snapshot, file_path)     # 失敗一律 RepoSnapshotError
```

依 `(repo, base_commit)` 產生唯讀 detached checkout，同一 pair 會重用快照。

### 3.3 驗證三件套

```python
validate_syntax(text) -> bool                      # 重組後的檔案能否 ast.parse
contains_expected_symbol_definition(...) -> bool   # 目標符號是否仍被定義
apply_patch_and_verify_symbol(...) -> ApplyResult  # 上面兩者的組合，失敗降級為 apply_failed
```

**`syntax_valid` 為 True 不代表補丁有意義**：Python 不要求顯式關閉區塊，一段落單的敘述可能被前一個函式的主體吸收，產出完全合法但目標符號已消失的檔案（WP1 實測踩過）。因此符號檢查不可省略。

### 3.4 正解隔離

`scripts/generate_stage4_patches.py` 的 `TICKET_DESCRIPTION_FIELDS` / `TICKET_GROUND_TRUTH_FIELDS`。

ticket 來源檔 `development_source_tickets.jsonl` 含 `bug_report`（可用），**同時含 `patch`、`fail_to_pass`、`pass_to_pass`、`hints_text`（絕對禁止進 prompt）**。這類洩漏會讓數字變**好看**而不會讓程式報錯，所以必須是程式強制而非慣例。新增任何 prompt 欄位時，都要確認它不在禁用清單內。

---

## 4. 迭代重試

計畫書第 14 節要求「固定迭代次數上限 ≤3」。

```
for attempt in 1..3:
    blocks = model_generate(prompt)
    ok, new_text, reason = apply_edit_blocks(target_text, blocks)
    if not ok:
        prompt = base_prompt + failure_feedback(reason, blocks)   # 見下
        continue
    result = apply_patch_and_verify_symbol(...)
    if result.apply_status in ("applied_clean", "applied_with_offset"):
        return result
    prompt = base_prompt + failure_feedback(result.apply_status, result.notes)
```

回饋內容必須具體到可行動：

| 失敗原因 | 回饋給模型的訊息 |
|---|---|
| `search_not_found` | 附上找不到的那段 SEARCH 文字，要求逐字複製原始碼 |
| `search_ambiguous` | 說明出現多次，要求加長 SEARCH 以取得唯一性 |
| `syntax_error` | 附上 `SyntaxError` 的行號與訊息 |
| `symbol_missing` | 說明目標符號被刪除，要求保留 `def`/`class` 那一行 |

**每次 attempt 都要記錄**（`attempt_count`、每次的失敗原因），否則無法回答「重試有沒有用」這個問題。

---

## 5. 資料契約變更

`PatchRecordV1` 現有欄位保留，**新增**：

| 欄位 | 型別 | 用途 |
|---|---|---|
| `target_rank` | int | 實際使用的候選在 `stage3_ranked_symbols` 的名次（1-based）。雙軌回報的依據 |
| `target_lines` | int | 解析後定義的行數 |
| `target_symbol_kind` | str | function / method / class |
| `target_symbol_name` | str | 除錯用；目前只有 hash 過的 `target_symbol_id`，人看不懂 |
| `edit_format` | str | `"search-replace-v1"`，未來換格式時可區分 |
| `attempt_count` | int | 實際用掉幾次重試 |
| `attempt_failures` | list[str] | 每次失敗的原因代碼 |

`schema_version` 隨之改為 `"patch-record-v2"`。`apply_status` 取值不變（`applied_clean` / `applied_with_offset` / `syntax_error` / `apply_failed`），新增的失敗原因（`search_not_found` 等）記在 `attempt_failures`，避免破壞既有取值定義。

`prompt_version` 改為 `"patchgen-search-replace-v1"`。

---

## 6. 實作順序

每一階段都要能獨立驗收再往下，不要一路寫到底才測。

### 階段 1：編輯區塊的解析與套用（純離線，不碰模型）

**新檔案 `src/utils/patch_edit_blocks.py`：**

```python
@dataclass(slots=True)
class EditBlock:
    search: str
    replace: str

@dataclass(slots=True)
class EditApplyResult:
    text: str
    applied: bool
    reason: str          # "" | search_not_found | search_ambiguous | no_blocks | malformed
    applied_block_count: int

def parse_edit_blocks(model_output: str) -> list[EditBlock]: ...
def apply_edit_blocks(target_text: str, blocks: list[EditBlock]) -> EditApplyResult: ...
```

**測試（`tests/test_patch_edit_blocks.py`）至少涵蓋：**
單一區塊、多個區塊、SEARCH 找不到、SEARCH 出現兩次、格式殘缺（缺 `=======` 或結尾標記）、模型在區塊外夾雜散文（要能忽略）、空輸出、SEARCH 含正規表示式特殊字元（必須當字面字串處理）、CRLF 與 LF 混用。

**驗收：** 上述測試全過，且 `apply_edit_blocks` 在任何輸入下都不拋例外、只回報 reason。

### 階段 2：目標選取與資料契約

- `select_target_symbols()` 改為實作第 2.1 節的規則，回傳 `(candidate, resolved_range, rank)`
- 設定檔加 `symbol_selection.max_target_lines`（預設 50）
- `PatchRecordV1` 加第 5 節欄位，`schema_version` 升版

**測試：** top-1 過大時往下取、全部過大時回傳 None 並記 `no_target_within_size_limit`、解析失敗的候選被跳過、`target_rank` 記錄正確。

**驗收：** 用 `scripts/inspect_stage4_input_symbols.py` 對 46 票跑一次，實際選到的目標分布與第 2.2 節模擬的 43/46 一致。

### 階段 3：prompt 與生成路徑

- `OllamaClient` 新增純文字生成方法（現有 `generate()` 強制 JSON、`generate_fim()` 走 FIM，兩者都不適用）：
  ```python
  def generate_text(self, prompt: str, *, temperature: float, num_predict: int,
                    stop_sequences: tuple[str, ...] | None = None) -> str
  ```
- prompt 模板存成版本化檔案 `configs/fault_localization/stage4_patch_prompt_v1.md`，內容包含：錯誤描述、目標符號完整原始碼、檔案上下文（`slice_prefix_suffix` 的預算內）、SEARCH/REPLACE 格式說明與一個範例、以及「只輸出區塊，不要解釋」的指示
- 模型：`codellama:7b-instruct`（這條路是對話式生成，**不是** FIM，所以用 instruct 變體；`codellama:7b-code` 留給 FIM 路徑）

**測試：** 用假 client 驗證 prompt 內含錯誤描述與目標原始碼、且**不含**任何正解欄位。

**驗收：** 對 1 張真實票跑一次，肉眼確認 prompt 內容合理、模型輸出至少是 SEARCH/REPLACE 的形狀。

### 階段 4：重試迴圈與批次整合

- 把第 4 節的迴圈接進 `generate_patch_candidates()`
- 摘要輸出加：目標選取分布（rank 1 / rank>1 / 無目標）、每種失敗原因的次數、重試成功率

**驗收：** 假 client 的測試涵蓋「第一次失敗第二次成功」「三次都失敗」兩條路徑。

### 階段 5：真實資料分階段執行

依計畫書第 11.3 節：**1 張 → 5 張 → 10 張 → 46 張**，每階段看完數字再往下。

每階段要看的：Syntax Valid Rate、Apply Rate（嚴格版與放寬版分開）、失敗原因分佈、平均重試次數。

### 階段 6：接上執行層級驗證

目前的驗證只到「補丁格式正確」，**不能說明補丁有沒有真的修好 bug**。組員那邊已有可運作的 `RegressionTester`（套用 → 重現測試 → 回歸測試 → RIPR 四項判定），且已在合成案例上跑通。

這一步是 WP4 的範圍，但**必須在宣稱任何「補丁成功率」之前完成**——在此之前所有數字都只是 Apply Rate，不是修復率。

---

## 7. 與組員架構的接合點

組員的 `bug_tracking_llm_system` orchestrator 已有 `PatchGenerator` 與 `RegressionTester`，並在合成案例上端對端跑通（生成 → 套用 → 重現 → 回歸 → RIPR，`success: True`）。

**決定接法的關鍵問題：`PatchGenerator.generate()` 產出的是什麼格式？**

- **產 unified diff 或局部編輯** → 它結構上已避開本文件第 0 節的問題。**改為以它當生成主體**，本文件的第 2、3 節（目標選取 + 邊界解析 + 正解隔離）接到它前面當輸入層，第 6 節階段 1 可省略。
- **產整段函式或整個檔案** → 它會撞到完全相同的牆，只是還沒在真實資料上試過。兩邊都照本文件改成局部編輯。

**不論答案為何，以下三件事都要從本文件接過去**（與生成方式無關）：

1. `resolve_symbol_line_range()` — 否則 chunk 邊界會造成系統性假失敗
2. 依目標大小計算生成長度上限（`resolve_num_predict()`）— 寫死的上限會截斷大目標
3. `TICKET_GROUND_TRUTH_FIELDS` 正解隔離

**建議的決定性實驗**：把組員現有的 smoke 流程接到 46 票裡的 **5 張真實票**（不要用合成案例），輸入用 `b1_coverage_aware_v1_predictions.jsonl`，取檔用 `repo_snapshot`，邊界先用 `resolve_symbol_line_range()` 修正。這是目前最便宜且最有決定性的比較，跑完才知道該以誰的生成路徑為主。

---

## 8. 驗收條件

| 項目 | 條件 |
|---|---|
| 階段 1–4 | 對應單元測試全過，全套測試無退步（目前 337 個） |
| 階段 5 | 1 → 5 → 10 → 46 四階段完成，每階段有 Apply Rate 與失敗原因分佈 |
| 報告 | 嚴格版與放寬版 Apply Rate **並列**，明說大小上限與選取規則 |
| G2 門檻 | 計畫書第 10 節：conditional Patch Apply Rate ≥ 80%。未達成時檢視編輯格式與目標選取，**不得**改用更寬鬆的成功定義湊數字 |
| 修復率宣稱 | 在階段 6（執行層級驗證）完成前，一律只能稱 Apply Rate，不得稱修復率或成功率 |

---

## 9. 不要重蹈的覆轍

這些都是實際踩過的，記在這裡避免重複：

1. **不要信任 Stage-3 的行號範圍** — 是 chunk 邊界。一律用 `resolve_symbol_line_range()` 重新解析。
2. **不要用寫死的生成長度上限** — 依目標大小計算。
3. **不要只檢查語法** — 語法合法但目標符號被刪除的補丁會通過檢查。
4. **不要在解析或比對失敗時「盡力而為」** — 找不到 SEARCH 就拒絕，別模糊比對；解析不出邊界就跳過，別退回用 chunk 範圍。假成功比失敗更難發現。
5. **不要把 ticket 物件整包送進 prompt** — 它含 developer patch。
6. **不要一次跑完 46 票才看結果** — 1 張就能發現的問題，跑 46 張只是浪費時間。
7. **不要在沒有執行層級驗證前宣稱修復率** — Apply Rate 不是修復率。

---

## 10. 兩條分支怎麼合併

### 10.1 目前狀況（2026-09-12 實測）

| 項目 | 值 |
|---|---|
| 共同祖先 | `66e0350` |
| `main`（組員）領先 | 4 個提交，最新 `e4e699c` |
| `stage3-wp4-symbol-llm-pilot`（本分支）領先 | 1 個提交 `cd3f450` |
| 兩邊都改到的檔案 | 只有 `README.md`、`tests/test_fault_localization.py` |

**實測結果：合併零衝突。** 驗證方式不只看 git 是否報衝突，而是把合併後的 tree 實體化出來跑完整測試：

- `git merge-tree` 試算：無衝突
- 測試方法同名檢查：無重複（main 新增 3 個 `test_bug_localizer_*`，本分支新增 19 個 `test_generate_fim_*` / `test_symbol_gate_*` / `test_confidence_gate_*`）
- **合併後的完整測試套件：340 個全過**（337 + 3）
- `README.md`：458 + 66 + 11 = 535 行，兩邊新增內容都完整保留

兩邊碰的是不同區域：組員動 `src/modules/bug_localizer.py`（Stage-3 接線）與 `reports/`，本分支動 `src/utils/`（patch_generation / repo_snapshot / llm_client）與 `scripts/`。

### 10.2 合併步驟

先把 `main` 合進本分支（而不是反過來），確認無誤後再回推：

```powershell
git fetch origin
git merge origin/main            # 預期：Merge made by the 'ort' strategy，無衝突
python -m pytest -q              # 預期：340 passed
git push origin stage3-wp4-symbol-llm-pilot
```

如果 `git merge` 意外報衝突（代表期間又有新提交），**不要用 `--force` 或 `checkout --theirs` 硬解**。衝突只會落在 `README.md` 或 `tests/test_fault_localization.py`，兩者都是「雙方各自新增內容」的性質，正確解法是**兩邊的內容都保留**，然後重跑測試確認。

回推到 `main` 前務必先在本分支合併並測過，不要直接 `git push origin HEAD:main`。

### 10.3 程式碼層面怎麼整合

合併乾淨只代表**檔案不打架**，不代表兩套 WP2 實作已經整合。實際整合順序：

**第一步（無爭議，先做）：把與生成方式無關的元件接上組員的路徑。**

不論第 7 節那個問題的答案是什麼，這三件事都要接過去：

1. `resolve_symbol_line_range()` — 否則 chunk 邊界造成系統性假失敗
2. `resolve_num_predict()` 或等效的動態長度上限
3. `TICKET_GROUND_TRUTH_FIELDS` 正解隔離

這一步不需要等任何決策，且對雙方都是淨增益。

**第二步：回答「`PatchGenerator.generate()` 產出什麼格式」。**

這個答案決定生成主體用誰的（見第 7 節）。在答案出來前，不要兩邊同時往下寫生成邏輯——那正是目前重工的原因。

**第三步：把組員的 `PatchGenerator` / `RegressionTester` 移進本 repo。**

目前它們在 `D:/bug-llm-project/bug_tracking_llm_system/`，`scripts/run_real_patch_generation_smoke.py` 第 14 行寫死這個絕對路徑。**這在任何其他機器上都跑不起來，包括助教或審查者的機器。**

對一個要求可重現的專題，這是必須解決的問題，建議二選一：

- 把 `PatchGenerator`、`RegressionTester` 與其相依搬進 `src/modules/` 或 `src/utils/`
- 或將該系統包成可安裝套件，在 `requirements.txt` 宣告版本，用 import 而非硬路徑

在此之前，組員的 smoke 結果**無法被獨立重現**，不適合寫進正式報告。

### 10.4 建議的分工

避免第二次重工，建議按「誰已經有可運作的東西」切：

| 區塊 | 建議負責 | 理由 |
|---|---|---|
| 輸入層（repo 快照、邊界解析、目標選取、大小診斷）| 本分支 | 已對真實 46 票驗證過 |
| 補丁生成（編輯格式、prompt、重試）| 依第 7 節答案決定 | 兩邊都有實作，不該再平行開發 |
| 執行層級驗證（套用→重現→回歸→RIPR）| 組員 | 已在合成案例跑通，本分支沒有 |
| 正解隔離 | 兩邊已有共識 | 各自實作已一致，合併時統一成一份 |
| 報告與指標定義 | 共同 | 雙軌回報規則（第 2.3 節）需雙方都遵守 |

**交接時要明確約定的一件事**：Apply Rate 與修復率是不同的東西。在第 6 節階段 6 完成前，任何一方都不得在簡報或報告中把 Apply Rate 寫成修復率或成功率。
