# 第三階段（Symbol 定位）WP1～WP4 進度報告

- 報告日期：2026-09-08
- 適用範圍：Fault Localization 專題第三階段（函式／方法／類別層級錯誤定位）
- 對應文件：`STAGE3_SYMBOL_RERANKER_IMPLEMENTATION_PLAN_ZH.md`（完整計畫與逐日更新）

## 一、背景：第一、二階段現況（銜接用，非本次重點）

- **第一階段（檔案定位）已完成**，正式採用 E8-A：TF-IDF 固定 50 候選 → SBERT 語意重排 → Symbol/API 擴充 → Call Graph Top-3 → 輸出 Top-20 唯一檔案。準確率基準 E6：Validation Recall@20 85.92%，Final Holdout Recall@20 67.17%（跨 repository 泛化仍是已知限制）。
- **第二階段（檔案排序）已完成，正式決定不採用 LLM**：`codellama:7b-instruct` File Reranker 在 10 張票配對比較中，File Hit@1/3/5 與 MRR 均比 retrieval baseline 低 0.1；正式流程維持 retrieval baseline Top-5，7B reranker 只保留為實驗選項。
- **第三階段（函式層級定位）是本報告主題**，目標是在 Stage-2 Top-5 檔案中，把最可能出錯的函式／方法／類別排到前幾名。

## 二、WP1：Symbol 資料契約與 AST 正確性 — 已完成

**目標：** 建立可信賴的 symbol schema，讓後續 gold 標註與評估有穩定的識別基礎。

**完成內容：**
- `SymbolRecordV1`、`SymbolParseResult v2`、`CodeIndex v5`：完整 scope stack、stable ID（sha256）、column range、commit provenance、multiline signature。
- 明確區分 diagnostics：`SyntaxError`、`RecursionError`、`no_symbols`、`unsupported`、`missing_file`、`invalid_path`、`symlink_escape`，避免「parse 失敗」與「合法無 symbol」被誤判為同一種情況。
- 舊 API（`_python_symbol_ranges` 等）保留相容 wrapper，不影響既有呼叫端。

**驗收結果：** 完整回歸 161/161 通過。

## 三、WP2：Symbol Gold 與 Evaluator — 已完成（G1 通過）

**目標：** 建立可信的 ground truth 與 file-qualified 評估邏輯。

**完成內容：**
- Gold 建置：固定種子 61 筆 development tickets、12 個 repositories，61/61 base commits 可讀。共產生 207 筆 Symbol Gold（205 mapped、2 明確排除，不硬猜）。
- 品質稽核：固定種子抽樣 50 筆，涵蓋 12 repositories、nested symbol 23、`<module>` 10、純新增 12、刪除證據 28、多檔修改 23。逐筆對照 developer patch、base-commit source、獨立 AST scope，**exact 50/50（100%）、provenance 50/50（100%）**，達到 G1 門檻（≥95% exact、100% provenance）。
- Evaluator：`SymbolEvaluationItemV1` 採 ID-first、否則 file-qualified `(file_path, symbol_kind, qualified_name)` exact match；relaxed match（qualified name / suffix / leaf）僅作診斷用途，不算正式成果。支援多 gold 聚合、missing prediction 保留在分母、conditional 分母、paired outcomes 與 bootstrap 95% CI。

**驗收結果：** 完整回歸 170/170 通過。

## 四、WP3：Deterministic Candidate Baseline — 進行中（G2 未通過）

**目標：** 在不使用 LLM 的情況下，把正確 symbol 穩定地排進 Top-30 候選池，作為後續 LLM 比較的地基。G2 門檻：Conditional Exact Candidate Recall@30 ≥ 90%。

**已測試的變體（development set，61 筆中 46 筆為 Stage-2 conditional-eligible）：**

| 變體 | 說明 | Conditional Exact Candidate Recall@30 | 是否採用 |
|---|---|---:|---|
| B0 TF-IDF | 純 TF-IDF baseline | 60.60% | 否，作為最低基準 |
| B1 全域 structured evidence | identifier/stack trace/lexical/Stage-2 file score 綜合 | 64.36% | 否 |
| B1 + per-file quota 4/6/8 | 限制單檔案候選數 | 61.34% / 53.35% / 56.24% | 否，均更差 |
| B1 module-reserved | 為每個 Stage-2 檔案保留一個 `<module>` 候選 | — | 併入 coverage-aware-v1 設計 |
| **coverage-aware-v1** | 保留強 global prefix＋每檔案一個 module 候選＋class family 成員補位 | **68.64%（選定 baseline）** | **是** |
| source-neighborhood-v1 | 同檔最近定義擴展（≤5 名額、≤100 行） | 64.70% | 否，找回 1 個 miss 但失去 7 個既有命中 |
| call-neighborhood-v1 | 重建呼叫圖做一跳擴展 | 66.02% | 否，找回 2 個 miss 但失去 6 個既有命中 |
| call-neighborhood-v2 | 改用 index 既有 repository-level 呼叫圖＋candidate 過濾 | 68.20% | 否，找回 4 個 miss 但失去 5 個既有命中，仍低於 coverage-aware-v1 |

**關鍵發現：** AST candidate pool 的 exact oracle（理論上限）達 90.41%，代表正確答案大多「存在」於可索引範圍內，但目前的 deterministic 排序規則只能穩定排進 Top-30 的 68.64%。三次以「擴大鄰域／補呼叫邊」為方向的嘗試，全部低於已選定的 coverage-aware-v1，且都是「找回的少、失去的多」，顯示這個方向已接近報酬遞減。

**驗收結果：** 完整回歸最終為 188/188 通過（隨每次實驗遞增）。**G2 尚未通過**（68.64% < 90%）。

## 五、關鍵決策點：2026-09-08，帶著限制推進 WP4

**背景：** 三次針對候選池的消融嘗試（source-neighborhood、call-neighborhood v1/v2）都沒能超過 coverage-aware-v1，顯示短期內用同類型規則微調不太可能把 68.64% 拉到 90% 的 G2 門檻。同時，專題排程規定第三階段（連同補丁生成與驗證）僅到 115 年 12 月，後續還有提交訊息生成、系統測試與優化要在 116 年 2 月前完成。

**決策：** 比照 Stage 1 當初處理 Final Holdout Recall@20 只有 67.17% 的做法，**不把 G2 當成不可逾越的硬性阻擋**，而是將 68.64% 明確記錄為已知限制，先啟動 WP4 Pilot，取得 Symbol LLM 排序的真實可行性數據，再決定後續。這不是撤銷 G2 的正式定義，最終正式採用仍需完整跑過 G4／G5 驗證。

## 六、WP4：Code Llama Symbol Reranker Pilot — 已完成一輪，建議不採用

**與既有雛形的差異（修正已知設計問題）：**

舊有的 `--symbol-llm-rerank` 雛形把 Top-30 拆成每批 5 個分批呼叫、用同批本地排名當 ID，且跨批分數直接混合排序——這是計畫書已指出、尚未修正的已知問題。WP4 Pilot 新增獨立腳本（不修改既有雛形，避免影響其既有測試），改良為：

- 直接沿用 WP3 已凍結的 `b1_coverage_aware_v1` Top-30 pool，不重算 retrieval。
- 從 Top-30 取 Top-10 shortlist，**單一 Ollama 呼叫**完成排序，不分批。
- candidate_id 改為**洗牌過的 opaque ID**（`C1`～`C10`，固定種子重新排列，不等於原始 rank），prompt 只含 file_path、symbol_kind、qualified_name、行號與程式碼片段，不含 retrieval score、Stage-2 file score 或原始 rank，避免分數洩漏。
- 缺一筆、重複 ID、未知 ID、NaN／超界分數、非 JSON，一律視為整票 LLM failure，清楚回退到 deterministic baseline 順序。

**新增產物：**
- `scripts/run_stage3_wp4_symbol_llm_pilot.py`（主程式）
- `scripts/analyze_stage3_wp4_pilot.py`（配對統計與 bootstrap 95% CI 分析）
- `tests/test_stage3_wp4_symbol_llm_pilot.py`（16 個單元／整合測試）
- 完整回歸：**204/204 通過**（188 既有＋16 新增）；開發過程中測試曾抓到一個真實 bug（fallback 誤用洗牌後順序而非正確 baseline 順序），已修正。

**執行結果（使用者本機真實 `codellama:7b-instruct`，Ollama）：**

依計畫書 10.3 節順序執行：1 票 smoke → 10 票 smoke → 46 票（全部 Stage-2 conditional-eligible development tickets）正式 pilot。

*可靠度（G3 門檻：valid coverage ≥95%、fallback ≤5%）*

`llm_valid_count = 42/46`，fallback = 4/46 = **8.70%**，略高於 G3 門檻（≤5%）。四筆 fallback（`invalid_or_incomplete_output`）：`pallets__flask-4544`、`pytest-dev__pytest-10893`、`scikit-learn__scikit-learn-11042`、`sympy__sympy-13177`。

*準確率（Exact Hit@K，baseline = B1 coverage-aware-v1 deterministic Top-5，LLM = WP4 單次 Top-10 shortlist rerank，2,000 次 resample 固定種子 42 的 bootstrap）*

| K | Baseline | LLM | Mean Δ | 95% CI | 判讀 |
|---|---:|---:|---:|---:|---|
| 1 | 26.09% | 10.87% | -15.22 pp | [-28.26, -2.17] pp | **CI 不含 0，LLM 顯著更差** |
| 3 | 47.83% | 41.30% | -6.52 pp | [-21.74, +8.70] pp | 方向為負，CI 含 0，不顯著 |
| 5 | 60.87% | 58.70% | -2.17 pp | [-15.22, +10.87] pp | 方向為負，CI 含 0，不顯著 |

逐票配對結果（improved／unchanged-hit／worsened／both-miss）：Hit@1 為 2／3／9／32；Hit@3 為 5／14／8／19；Hit@5 為 4／23／5／14。三個 K 值全部呈現「worsened 多於 improved」。

## 七、正式建議

**Symbol LLM Reranker（`codellama:7b-instruct`）不採用；Stage 3 正式輸出維持 B1 deterministic baseline（coverage-aware-v1）。**

依 G5 判準（LLM 點估計需高於 B1 且 95% CI 下界不低於 0），本輪 pilot 明確不通過；Hit@1 甚至是統計上顯著更差。這個結論與第二階段對 File Reranker 的決定完全一致：**兩個獨立階段（檔案層級、函式層級）都證明現有 7B 模型的排序能力補不上規則式方法**，這本身是一個站得住腳、可以直接對外報告的研究發現。

## 八、限制（報告時應一併陳述）

1. WP3 的 G2 門檻（Conditional Exact Candidate Recall@30 ≥90%）**尚未通過**（68.64%），本報告的 WP4 結果是在此已知限制下取得，只能回答「在目前候選池品質下 LLM 排序是否有幫助」，不能回答「LLM 排序能力本身的上限」。
2. WP4 pilot 樣本為 46 筆 development-only tickets、12 個 repositories，未達計畫書 G4 門檻（≥200 tickets、獨立 repo-disjoint holdout），屬 pilot／exploratory 等級，非正式 G4 驗證。
3. 4 筆 fallback 尚未逐筆歸因具體違反 schema 的原因。
4. G3 可靠度門檻（fallback ≤5%）以 8.70% 些微未達標，若要精確判斷是否可透過 prompt 調整過關，需要更多樣本或逐筆檢視原始回應。

## 九、後續工作建議

1. 若要繼續衝 WP3 的 G2 門檻，建議换一個量級不同的候選生成方式（例如語意相似度輔助，而非持續在「圖擴展／鄰域規則」這個已報酬遞減的方向微調）。
2. 若接受目前候選池上限，第三階段可正式定案為「deterministic B1 baseline，LLM 保留為未通過驗證的實驗選項」，比照第二階段的處理方式，將心力轉往計畫書後續步驟（補丁生成、測試案例生成、提交訊息生成）。
3. 若要精確診斷 4 筆 fallback 的成因，可保留原始 LLM 回應內容供逐筆檢視。

## 十、主要產物索引

- 計畫與逐日進度：`STAGE3_SYMBOL_RERANKER_IMPLEMENTATION_PLAN_ZH.md`（第 15～17 節為近期更新）
- WP3 凍結結果：`reports/fault_localization/stage3_deterministic_g2_dev_v1/`
- WP3 消融實驗：`reports/fault_localization/stage3_source_neighborhood_dev_v1/`、`stage3_call_neighborhood_dev_v1/`、`stage3_call_neighborhood_dev_v2/`
- WP4 Pilot 程式：`scripts/run_stage3_wp4_symbol_llm_pilot.py`、`scripts/analyze_stage3_wp4_pilot.py`
- WP4 Pilot 測試：`tests/test_stage3_wp4_symbol_llm_pilot.py`
- WP4 Pilot 原始結果：`reports/fault_localization/stage3_wp4_pilot/pilot_46tickets.jsonl`、`pilot_46tickets_summary.json`、`pilot_46tickets_analysis.json`
