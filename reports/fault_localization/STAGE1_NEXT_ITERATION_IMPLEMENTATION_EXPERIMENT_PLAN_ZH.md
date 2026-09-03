# 第一階段錯誤定位：下一版實作與實驗計劃書

- 文件版本：v1.1
- 建立日期：2026-08-17
- 更新日期：2026-09-02
- 適用範圍：第一階段 Top-20 候選檔案檢索
- 目前狀態：E0～E8皆已完成；專題正式採用「E8實作＋E6準確率基準」
- 正式決策：E8保留E6的固定50候選、SBERT、Symbol／API與Call Graph Top-3排名流程，並新增`.pyi`／`.scala`來源支援；E6的同資料Validation與500筆Final Holdout作為主要準確率證據
- 研究限制：E6僅497／500筆、E8僅98／100筆符合恰好20個唯一候選的固定Top-20契約；兩者使用不同Holdout，因此不得用原始百分比宣稱E8準確率優於E6
- 最終總結：`reports/fault_localization/FINAL_PROJECT_SUMMARY_ZH.md`已分開呈現E6準確率證據、E8工程涵蓋結果、第二階段結果與研究限制

## 一、計劃目的

本計劃的目標，是在目前 **TF-IDF Top-50＋SBERT Reranker** 的基礎上，依序實作與驗證下列五項改進：

1. 分析完全未命中與部分命中案例。
2. 改進同一檔案內多個程式碼區塊的分數整合。
3. 加入檔案之間的 Import Graph。
4. 加入「功能名稱到真正實作位置」的候選擴充。
5. 最後測試 Call Graph 與 Repository 大小調整。

本計劃只處理「錯誤定位」第一階段，不包含部署、函式層級定位、程式碼修正或補丁產生。

## 二、目前基準

### 2.1 正式方法

```text
Ticket
  → TF-IDF 初步檢索 50 個候選檔案
  → SBERT 語意重新排序
  → 輸出 20 個不重複的候選檔案路徑
```

正式方法設定：

- TF-IDF負責初步縮小搜尋範圍。
- SBERT模型為`sentence-transformers/all-MiniLM-L6-v2`。
- SBERT重新排序的候選檔案數為50。
- Domain/path routing關閉。
- 正式輸出固定為20個不重複的檔案路徑。

### 2.2 可比較的Validation基準

後續所有改進先與相同的Validation 500筆基準比較：

| 指標 | 目前基準 |
|---|---:|
| Hit@20 | 89.80% |
| Recall@20 | 82.98% |
| Top-1 | 56.20% |
| MRR@20 | 0.6597 |
| 完全未命中 | 51筆 |

### 2.3 已完成的Frozen Holdout結果

| 指標 | v1正式結果 |
|---|---:|
| Hit@20 | 93.00% |
| Recall@20 | 84.47% |
| Top-1 | 54.80% |
| MRR@20 | 0.6623 |
| 完全／部分／未命中 | 387／78／35筆 |

這組Frozen Holdout結果只代表目前v1方法。因為後續會查看35筆未命中與78筆部分命中案例，這500筆資料不得再用來選擇v2參數，也不得把v2在同一組資料的結果當成新的獨立最終測試。

## 三、實驗規則

### 3.1 資料使用規則

| 資料 | Ticket數 | 下一版用途 |
|---|---:|---|
| Development | 1,294 | 失敗分析、功能開發、權重與參數調整 |
| Validation | 500 | 每個階段的凍結版本比較與方法選擇 |
| 原Frozen Holdout | 500 | 只保留v1正式結果；可做事後說明，不再調整v2 |
| 新Final Holdout | 500 | 已建立且與既有資料的Repository完全不重疊；只供凍結後的一次性最終評估 |

新Final Holdout應優先採用Repository不重疊的資料；若無法取得，報告必須明確寫出它只能測試未見Ticket，不能主張未見Repository泛化。

### 3.2 評估指標

- 主要指標：**Recall@20**，衡量正確修改檔案找回的完整程度。
- 輔助指標：Hit@20、Top-1、MRR@20。
- 錯誤數量：完全未命中、部分命中、完全找回。
- 分組結果：單檔案／多檔案Ticket、各Repository、Repository大小分組。
- 所有方法皆計算10,000次成對bootstrap 95%信賴區間。

### 3.3 保留新方法的最低條件

一項改進只有同時符合下列條件，才加入下一個組合實驗：

1. Validation Recall@20至少提高0.50個百分點。
2. Recall@20成對差異的95%信賴區間下限不小於0。
3. Hit@20下降不得超過0.50個百分點。
4. 500筆皆成功產生結果，每筆恰好20個不重複檔案。
5. 模型執行期間不能讀取Gold檔案、Patch或修正後程式碼。

若只有特定失敗類型改善，但整體信賴區間包含0，先標記為「探索性結果」，不直接納入正式方法。

## 四、實作順序與實驗設計

## 第0階段：分析未命中與部分命中案例

### 執行結果（2026-08-17）

分析程式與正式輸出已建立：

```text
scripts/analyze_stage1_failure_cases.py
scripts/review_stage1_failure_sample.py
reports/fault_localization/stage1_next_iteration/failure_analysis.json
reports/fault_localization/stage1_next_iteration/failure_cases.csv
reports/fault_localization/stage1_next_iteration/failure_analysis_zh.md
reports/fault_localization/stage1_next_iteration/manual_review_sample.csv
reports/fault_localization/stage1_next_iteration/manual_review_completed.csv
reports/fault_localization/stage1_next_iteration/manual_review_summary.json
reports/fault_localization/stage1_next_iteration/manual_review_report_zh.md
```

| 資料組 | 部分命中 | 完全未命中 | 索引範圍問題 | TF-IDF前50遺漏 | 混合問題 | SBERT排出Top-20 |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 73 | 51 | 13 | 61 | 15 | 35 |
| 舊Holdout事後分析 | 78 | 35 | 9 | 44 | 30 | 30 |

Validation的124筆失敗案例中，最大的失敗來源是正確檔案沒有進入TF-IDF前50名；其次是正確檔案已進入前50名，但被SBERT排出Top-20。這表示後續除了測試檔案分數整合，也必須保留Import Graph、API查詢擴充與候選池大小實驗。

已完成30筆分層抽樣案例的人工閱讀與證據核對，30筆分類全部確認，沒有需要修正的案例。抽樣中共有8筆案例涉及Code Index涵蓋問題，對應9個遺漏檔案：8個檔案在base commit尚不存在，可能是修正時新增或改名；1個`setup.cfg`在base commit已存在，但因目前索引只處理支援的程式碼檔案而被排除。

第一筆抽查案例`astropy__astropy-13075`共有2個正確檔案：`astropy/cosmology/io/__init__.py`已排在最終第17名，`astropy/cosmology/io/html.py`則未進入Code Index，且在base commit尚不存在。因此將此案例判定為「部分命中」，失敗環節為「索引涵蓋問題」是合理的；排序模型無法找回修正前版本中不存在的檔案。

### 目標

先確認模型失敗發生在哪一個環節，再決定後續功能的優先度。

### 實作內容

新增：

```text
scripts/analyze_stage1_failure_cases.py
```

輸入資料：

- v1預測結果。
- 對應的Gold檔案路徑。
- TF-IDF Top-50中間候選。
- SBERT重新排序後的Top-20。
- 對應base_commit建立的Code Index。

每筆失敗案例需判定一個主要原因：

| 分類 | 白話說明 |
|---|---|
| Index coverage failure | 正確檔案根本沒有進入程式碼索引 |
| Initial retrieval miss | 正確檔案沒有進入TF-IDF前50名 |
| Reranker demotion | 正確檔案進入前50名，但被SBERT排出前20名 |
| Cross-file partial miss | 找到其中一個正確檔案，但漏掉與它相關的其他檔案 |
| Ambiguous ticket／other | Ticket線索不足，或無法歸入前四類 |

### 產出檔案

```text
reports/fault_localization/stage1_next_iteration/failure_analysis.json
reports/fault_localization/stage1_next_iteration/failure_cases.csv
reports/fault_localization/stage1_next_iteration/failure_analysis_zh.md
```

### 驗收條件

- Validation的51筆未命中與73筆部分命中全部被分析。
- 原Holdout的35筆未命中與78筆部分命中只做事後描述性分類。
- 每筆案例都有主要分類、正確檔案、Top-20、失敗環節與建議改進方式。
- 自動分類完成後，人工抽查至少30筆案例。

### 預估時間

1～2個工作天。

---

## 第1階段：改進檔案分數整合

### 目標

避免只因某一小段程式碼分數最高，就忽略同一檔案中的其他相關線索。

### 目前程式狀態

E1程式已完成。TF-IDF階段現在會保留同檔案的多個chunk作為聚合證據；SBERT仍只處理每個檔案的一個代表chunk。完成SBERT重排後，系統再依指定的E1模式加入有上限的多chunk、symbol coverage與package proximity分數。

四種模式已分開實作為`basic`、`supporting-chunks`、`supporting-symbols`與`supporting-symbols-package`，可直接執行E1-A～E1-D比較。聚合模式與參數會寫入method manifest及候選的`scoring_signals`。

### 實作內容

1. 在TF-IDF階段保存每個候選檔案分數最高的數個chunk。
2. SBERT仍只處理每個檔案的一個代表chunk，避免計算量大幅增加。
3. 檔案最終分數加入有上限的supporting-chunk與symbol-coverage加分。
4. 將每個分數來源寫入`scoring_signals`，保留可解釋性。
5. 所有加分權重只在Development調整，不使用Holdout。

建議比較：

| 實驗ID | 方法 |
|---|---|
| E1-A | 目前TF-IDF Top-50＋SBERT基準 |
| E1-B | 基準＋多chunk輔助分數 |
| E1-C | E1-B＋symbol coverage |
| E1-D | E1-C＋package proximity |

固定參數如下；這些是Development待驗證的工程假設，不是文獻給定權重：

| 參數 | 設定 |
|---|---:|
| 每檔最多證據chunk | 5 |
| 證據相對門檻 | 最佳TF-IDF chunk的80% |
| 證據最低分數 | 0.05 |
| 每個額外chunk加分 | 0.0125 |
| 多chunk加分上限 | 0.05 |
| 每個額外Symbol加分 | 0.01 |
| Symbol加分上限 | 0.04 |
| Package proximity加分上限 | 0.10 |
| 視為重複chunk的行數重疊率 | 50% |

完整設定另存於`reports/fault_localization/stage1_next_iteration/e1_experiment_matrix.json`。

### 完整Validation結果（2026-08-17）

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 決定 |
|---|---:|---:|---:|---:|---|
| E1-A | 89.80% | 82.98% | 56.20% | 0.6597 | 維持正式基準 |
| E1-B | 91.00% | 83.94% | 56.60% | 0.6654 | 探索性保留，不納入正式方法 |
| E1-C | 90.80% | 83.33% | 52.00% | 0.6407 | 不保留 |
| E1-D | 90.00% | 82.28% | 52.60% | 0.6380 | 不保留 |

E1-B的Recall@20比E1-A提高0.96百分點，但成對95%信賴區間為-0.31～+2.27百分點，下限小於0，未通過第三章預先設定的保留條件。因此下一階段仍使用E1-A作為正式基準。完整報告位於`reports/fault_localization/stage1_next_iteration/e1_validation_500/E1_VALIDATION_500_RESULTS_ZH.md`。

### 程式修改範圍

- `src/utils/fault_localization.py`
- `scripts/run_swebench_lite_fault_localization.py`
- `scripts/run_swebench_full_stage1_experiment.py`
- `tests/test_fault_localization.py`

### 驗收條件

- 關閉功能時，輸出必須與目前基準一致。
- 開啟功能時，每筆仍輸出20個不重複檔案。
- 加分必須有上限，不能讓大量低相關chunk無限制累積。
- 通過單元測試、100筆smoke test與Validation 500筆實驗。
- 依第三章的最低條件決定是否保留。

### 預估時間

2～3個工作天，另加一次完整Validation實驗時間。

---

## 第2階段：加入Import Graph

### 目標

模型找到一個相關檔案後，能繼續找到它引用或被它引用的相關檔案。

### 目前程式狀態

現有`repository_proximity`可以從高排名檔案出發，找出它直接import的檔案；目前是實驗性、單向，而且會在每次查詢時重新整理關係。

### 實作內容

1. 建立Repository層級的Import Graph，並與Code Index一起快取。
2. 解析Python的`import`、`from ... import ...`與相對引用。
3. 同時保存「這個檔案引用誰」與「誰引用這個檔案」。
4. 只從高信心候選向外走一層，避免無限制擴散。
5. Import加分必須有上限，並記錄是哪個候選檔案提供關聯證據。

建議比較：

| 實驗ID | 方法 |
|---|---|
| E2-A | 上一階段最佳方法 |
| E2-B | ＋單向Import關係 |
| E2-C | ＋雙向Import關係 |
| E2-D | 最佳Import版本＋最佳檔案聚合版本 |

### 測試案例

- 絕對import、相對import與別名import。
- `__init__.py`與模組重新匯出。
- 循環引用不能造成無限迴圈。
- 找不到對應檔案時不得錯誤加分。
- 關閉Import Graph時必須回到原始結果。

### 驗收條件

- Import Graph只根據修正前Repository建立。
- 圖關係可重複使用，不需要每張Ticket重新解析全部檔案。
- Validation中跨檔案部分命中案例的找回數增加。
- 整體結果符合第三章最低條件。

### 預估時間

3～5個工作天，另加一次完整Validation實驗時間。

### 執行進度（2026-08-17）

E2工程實作與100筆smoke test已完成：

- 已建立可保存於Code Index或獨立sidecar的雙向Import Graph。
- 已支援Python絕對、相對、別名import及`__init__.py`重新匯出。
- 每張Ticket只使用前5個高排名檔案向外走一層，單一候選加分上限為0.08。
- 45個測試全部通過。
- E2-B與E2-C各完成100筆，皆為100筆成功、0筆失敗、每筆20個唯一檔案。

100筆初步Recall@20為：E2-A 88.24%、E2-B 86.91%、E2-C 85.41%。目前兩個Import版本皆未優於基準，但此子集只有Astropy與Django，仍需用完整500筆與成對信賴區間正式判定。完整紀錄位於`reports/fault_localization/stage1_next_iteration/E2_IMPORT_GRAPH_IMPLEMENTATION_SMOKE_ZH.md`。

### 完整Validation結果（2026-08-22）

E2-B與E2-C各完成500筆，皆為0筆失敗、每筆20個唯一候選檔案。

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 正式判定 |
|---|---:|---:|---:|---:|---|
| E2-A | 89.80% | 82.98% | 56.20% | 0.6597 | 維持基準 |
| E2-B | 90.20% | 83.60% | 49.40% | 0.6136 | 僅列探索性結果 |
| E2-C | 89.40% | 83.17% | 53.00% | 0.6384 | 不保留 |

E2-B的Recall@20提高0.62百分點，但成對95%信賴區間為-1.56～+2.72百分點，下限小於0；E2-C只提高0.19百分點，信賴區間為-1.84～+2.26百分點。兩者均未通過全部保留條件，因此不執行E2-D，下一階段仍使用E2-A。完整報告位於`reports/fault_localization/stage1_next_iteration/e2_validation_500/E2_VALIDATION_500_RESULTS_ZH.md`。

---

## 第3階段：加入功能名稱到實作位置的搜尋

### 目標

Ticket只寫公開API或功能名稱時，系統仍能找到真正負責執行該功能的底層檔案。

### 實作內容

1. 從Ticket抽取函式、Class、模組與程式碼形式的名稱。
2. 在Code Index建立「Symbol名稱→定義檔案」對照表。
3. 使用Import Graph尋找重新匯出、包裝函式與底層模組。
4. 將找到的名稱加入內部搜尋查詢，或加入有限度的候選分數。
5. 在輸出中記錄原始名稱、擴充名稱與候選來源。

限制條件：

- 只允許使用Ticket與修正前程式碼。
- 不使用Gold檔名、Patch、測試結果或修正後內容。
- 每個Ticket最多擴充固定數量的名稱與檔案。
- 只採用能在Repository中找到明確定義或引用的名稱。
- 一般英文單字不得直接視為程式Symbol。

建議比較：

| 實驗ID | 方法 |
|---|---|
| E3-A | 上一階段最佳方法 |
| E3-B | ＋Symbol definition expansion |
| E3-C | ＋API re-export／wrapper expansion |
| E3-D | 最佳API擴充＋Import Graph |

### 驗收條件

- 對API-to-implementation失敗類型的找回率提高。
- 不因一般英文詞彙產生大量無關候選。
- 每筆擴充來源可追蹤與重現。
- 整體結果符合第三章最低條件。

### 預估時間

3～5個工作天，另加一次完整Validation實驗時間。

### 執行進度（2026-08-22）

E3-B核心與30筆smoke test已完成：

- 已從Ticket抽取明確的程式名稱，並排除資料欄位標籤與常見程式關鍵字。
- 已在Code Index建立可保存的`Symbol名稱 → 定義檔案`對照。
- 已加入有上限、可追蹤的Symbol definition候選加分。
- 已新增`e3-a-baseline`與`e3-b-symbol-definitions`實驗設定。
- 48項測試全部通過。
- 30筆smoke test全部成功，每筆20個不重複候選檔案。

同30筆初步結果為：E3-A Recall@20 84.52%、E3-B 86.83%。此結果只證明工程流程可執行且方向值得繼續測試，不能作為正式方法選擇。完整紀錄位於`reports/fault_localization/stage1_next_iteration/E3_SYMBOL_DEFINITION_IMPLEMENTATION_SMOKE_ZH.md`。

Development證據檢查亦已完成第一輪：

- 在Development前40筆建立E3-B證據池，40筆全部成功、39筆具有E3證據。
- 以固定亂數種子從39筆證據案例抽取30筆，依E3對應檔案與Gold修改檔案的關係分類。
- 正確對應6筆（20.0%）、名稱過度模糊19筆（63.3%）、錯誤對應5筆（16.7%）。
- 30筆共出現68列Exact證據與87列Leaf證據；`self.version`、`other.version`等點號名稱的leaf fallback會擴充到無關同名Method，是目前最明確的噪音來源。
- 本次證據池只包含`astropy/astropy`，用途是找出規則缺陷，不代表跨Repository比例，也不能取代正式500筆Validation。

點號名稱leaf fallback限制與相同證據池重跑已完成：

- `symbol-definitions-strict`完全關閉點號名稱leaf fallback；雖然非Gold證據減少，但遺失3個Gold證據，Top-1由77.50%降為72.50%，因此淘汰。
- `symbol-definitions-guarded`阻止receiver、過短與泛用名稱，同時保留具辨識力的API名稱。
- Guarded在相同30筆中保留全部26個Gold證據檔案，非Gold證據檔案由75降為55，正確對應由6筆增為8筆，錯誤對應維持5筆。
- Guarded在相同40筆的Hit@20與Recall@20維持100.00%與95.54%；Top-1由77.50%降為75.00%，因此尚未證明可正式取代Legacy。

下一輪500筆Validation保留Legacy與Guarded作成對比較，不使用Strict。完整紀錄位於`reports/fault_localization/stage1_next_iteration/E3_DOTTED_LEAF_FALLBACK_ABLATION_ZH.md`。

Legacy與Guarded的正式500筆Validation比較已完成：

- 兩組皆完成相同500筆、12個Repository，失敗皆為0筆，每筆皆有20個不重複候選檔案。
- Legacy的Hit@20、Recall@20、Top-1與MRR@20分別為91.40%、84.72%、60.80%與0.7024。
- Guarded分別為91.40%、84.55%、61.20%與0.7043。
- Guarded的Recall@20下降0.17個百分點，成對95%信賴區間為-0.43～0.00個百分點，沒有通過Recall改善與信賴區間條件。
- 500筆中Recall改善0筆、退步2筆、其餘498筆相同；退步皆出現在SymPy。
- Guarded雖將Top-20內的leaf對應證據由1,370列降至1,109列，但減少噪音沒有轉化為較高的Top-20找回率。

正式決定保留Legacy作為E3-C基準，不合併Guarded，也不使用Holdout重新調整阻擋規則。完整報告位於`reports/fault_localization/stage1_next_iteration/e3_validation_500/E3_LEGACY_VS_GUARDED_VALIDATION_500_RESULTS_ZH.md`。

原始30筆逐案結果位於`reports/fault_localization/stage1_next_iteration/e3_development_evidence_review_30/E3_DEVELOPMENT_EVIDENCE_REVIEW_30_ZH.md`。

E3-C API重新匯出／wrapper擴充的核心與40筆smoke test已完成：

- Code Index已加入可保存的`api_implementation_links`。
- 已使用修正前Python AST建立`reexport`與直接`wrapper`的一層關係。
- 每筆證據都保存公開名稱、來源檔案、底層Symbol、底層檔案、關係種類與行號。
- 已限制每個名稱最多4個實作檔案、每個候選最多4筆證據、wrapper最多4個有效陳述式，不做遞迴擴充。
- 新增`symbol-definitions-api`模式與`e3-c-api-implementation`實驗設定，49項測試全部通過。
- Development前40筆全部成功，Hit@20、Recall@20、Top-1與MRR@20和Legacy完全相同，分別為100.00%、95.54%、77.50%與0.8471。
- 22筆具有API證據，其中8筆至少有一個證據檔案對到Gold，14筆只有非Gold證據；因此目前只能確認工程可行，尚未證明準確率提升。

完整紀錄位於`reports/fault_localization/stage1_next_iteration/E3_C_API_IMPLEMENTATION_SMOKE_ZH.md`。

E3-C證據案例人工檢查已完成：

- 從37筆API證據池以固定seed抽取30筆，包含Astropy 21筆與Django 9筆。
- 正確對應8筆（26.67%）。
- API關係正確但非本次修改位置13筆（43.33%）。
- 無關對應9筆（30.00%）。
- 主要噪音是點號名稱忽略模組前綴後的leaf碰撞，例如`fits`、`p.group`、`io.html`、`Angle.to_string`與`timezone.now`。

E3-C namespace限制與固定30筆Development複驗已完成：

- 新增`symbol-definitions-api-namespace`模式；點號名稱使用leaf fallback時，前綴必須與API來源或實作命名空間相符。
- 相同30筆全部成功、0筆失敗，8筆正確對應全數保留。
- 無關對應由9筆降為6筆，移除3筆（33.3%）；API證據由83列降為58列。
- Hit@20、Recall@20、Top-1與MRR@20前後完全相同，分別為96.67%、90.56%、46.67%與0.6325。
- 另有1筆關係正確但非本次Gold位置的證據被移除，正式500筆仍須確認泛化影響。

完整複驗報告位於`reports/fault_localization/stage1_next_iteration/e3_c_api_namespace_review_30/E3_C_API_NAMESPACE_REVIEW_30_ZH.md`。

原始E3-C與namespace限制版的正式500筆Development比較已完成：

- 兩版皆完成500筆、12個Repository、失敗0筆，每筆皆有20個不重複候選檔案。
- 兩版Hit@20、Recall@20、Top-1與MRR@20完全相同，分別為91.40%、84.72%、60.80%與0.7024。
- 四項成對差異與其95%信賴區間均為0。
- Namespace版將Top-20 API證據由701列降為567列（-19.1%），但指向Gold的證據案例由137筆降為133筆。
- 只有5筆Top-20集合改變，沒有Gold檔案被加入或移除，所有Ticket的Top-1檔案均不變。
- Namespace版沒有達到Recall@20至少提高0.50個百分點的保留門檻，因此不合併；原始E3-C保留為E3-C實驗基準。

完整正式報告位於`reports/fault_localization/stage1_next_iteration/e3_c_validation_500/E3_C_ORIGINAL_VS_NAMESPACE_VALIDATION_500_RESULTS_ZH.md`。本輪未使用Holdout，也不再根據這500筆調整namespace規則。

---

## 第4階段：測試Call Graph與Repository大小調整

這兩項分開實驗，不同時加入。只有單項有效時，才進行組合測試。

### 4.1 Call Graph

#### 目前執行結果（2026-08-22）

E4核心與固定Validation前30筆smoke test已完成：

- Python AST一層靜態Call Graph、排序加分、診斷欄位與可攜式快取已實作。
- 支援本地函式、直接匯入函式、`module.function()`與`self.method()`；動態或無法唯一解析的呼叫不加分。
- 56項相關單元與回歸測試全部通過；30筆實驗成功、0筆失敗。
- 相較原始E3-C，Hit@20不變，Recall@20增加0.83個百分點，但Top-1下降3.33個百分點、MRR@20下降0.0347。
- 30筆中29筆排序改變，Top-20共有162個檔案收到Call Graph加分，顯示目前觸發範圍過廣。
- 因此目前版本不直接進入500筆比較；先抽查30筆證據並增加觸發限制，再重跑相同smoke test。

完整結果位於`reports/fault_localization/stage1_next_iteration/e4_call_graph_smoke_30/E4_CALL_GRAPH_SMOKE_30_RESULTS_ZH.md`。本輪未使用Holdout。

固定30條Call Graph證據人工分類亦已完成：

- 完整證據池有402條呼叫邊，來自30筆Ticket與162個Top-20候選檔案。
- 使用固定seed `20260823`抽取30條，涵蓋20筆Ticket；Gold只在排名完成後用於事後分類。
- 5條（16.67%）指向Gold修改檔案，10條（33.33%）功能相關但不是本次修改位置，15條（50.00%）完全無關。
- `imported_function`與`module_function`的完全無關比例都為50%，目前不淘汰任一解析類型。
- 第1名來源的無關比例為33.3%，第2–3名為46.7%，第4–5名為66.7%；下一版因此只將來源由前5名限制為前3名，其他參數保持不變。

完整分類位於`reports/fault_localization/stage1_next_iteration/e4_call_graph_evidence_review_30/E4_CALL_GRAPH_EVIDENCE_REVIEW_30_ZH.md`；依分類結果執行的Top-3複驗如下。

E4 Top-3來源限制與相同30筆複驗已完成：

- 新增獨立`outgoing-top3`模式；原Top-5模式保持不變，兩者可分開重現。
- 30筆全部成功、0筆失敗，Hit@20、Recall@20與Top-1和Top-5相同，分別為96.67%、87.66%與63.33%。
- MRR@20由Top-5的0.7243提高至0.7326，成對差異為+0.0083。
- Call Graph證據邊由402降至275（-31.6%），獲加分候選檔案由162降至115（-29.0%）。
- Recall增益沒有消失且證據範圍明顯縮小，因此Top-3保留為E4正式500筆比較候選。

完整結果位於`reports/fault_localization/stage1_next_iteration/e4_call_graph_top3_smoke_30/E4_CALL_GRAPH_TOP3_SMOKE_30_RESULTS_ZH.md`。本輪未使用Holdout。

E4 Top-3與原始E3-C的正式500筆Validation比較已完成：

- 兩版皆完成500筆、12個Repository；E4失敗0筆，每筆皆有20個不重複候選檔案。
- E3-C的Hit@20、Recall@20、Top-1與MRR@20為91.40%、84.72%、60.80%與0.7024。
- E4 Top-3為91.80%、85.92%、56.20%與0.6775；完整／部分／未命中為392／67／41筆。
- Recall@20成對提高1.20個百分點，95%信賴區間為+0.09～+2.36個百分點；Hit@20提高0.40個百分點。
- Top-1下降4.60個百分點，MRR@20下降0.0249，兩項退步的成對信賴區間皆不包含0。
- E4 Top-3通過第三章全部最低條件，因此保留到E6組合實驗；它目前只代表Top-20找回率改善，不直接宣稱為最終v2方法。
- 不再使用本組Validation調整E4參數，原Holdout繼續封存。

完整報告位於`reports/fault_localization/stage1_next_iteration/e4_validation_500/E4_CALL_GRAPH_TOP3_VALIDATION_500_RESULTS_ZH.md`。

#### 目標

Import關係只能知道檔案是否互相引用；Call Graph進一步估計函式或Method實際呼叫了哪個Symbol。

#### 實作內容

- 使用Python AST建立靜態呼叫關係。
- 先處理可明確解析的本地函式、`module.function()`與`self.method()`。
- 只使用一層鄰近關係，不做無限制遞迴。
- 動態派發、反射與執行時產生的呼叫標記為無法確定。
- Call Graph結果與Code Index一起快取。

#### 驗收條件

- 錯誤呼叫關係不得造成大範圍候選加分。
- 循環呼叫不得造成無限迴圈。
- Call Graph單獨實驗達到第三章最低條件才保留。

#### 預估時間

5～8個工作天。

### 4.2 Repository大小調整

#### 目前執行結果（2026-08-23）

Repository大小分組與E3-C基準診斷已完成：

- 使用每張Ticket在base commit的Code Index不重複檔案數；同一Repository取中位數後排序。
- 12個Repository依序平衡分成小、中、大三組，每組4個Repository；分組不使用Gold或準確率。
- 小型組為Flask、Requests、Xarray與Seaborn；中型組為Pylint、Pytest、Sphinx與Scikit-learn；大型組為Astropy、SymPy、Django與Matplotlib。
- 三組的Ticket加權E3-C Recall@20分別為88.73%、81.53%與85.51%；Repository等權Recall@20分別為92.76%、80.25%與84.48%。
- 固定50個候選約占三組Code Index的中位比例分別為49.02%、17.06%與6.17%。這是候選池相對大小，不是Gold檔案進入TF-IDF Top-50的準確率。
- 目前結果只能確認分組與基準差異，尚不能證明大型Repository需要擴大候選池。
- 本輪只使用500筆Validation既有輸出，沒有使用Holdout，也沒有修改E3-C或E4設定。

完整報告位於`reports/fault_localization/stage1_next_iteration/e5_repository_size/E5_REPOSITORY_SIZE_GROUPS_BASELINE_ZH.md`。下一步逐筆計算TF-IDF Top-50 Hit@50與Recall@50，再決定是否執行候選池75與100的完整比較。

完整500筆TF-IDF Top-50分組診斷亦已完成：

- 500筆皆成功建立純TF-IDF檔案層級Top-50；重用124筆既有快取並新計算376筆，失敗0筆。
- 整體Index Recall為99.28%、Hit@50為94.00%、Recall@50為88.94%、MRR@50為0.6260。
- 小型組Hit@50與Recall@50為100.00%與94.98%，Index到Top-50的Recall遺失為3.09個百分點。
- 中型組Hit@50與Recall@50為90.23%與85.79%，Index到Top-50的Recall遺失為13.65個百分點。
- 大型組Hit@50與Recall@50為94.77%與89.45%，Index到Top-50的Recall遺失為9.93個百分點。
- 固定50個候選對中型與大型Repository仍有明顯初步檢索遺漏；小型組已全部Hit，因此下一輪不增加小型組候選池。
- 本輪只使用Validation，Gold僅在TF-IDF排序完成後評估；沒有使用Holdout。

下一輪實驗設定在執行前固定如下：

| 實驗ID | 小型Repository | 中型Repository | 大型Repository | 最終輸出 |
|---|---:|---:|---:|---:|
| E5-A | 50 | 50 | 50 | Top-20 |
| E5-B | 50 | 75 | 75 | Top-20 |
| E5-C | 50 | 100 | 100 | Top-20 |

完整診斷報告位於`reports/fault_localization/stage1_next_iteration/e5_repository_size/E5_TFIDF_TOP50_BY_SIZE_ZH.md`。

固定30筆smoke test亦已完成：

- 新增可攜式Repository大小分組設定，以及E5-B／E5-C的大小感知`semantic_candidate_k`選擇。
- 57項相關單元測試全部通過。
- 樣本固定為Small、Medium、Large各10筆；E5-B與E5-C皆完成30筆、失敗0筆，且每筆輸出20個不重複候選檔案。
- E5-A、E5-B與E5-C的Hit@20皆為93.33%，Top-1皆為66.67%，MRR@20皆為0.7597。
- E5-A Recall@20為85.94%；E5-B與E5-C皆為86.41%，增加0.48個百分點，但成對95%信賴區間包含0。
- E5-A、E5-B與E5-C均以目前相同runner版本重跑；E5-B平均每筆5.38秒，E5-C為5.74秒，分別比E5-A增加3.2%與10.2%。
- 本次只使用Validation，沒有使用Holdout；30筆結果只判斷工程可行性，不作正式方法選擇。

完整smoke test報告位於`reports/fault_localization/stage1_next_iteration/e5_size_aware_smoke_30/E5_SIZE_AWARE_SMOKE_30_RESULTS_ZH.md`。後續正式比較沿用相同固定設定，沒有看過結果後只保留最好的一次。

相同500筆Validation正式比較已完成：

- E5-A、E5-B、E5-C的Recall@20分別為84.72%、84.91%與84.97%。
- E5-B與E5-C相較E5-A只增加0.19與0.25個百分點，成對95%信賴區間皆包含0。
- 三種方法Top-1皆為60.80%；E5-B與E5-C的MRR@20略低於E5-A。
- 大型組Recall@20在E5-B／E5-C增加0.41／0.66個百分點，但中型組下降0.30／0.67個百分點。
- E5-B與E5-C皆完成500筆、失敗0筆，每筆皆輸出20個不重複候選檔案。
- 本輪只使用Validation，沒有使用Holdout。
- 正式選擇維持E5-A固定50候選；E5-B與E5-C不納入正式方法。

完整正式實驗報告位於`reports/fault_localization/stage1_next_iteration/e5_size_aware_validation_500/E5_SIZE_AWARE_VALIDATION_500_RESULTS_ZH.md`。

### 4.3 E6正式組合與Final Holdout凍結

#### 目前執行結果（2026-08-24～2026-08-25）

E6並不是單獨新增另一套模型，而是把前面通過驗收的設定組成正式版本：

```text
固定50個TF-IDF候選檔案
  → SBERT重新排序
  → E3-C Symbol／API擴充
  → E4 Top-3一層Call Graph
  → 輸出20個不重複候選檔案
```

- E1進階聚合、E2 Import Graph與E5候選池75／100未通過正式保留條件，因此不加入E6。
- E4 Top-3已經使用固定50個候選池，故E6正式設定即為`e4-c-call-outgoing-top3`，不需要使用Validation再調整參數。
- 以目前程式重跑固定30筆，30筆的Top-20檔案順序與檢索分數皆和E4正式輸出完全相同。
- 已凍結方法參數、資料雜湊、八個主要實作檔案雜湊、唯一允許的輸出目錄及一次性完成紀錄。
- 最終凍結編號為`stage1-v2-9db2a1fbec61bf3d`；凍結後若主要程式、Ticket或封存答案的雜湊不同，runner會拒絕執行。
- 新Final Holdout從SWE-bench官方train split建立，共500筆、31個Repository；和先前使用的2,294筆資料有0個Ticket及0個Repository重疊。
- 31個Repository皆已準備完成；500筆Ticket使用496個不同base commit，496個皆能在本機Repository找到。
- Final Holdout已於所有500筆預測完成後才讀取封存答案，並且只執行一次。496筆具有檔案層級答案的主要結果為Hit@20 84.68%、Recall@20 67.17%、Top-1 41.13%與MRR 0.5248。
- 500筆皆成功產生預測、執行失敗0筆；但只有497筆恰好輸出20個候選，youtube-dl有3筆分別輸出7、7、18個候選。
- 標準封存器因此拒絕標記為完整通過；已建立`holdout_evaluated_once_output_contract_failed`不可重跑紀錄。本結果不得用來調參或重跑E6。

完整凍結與資料準備報告位於`reports/fault_localization/stage1_next_iteration/final_holdout_v2/E6_FINAL_FREEZE_AND_HOLDOUT_PREPARATION_ZH.md`。
正式一次性結果報告位於`reports/fault_localization/stage1_next_iteration/final_holdout_v2/FINAL_HOLDOUT_V2_RESULTS_ZH.md`。

### 4.4 E7 Development錯誤分層與大型Repository候選池

#### E7-A基準結果（2026-08-25）

E7只使用1,294筆Development，既有Final Holdout未讀取、未重跑，也不參與參數選擇。E7-A沿用E6設定：固定50個TF-IDF候選、SBERT重排、Symbol／API擴充與Call Graph Top-3。

| 指標 | E7-A Development結果 |
|---|---:|
| Hit@20 | 92.50% |
| Recall@20 | 87.89% |
| Top-1 | 56.11% |
| MRR | 0.6658 |
| 完全／部分／未命中 | 1,077／120／97筆 |

- Hit@20的bootstrap 95%信賴區間為91.04%～93.89%。
- Recall@20的bootstrap 95%信賴區間為86.22%～89.40%。
- 1,294筆皆成功產生預測、執行失敗0筆，且每筆都有20個不重複候選檔案。

#### 217筆失敗分層

- 初始TF-IDF Top-50遺漏85筆。
- 同時包含初始檢索與重排遺漏29筆。
- 正確檔案進入Top-50但被重排排出Top-20共67筆。
- Code Index涵蓋問題17筆。
- 暫時無法細分19筆。

初始檢索相關失敗合計114筆，其中81筆同時屬於大型多模組Repository，因此E7下一個比較先處理「大型Repository的初始候選池不足」。

#### E7固定比較

- E7-A：小型、中型、大型Repository皆保留50個TF-IDF候選。
- E7-B：小型與中型維持50個，大型擴大為100個；其他設定完全相同。
- E7-B需使整體Recall@20至少增加0.50個百分點、成對95%信賴區間下限不小於0、Hit@20下降不超過0.50個百分點，並維持每筆20個唯一候選。

完整報告位於`reports/fault_localization/stage1_next_iteration/e7_development_1294/E7_A_DEVELOPMENT_BASELINE_AND_STRATA_ZH.md`。

#### E7-B Development結果與選擇

- E7-A與E7-B皆完成1,294筆、失敗0筆，每筆皆為20個不重複候選檔案。
- E7-B的Hit@20為92.736%，較E7-A增加0.232個百分點。
- E7-B的Recall@20為87.997%，較E7-A只增加0.106個百分點；成對95%信賴區間為-0.224～+0.459個百分點。
- large Repository Recall增加0.158個百分點；P0與全部初始檢索相關失敗群組分別增加1.624與1.154個百分點，但只視為探索性子群結果。
- E7-B未達整體Recall至少增加0.50個百分點，且成對信賴區間下限小於0，因此不保留；E7正式維持E7-A。

完整比較報告位於`reports/fault_localization/stage1_next_iteration/e7_development_1294/E7_A_VS_E7_B_DEVELOPMENT_RESULTS_ZH.md`。

#### E7-A全新未見Holdout一次性結果（2026-09-01）

- 排除先前2,794筆Ticket與43個Repository後，官方train split只剩27筆、4個完全未見Repository；已使用全部剩餘資料，沒有用舊Repository補足500筆。
- 新Holdout與先前資料的Ticket重疊為0、Repository重疊為0；4/4個Repository與27/27個base commit預檢通過。
- E7-A以`stage1-e7-047d563271a0fa02`凍結後只執行一次；27筆預測全部完成、執行失敗0筆，且Gold只在預測寫入後開啟。
- 原始結果為Hit@20 70.37%、Recall@20 62.63%、Top-1 40.74%與MRR 0.5031；樣本僅27筆，95%信賴區間較寬。
- 20/27筆恰好輸出20個候選；7筆候選不足（3筆為0、1筆為1、3筆為19），因此標準封存器拒絕完整通過，已建立`holdout_evaluated_once_output_contract_failed`不可重跑紀錄。
- 本Holdout不得重跑或用來調參；若修正稀疏Python Repository輸出，須使用新實驗ID與新的外部未見資料來源。

完整結果報告位於`reports/fault_localization/stage1_next_iteration/final_holdout_e7_v1/E7_A_UNSEEN_HOLDOUT_RESULTS_ZH.md`。

### 4.5 E8來源副檔名輸出契約修正與外部Holdout

#### 執行結果（2026-09-01）

- E8-A只新增`.pyi`與`.scala`索引支援，排序設定與E7-A完全相同；index／method版本更新為v3／v20。
- 使用SWE-bench-Live Verified固定commit `a3165f4df45702cdcb7225e70403d055f74d9d01`。排除先前2,821筆與47個Repository後，從382筆、91個未見Repository盲選100筆、53個Repository。
- Ticket與Repository重疊皆為0；53/53個Repository與100/100個base commit預檢通過。
- E8-A以`stage1-e8-f7c5881d1a673480`凍結並只評估一次；100筆預測成功、0失敗，Gold在全部預測寫入後才開啟。
- 原始結果為Hit@20 89.00%、Recall@20 68.89%、Top-1 54.00%與MRR 0.6143。
- 恰好20個候選的完整率從E7新Holdout的20/27（74.07%）提升至98/100（98.00%）；仍有buku 1筆為17個、ntc-templates 1筆為4個。
- 標準封存器仍拒絕完整通過；已建立`holdout_evaluated_once_output_contract_failed`不可重跑紀錄。

完整報告位於`reports/fault_localization/stage1_next_iteration/e8_holdout_v1/E8_A_SWEBENCH_LIVE_HOLDOUT_RESULTS_ZH.md`。

#### 目標

確認大型Repository是否因候選太多，導致正確檔案無法進入SBERT前50名。

#### 實作內容

- 先依Code Index檔案數將Repository分為小、中、大三組。
- 分組報告TF-IDF Top-50 coverage與Recall@20。
- 測試SBERT候選池50、75與100個檔案。
- 正式輸出仍固定為Top-20，不因Repository大小改變。
- 不直接把整個Repository的分數乘上相同係數，因為這不會改變同一Repository內的排名。

#### 驗收條件

- 大型Repository的Recall@20提高。
- 小型Repository不得出現明顯退步。
- 增加候選池後，執行時間與記憶體使用量需記錄在實驗報告。

#### 預估時間

2～3個工作天。

---

## 五、完整實驗矩陣

| 實驗ID | 改進內容 | 主要回答的問題 |
|---|---|---|
| E0 | 目前TF-IDF Top-50＋SBERT | 現有基準是多少？ |
| E1 | 檔案分數整合 | 多個相關chunk能否提高Recall@20？ |
| E2 | Import Graph | 檔案引用關係能否找回其他修改檔案？ |
| E3 | API-to-implementation擴充 | Ticket只提功能名稱時能否找到實作檔案？ |
| E4 | Call Graph | 函式呼叫關係是否比Import關係提供更多幫助？ |
| E5 | Repository大小調整 | 大型專案是否需要更大的SBERT候選池？ |
| E6 | 通過驗收項目的最終組合 | 有效訊號合併後是否仍能穩定提升？ |
| E7 | Development錯誤分層＋大型專案候選池100 | 初始Top-50遺漏是否能在不傷害其他專案下改善？ |

每個實驗都必須保存：

- 完整參數與程式版本雜湊。
- 500筆Validation預測結果。
- Hit@20、Recall@20、Top-1與MRR@20。
- 完全／部分／未命中Ticket清單。
- 與E0的成對差異及95%信賴區間。

E7是E6完成後另建的Development專用迭代，固定使用1,294筆Development比較E7-A與E7-B，不重用既有Final Holdout選擇方法。

## 六、程式修改規劃

### 6.1 主要程式

| 檔案 | 預計修改內容 |
|---|---|
| `src/utils/fault_localization.py` | 聚合、Import／Call Graph、API擴充與新分數訊號 |
| `scripts/run_swebench_lite_fault_localization.py` | 新增功能開關並保存完整設定 |
| `scripts/run_swebench_full_stage1_experiment.py` | 新增實驗方法名稱與參數組合 |
| `scripts/analyze_swebench_full_stage1_results.py` | 增加分組結果與成對比較 |
| `tests/test_fault_localization.py` | 新增聚合、Graph與查詢擴充測試 |

### 6.2 新增檔案

```text
scripts/analyze_stage1_failure_cases.py
reports/fault_localization/stage1_next_iteration/
```

若Graph邏輯使`fault_localization.py`過大，新增：

```text
src/utils/code_relation_graph.py
tests/test_code_relation_graph.py
```

## 七、每個階段的固定執行流程

1. 先寫單元測試，再實作單一功能。
2. 使用少量Ticket執行smoke test，確認輸出格式與程式穩定。
3. 在Development進行參數調整與錯誤分析。
4. 固定設定後，執行Validation 500筆並與E0比較。
5. 根據最低條件決定保留、淘汰或標記為探索性結果。

禁止在看到Validation結果後直接改一個數字、重跑並只保留最好結果。若需要新一輪調整，必須建立新的實驗ID並完整留下結果。

## 八、時間規劃

| 工作 | 預估工作天 |
|---|---:|
| 第0階段：失敗分析 | 1～2天 |
| 第1階段：檔案分數整合 | 2～3天 |
| 第2階段：Import Graph | 3～5天 |
| 第3階段：API到實作位置 | 3～5天 |
| 第4階段：Call Graph | 5～8天 |
| Repository大小調整 | 2～3天 |
| 完整實驗、比較與報告 | 3～5天 |

總計約19～31個工作天，約4～6週。若現有進階聚合與Import鄰近功能可直接通過測試，時間可縮短約3～5個工作天。

## 九、風險與處理方式

| 風險 | 處理方式 |
|---|---|
| Graph加入太多無關檔案 | 只走一層、限制來源數量、設定加分上限 |
| Python動態呼叫無法準確解析 | 只採用高信心靜態關係，其餘不加分 |
| 權重為人工建議值 | 在Development做預先定義的小範圍比較並保存全部結果 |
| 重複查看Holdout造成資料洩漏 | 原Holdout只保留v1結果，v2另建Final Holdout |
| 整體平均掩蓋個別Repository退步 | 同時報告各Repository與大小分組結果 |

## 十、完成定義

下一版第一階段只有在以下條件全部完成後，才能標記為研究完成：

- [x] 五個階段都完成實作或留下有證據的淘汰理由。
- [x] E6設定固定，所有程式與參數有版本雜湊。
- [x] Validation Recall@20相較82.98%有可重現提升。
- [x] Validation所有Ticket皆輸出20個不重複候選檔案，且執行失敗數為0。
- [x] 使用新的Final Holdout完成一次性評估並產生正式報告。
- [ ] Final Holdout全部500筆均符合恰好20個候選的輸出契約（目前497筆通過、3筆未通過）。

研究期望目標為Recall@20達到90%，但這是改進目標，不是預先保證的結果。若未達90%，仍須如實報告各項改進的效果、信賴區間與剩餘限制。

## 十一、執行檢查表

### 已完成

- [x] 建立`analyze_stage1_failure_cases.py`。
- [x] 產生Validation 51筆未命中與73筆部分命中分類。
- [x] 對原Holdout 35筆未命中與78筆部分命中做事後分類。
- [x] 確認正確檔案是否存在Code Index。
- [x] 人工確認30筆分層抽樣案例（30筆皆確認，0筆需修正）。
- [x] 決定第1階段聚合實驗的確切參數。
- [x] 完成E1-A～E1-D模式與多chunk證據保留程式。
- [x] 完成E1-D 100筆smoke test（100筆成功，0筆失敗）。
- [x] 在相同500筆Validation完整比較E1-A～E1-D。
- [x] 完成E1選擇：維持E1-A，E1-B僅列探索性結果。

### 接著做

- [x] 完成E2 Import Graph實作與E2-B／E2-C 100筆smoke test。
- [x] 在相同500筆Validation完整比較E2-A、E2-B與E2-C。
- [x] 完成E2選擇：維持E2-A，E2-B僅列探索性結果，E2-C不保留。
- [x] 開始E3 API-to-implementation實作：完成E3-B核心與30筆smoke test。
- [x] 在Development檢查E3-B錯誤擴充並固定設定：Legacy保留，Guarded不保留。

### 之後做

- [x] 完成E3-B Legacy與Guarded的500筆Validation正式比較。
- [x] 完成E3-C API重新匯出／wrapper核心與40筆smoke test。
- [x] 完成E3-C 30筆API證據案例人工檢查。
- [x] 完成E3-C namespace限制與固定30筆Development證據複驗。
- [x] 完成原始E3-C與namespace限制版的正式500筆Development比較。
- [x] 完成E3-C選擇：保留原始版作為E3-C實驗基準，namespace限制版不納入正式方法。
- [x] 完成E4 Call Graph核心、可攜式快取與固定Validation前30筆smoke test。
- [x] 完成E4固定30條Call Graph證據抽查與人工分類。
- [x] 將E4 Call Graph來源限制為前3名，並完成相同30筆複驗。
- [x] 完成E4 Call Graph正式500筆比較與方法選擇。
- [x] 完成E5-B／E5-C大小感知候選池、單元測試與固定30筆smoke test。
- [x] 完成E5 Repository大小實驗；正式選擇維持E5-A固定50候選。
- [x] 選定並凍結E6：固定50候選＋E4 Top-3 Call Graph。
- [x] 建立新的500筆跨Repository Final Holdout並完成31個Repository與496個base commit預檢。
- [x] 只執行一次Final Holdout：500筆預測成功、0失敗，並在預測全部完成後才讀取封存答案。
- [x] 建立不可重跑結果紀錄與正式報告；如實標記3筆未達Top-20輸出契約。
- [x] 建立E7 Development專用實驗設定與方法編號；不得在目前Final Holdout重跑E6。
- [x] 完成E7-A 1,294筆Development基準：Hit@20 92.50%、Recall@20 87.89%，0失敗且全部符合Top-20輸出契約。
- [x] 完成217筆未完全找回案例的TF-IDF Top-50失敗分層與E7優先級。
- [x] 在相同1,294筆Development完成E7-B與E7-A成對比較；E7-B未達保留門檻，E7正式維持E7-A固定50候選。
- [x] E7方法固定後，使用官方train split全部剩餘的27筆、4個未見Repository建立新Holdout並只評估一次；未重用目前Final Holdout選擇方法。
- [x] 建立E7-A新Holdout不可重跑紀錄與正式報告；27筆預測成功、0失敗，Gold在預測完成後才開啟。
- [ ] E7-A新Holdout全部Ticket符合恰好20個候選的輸出契約（目前20/27筆通過，7筆未通過；不得在本Holdout重跑）。
- [x] 建立E8-A新實驗ID，加入`.pyi`／`.scala`索引支援並保持E7-A排序設定不變。
- [x] 從SWE-bench-Live建立100筆、53個Repository的全新未見Holdout，完成100/100個base commit預檢。
- [x] E8-A只評估一次：100筆預測成功、0失敗，Gold只在預測完成後開啟；正式報告與不可重跑紀錄已建立。
- [ ] E8-A外部Holdout全部Ticket符合恰好20個候選的輸出契約（目前98/100筆通過，2筆未通過；不得重跑）。
