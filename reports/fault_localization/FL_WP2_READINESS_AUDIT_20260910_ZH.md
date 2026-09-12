# Fault Localization／WP2／Patch Generation 檢查

檢查日期：2026-09-10。以目前工作目錄程式、原始資料 schema、既有實驗產物為主，另唯讀檢查相鄰 ToJson 與 bug_tracking_llm_system。沒有修改演算法、既有 gold 或凍結實驗。附圖為待核對進度說明。

## 1. 功能完成度

**定位核心可運作；研究品質驗收及最新版本的補丁端到端串接尚未完成。** 不建議以沒有分母的百分比表示工程完成度。

- 已實作 bug report／錯誤訊息／stack trace 證據、repository 索引、檔案排序、Python AST symbol 與行號、Top-20 files、Stage-2 Top-5、Stage-3 最多 30 候選與 Top-5、JSON 輸出、信心與人工檢查旗標、LLM 失敗回退。
- 本次使用 `.venv-e7/Scripts/python.exe -m unittest discover -s tests -v`：204/204 通過（3.889 秒），紀錄在 `tmp/fl_audit_tests_20260910.log`。shell 沒有全域 python，但專案虛擬環境可用。這是工程回歸，沒有重跑大型 benchmark、Ollama 或真實補丁驗證。
- 既有 Stage-3 development 61 票、46 票符合 Stage-2 條件；選定 coverage-aware-v1 的 Conditional Exact Candidate Recall@30 為 68.64%，低於 90% 研究門檻。不是全流程成功率。
- 9/10 新實驗同樣 46 票：固定規則 Hit@5 28/46（60.87%），Code Llama 看最多 30 候選後 17/46（36.96%）。兩輪使用同一批票，不可加總樣本數。保留固定規則足以開始功能整合，不必先最佳化效能或再調模型。
- Python 有 AST；其他語言解析仍屬啟發式。新增檔案、module 級變更與跨函式修改需要保留檔案上下文，不能要求所有修復都落在既有函式內。

關鍵接線缺口：`src/modules/bug_localizer.py` 沒有傳入 Stage-3 開關／選定策略；底層預設 `symbol_localization=False`、`symbol_retrieval_mode=b0-tfidf`、`symbol_selection_mode=global`。CLI 支援顯式選擇，不能把一般 wrapper 呼叫當成已使用實驗選定配置。

## 2. WP2 現行定義及評分

- File gold：`scripts/prepare_swebench_lite_fault_localization.py` 從 developer `patch` 解析 `fixed_files`，不把獨立 `test_patch` 當定位答案。不是由 merge 狀態或 CI 結果篩選。
- Symbol gold：`src/utils/symbol_gold.py` 將 patch 的舊版變更行、刪除行、插入錨點等映射到 `base_commit` 的 symbol；保留 patch SHA-256、hunk、old/new 路徑與行號。實際 207 records／61 tickets：205 mapped、2 excluded。
- 既有 50 筆稽核核對 patch、base source 與独立 AST，紀錄 exact/provenance 50/50；它證明位置映射一致，沒有證明 50 個最終 merge commits 的測試皆成功。本次未重跑那份完整稽核。
- File 指標：Top-k/Hit、Candidate Recall@20、MRR。Symbol 正式 evaluator 先比可信 symbol ID，否則比完整 `(file_path, symbol_kind, qualified_name)`；同名／suffix relaxed matching 只作診斷。Hit 是至少一個 gold 命中；Recall 是各票命中 gold 比例的平均；MRR 是第一個命中的倒數排名。
- missing predictions 留在端到端分母；conditional symbol candidate 指標另以 Stage-2 已命中 gold file 的票為分母。排除／不支援映射需另報覆蓋率，不能把 50/50 稽核或 conditional 成績當整體定位準確率。
- 通用 `prepare_fault_localization_gold.py` 只是既有欄位正規化；它不核實 commit／測試，且會移除 file-qualified symbol 字串中的檔案前綴，不應取代 Stage-3 正式 gold/evaluator。

因此現行標籤精確名稱是「developer-patch-derived localization gold」。modified locations 是修復位置的代理標籤，不代表每個被改函式都是唯一根因。教師的新標準還需要 commit 與驗證來源證據。

## 3. 實際資料欄位

| 來源 | 實際可用 | 缺少／不能直接認定 |
|---|---|---|
| SWE-bench Full test，2,294 票；raw train，19,008 票 | repo、instance_id、base_commit、patch、test_patch、FAIL_TO_PASS、PASS_TO_PASS、environment_setup_commit 等 | 沒有 final/merge/fix commit 欄位；沒有逐次測試執行 log／結果欄位。base_commit 是修復前版本，environment_setup_commit 是環境用途 |
| SWE-bench-Live raw verified，500 票 | 另有 pull_number、issue_numbers、commit_url、commit_urls、test_cmds、log_parser；四個 commit_url/commit_urls/pull_number/test_cmds 欄位皆 500/500 非空 | 沒有明確 merged/merge_commit_sha 與測試通過紀錄欄位；不能把列表最後一個 commit 或任一連結直接當最終成功版本 |
| 轉換後 Full gold | fixed_files、base_commit、repo、來源 | 未保存 patch、merge/fix commit、validation provenance；patch 仍可從原 parquet 取回 |
| 轉換後 Live holdout tickets | bug report、repo、base_commit、fail_to_pass、pass_to_pass 等 | 已丟失上述 PR／commit 連結及 test_cmds；應由原始 parquet 補到獨立 evidence manifest |
| ToJson 本地 issues.json，60 筆 | source、issue_id、title、body、direct_fields；後者為 bug_type/component/error_message/os/priority/version | 沒有 commit、modified files、diff、測試驗證欄位 |
| GitBugs | 相鄰 ToJson README 僅列為參考來源；公開資料主要提供 report、分類、狀態與重複關係 | 本次未找到已匯入定位流程的 GitBugs 資料；不能宣稱本地已有 final fix 標註。公开論文 schema 也未建立完整 merge＋測試證據契約 |

FAIL_TO_PASS／PASS_TO_PASS 是 benchmark 測試標籤，可建評分規則，不能冒充本機剛執行成功的測試紀錄。資料集的驗證來源可保留，但須與本次獨立重跑區分。GitBugs 與 GitBug-Actions／GitBug-Java 是不同資料來源。

本地 Live 例：第一列 `commit_url` 指向 pylint tree/c668682...，另有三個 commit_urls 與 PR 9771；僅憑欄位名稱不足以確定最終修復 SHA，本次不對此列作 merge 認證。

外部核對來源：

- [SWE-bench 官方資料卡](https://huggingface.co/datasets/princeton-nlp/SWE-bench/blob/main/README.md)：patch、base_commit、測試標籤定義。
- [GitBugs 作者論文](https://arxiv.org/html/2504.09651v1)：report schema 與研究用途。
- [GitBugs repository](https://github.com/av9ash/gitbugs/)：也連結其他歷史 localization 資料，不能視為目前已匯入且已驗證。

## 4. 下一步最小修改方案

1. 保留現有 gold，新增每票 evidence manifest：repo、issue/PR URL、base_commit、fix_commit、merge_commit_sha、merged_at、patch hash、測試來源/指令/環境/結果/log、驗證時間與 eligibility。無法核實標記 unknown，不硬填成功。
2. 先選 5–10 筆非 sealed holdout 的 SWE-bench development 案例，用 PR 關聯查最終採納版本，核對 patch 與該修復一致。merge SHA 與 PR head/fix SHA 分開記錄；避免直接 diff 任意 merge parent 導入無關修改。多個修復 PR 或後續 revert 必須在固定觀察時間點記錄判定。
3. 在隔離環境重現：修復前相關測試失敗；gold patch 後 FAIL_TO_PASS 通過且 PASS_TO_PASS 不退步。只把 merge 與測試證據完整的票納入新標準主評分，同時報告 eligible/total，避免選樣後隱藏覆蓋損失。定位仍在 base_commit 執行，gold 只供離線評分。
4. 接入選定 Stage-3 設定；以 `stage3_ranked_symbols` 加 Stage-2 檔案為 handoff，攜帶 repo/base_commit、symbol ID、行號、完整函式／必要 module context、信心與失敗狀態。從同一 snapshot 補內容並驗證行號/檔案一致。
5. 跑上述小樣本「定位→模型生成 diff→套用→重現測試→回歸測試」，記錄每階段失敗及端到端成功率。生成結果依測試評分，不以是否逐字等於 developer diff 判定。

## 5. Patch Generation 是否可以開始

**可以開始受控整合，但尚不能宣稱最新定位已接通且完成自動修復驗證。**

目前 workspace 是定位子專案。相鄰完整系統已有 `PatchGenerator`、`RegressionTester`、orchestrator 的 patch/test 骨架，可重用；不是要從零重寫。唯讀程式檢查顯示：

- 完整系統預設建構 `PatchGenerator(prompt_path=...)`，未傳 llm_client；沒有提供 patch 時會回傳人工指引，不會自動產生真正補丁。
- `_localization_context` 讀舊 `localized_candidates/localized_files/candidates`，沒有直接消費最新 `stage3_ranked_symbols`。
- 現有 WP4 輸入每個片段上限 1,200 字元，報告記錄 18 個 module 候選片段為空；不適合原樣當完整修補上下文。
- `PatchGenerator._first_patch` 會直接接受 ticket 的 `patch`。Stage-3 gold source 含 developer patch，絕不能把該完整物件直接送生成端；使用輸入白名單，將 patch、test_patch、測試答案與 fix metadata 留在 evaluator/validator。
- RegressionTester 已能在暫存副本套用與跑測試，但此次未驗證它與新 Stage-3 的端到端運作，未配置／未跑測試不能算 passed；既有信心門檻也不等於補丁正確性保證。

簡報 WP2 狀態建議改為：「位置 gold 與評分工具已完成；最終 merge commit 與測試通過證據待補。」WP4 更新為同一批 46 票的兩輪比較，固定規則仍保留。當前優先事項是接線與成功／失敗可驗證性，不是效能最佳化。
