# Stage-4 WP2 交接筆記：在真實 46 票上跑補丁生成得到的三個發現

日期：2026-09-12
分支：`stage3-wp4-symbol-llm-pilot`（commit `cd3f450`）
對象：接手或平行開發 WP2 補丁生成的人

這份筆記記錄在**真實的 46 票 SWE-bench pilot 資料**上執行補丁生成時撞到的三個問題。這三個都跟生成模型或 prompt 無關，是**輸入資料與參數設定層級**的問題，所以不論補丁生成採用哪種架構（FIM、chat prompt 產 diff、或串接 `bug_tracking_llm_system` 的 `PatchGenerator`）都會踩到。完整脈絡見 `STAGE4_PATCH_GENERATION_IMPLEMENTATION_PLAN_ZH.md` 第 16–18 節。

---

## 發現一：`stage3_ranked_symbols[*].end_line` 是 chunk 邊界，不是定義邊界

**這是最重要的一個，任何用 Stage-3 輸出當 handoff 的人都會踩到。**

Stage-1 的程式碼索引以固定大小（本專案 80 行）切 chunk。`stage3_ranked_symbols` 裡的 `symbol_kind`、`symbol_qualified_name` 是正確的，但 `end_line` 取的是**該 chunk 的結尾**——任何超過一個 chunk 的定義都會被回報成截斷的範圍。

實測（`astropy__astropy-13073`，`astropy/io/ascii/ui.py`，base commit `43ee5806`）：

| | 行號 | 行數 |
|---|---|---|
| Stage-3 回報的 `read` | 252–331 | 80（剛好等於 chunk 大小）|
| 真實的 `def read` | 252–388 | **137** |

起點正確，結尾少了 57 行，落在函式主體中間。

**後果**：拿這個範圍當補丁替換區間，等於「用生成內容取代函式的前 80 行，後面 57 行舊的函式主體原封不動留在那裡」。沒有任何補丁能滿足這個條件，而失敗會被記成 `syntax_error`——**看起來像模型能力不足，其實是輸入邊界錯誤**。

**解法**（已實作在 `src/utils/patch_generation.py`）：

```python
from utils.patch_generation import resolve_symbol_line_range

resolved = resolve_symbol_line_range(
    file_text,                                    # base_commit 的完整檔案內容
    symbol_qualified_name=cand["symbol_qualified_name"],
    symbol_name=cand["symbol_name"],
    hint_start_line=cand["start_line"],           # Stage-3 的 chunk 範圍
    hint_end_line=cand["end_line"],               # 只當「在哪附近」的線索
)
if not resolved.resolved:
    skip(resolved.reason)      # 絕不退回使用 chunk 範圍
```

用 Stage-3 給的**名稱**去真實原始碼以 AST 解析出真正的定義邊界（含裝飾器）；chunk 範圍只用於同名符號的消歧義（取重疊度最高者）。同名方法出現在多個類別時也能正確區分。解析失敗時回傳 `resolved=False`，呼叫端必須跳過而不是用錯誤的邊界硬幹。

這個函式跟補丁生成方式完全無關，可以直接拿去用。

---

## 發現二：目標大小分布決定了 granularity 能不能用「整個符號」

用 `scripts/inspect_stage4_input_symbols.py` 量測 46 票 top-1 候選的**真實定義大小**（不是 Stage-3 那個被 chunk 截斷的數字）：

| 目標大小 | 票數 | 佔比 |
|---|---|---|
| ≤20 行 | 15 | 33.3% |
| 21–50 行 | 7 | 15.6% |
| 51–100 行 | 9 | 20.0% |
| **>100 行** | **14** | **31.1%** |

中位數 52 行，**最大 6470 行**。46 張票中有 **17 張的 top-1 是整個 class**：

```
6470 行  pydata__xarray-4940        (Dataset)
5942 行  pydata__xarray-4184        (Dataset)
1650 行  pylint-dev__pylint-6357    (PyLinter)
1016 行  pylint-dev__pylint-7097    (PyLinter)
 869 行  matplotlib__matplotlib-25281 (Legend)
```

**結論：如果補丁生成的輸出是「整個符號的新版本」，輸出長度就正比於符號大小，這批資料上不可能有好結果。** 要求模型重寫整個 6470 行的 `Dataset` 類別，不只做不到，語意上也不是一個合理的「補丁」——真實的修正是改某個方法裡的幾行。

**如果輸出是 unified diff / hunk，輸出長度正比於「修改量」而非「符號大小」，就結構性地避開了這個問題。** 這是兩種架構最關鍵的差異。

已驗證的補救方向（模擬過，尚未實作）：沿著 Stage-3 **自身排名**往下取第一個大小在上限內的候選。每張票有 2–5 個可解析候選，所以 top-1 是大類別時，後面常有該類別內的小方法：

| 大小上限 | 有可行目標 | 用 rank 1 | 用 rank>1 |
|---|---|---|---|
| 30 行 | 40 (87.0%) | 17 | 23 |
| 50 行 | 43 (93.5%) | 22 | 21 |
| 100 行 | 46 (100%) | 31 | 15 |

**但這有方法論代價**：系統性改挑較小的候選，等於用「生成可行性」換「補到正確位置的機率」，會壓低 Correct Patch Rate。若採用，必須記錄實際使用的 rank，並在報告中同時給出「僅 rank-1」與「排名最高且符合上限」兩個數字，明說篩選規則。

---

## 發現三：生成長度上限必須依目標大小計算，不能寫死

原本沿用手動測試的 `num_predict=256`。上面那個 137 行的目標約需 **825 tokens**，等於模型只拿到所需額度的 **31%**——每次生成都被硬切在句子中間（斷在 `except Exception as err:`、`If the ``format`` is not given then the` 這種地方），一樣被記成 `syntax_error`。

解法在 `utils.patch_generation.resolve_num_predict()`：以「被替換符號的估計 token 數 × headroom(2.0)」計算，並夾在 `[min, max]` 之間。同一個目標的額度從 256 變成 1652。

如果你那邊的生成是產 diff，這點的影響會小很多，但仍需確認上限足夠容納最大的 hunk。

---

## 一個我們獨立得到相同結論的地方

你在 `FL_WP2_READINESS_AUDIT_20260910_ZH.md` 第 5 節寫的：

> `PatchGenerator._first_patch` 會直接接受 ticket 的 `patch`。Stage-3 gold source 含 developer patch，絕不能把該完整物件直接送生成端；使用輸入白名單。

這邊也獨立踩到同一個風險並已用程式強制隔離（`scripts/generate_stage4_patches.py` 的 `TICKET_DESCRIPTION_FIELDS` / `TICKET_GROUND_TRUTH_FIELDS`），加了端對端測試驗證 prompt 內不含正解。

`data/fault_localization/swebench_full/stage3_symbol_gold/development_source_tickets.jsonl` 這個檔案（帶 `bug_report`，適合當 prompt 的錯誤描述來源）**同時含有 `patch`、`fail_to_pass`、`pass_to_pass`、`hints_text`**。這類洩漏最危險的地方是它會讓數字變**好看**，不會讓程式報錯。

---

## 想跟你確認的一件事

**`PatchGenerator.generate()` 產出的是 unified diff／hunk，還是整段函式／整個檔案？**

這個答案決定兩套架構怎麼合：

- **產 diff** → 結構上避開了發現二的問題，建議以你這套為生成主體，這邊把輸入層（發現一的邊界解析、大小診斷）接過去。
- **產整段函式／檔案** → 會撞到跟這邊完全一樣的牆，只是還沒在真實資料上試過。那兩邊都需要改 granularity。

---

## 建議的決定性測試

你那支 `run_real_patch_generation_smoke.py` 目前跑的是暫存目錄裡現建的 2 行 `normalize_username`。它證明了管線接得通（生成→套用→重現測試→回歸→RIPR），這塊是這邊沒有的。

**建議把同一個流程接到 46 票裡的 5 張真實票上跑一次。** 這是目前最便宜也最有決定性的實驗：

- 真實票的輸入可用 `reports/fault_localization/stage3_source_neighborhood_dev_v1/b1_coverage_aware_v1_predictions.jsonl`（含 `ticket_id`／`repo`／`base_commit`／`stage3_ranked_symbols`）
- repo 快照可用 `src/utils/repo_snapshot.py`（依 `repo` + `base_commit` 取出唯讀 checkout 並讀檔）
- 記得先用發現一的 `resolve_symbol_line_range()` 修正邊界，否則會得到跟這邊一樣的假失敗

跑得動 → 以你的架構往下走；跑不動 → 兩邊都要改 granularity，但至少我們會知道問題出在哪一層。

---

## 順帶修掉的環境問題（已在本分支）

- `scripts/prefetch_swebench_repositories.py` 與 `run_swebench_lite_fault_localization.py` 呼叫 git 時未指定編碼，在繁體中文 Windows（cp950）上遇到 git 的 UTF-8 輸出會直接 `UnicodeDecodeError` 當機。
- 同一支腳本判斷 repo 是否已初始化只看 `.git` 是否存在；上述當機若發生在 `git init` 與 `git remote add` 之間，12 個 repo 會全部永久卡在「有 `.git` 但無 `origin`」，`--resume` 也救不回來。已改為每次執行都確保 origin 正確。
- `pyproject.toml` 加了 `testpaths = ["tests"]`，避免 pytest 掃到專案根目錄下的非測試資料夾而與 `tests/` 同名檔案衝突。

全套測試 337 個通過。
