# E3-C API重新匯出與Wrapper：實作及40筆Smoke Test

## 一句話結論

E3-C核心已可執行並能追蹤公開API到實作檔案，但Astropy前40筆的準確率與Legacy完全相同；下一步必須先檢查證據品質，再決定是否跑正式500筆Validation。

## 已實作內容

1. Code Index新增`api_implementation_links`，可序列化並在不同環境載入。
2. 使用修正前Python AST找出兩種一層關係：
   - `reexport`：`__init__.py`、明確別名或`__all__`公開的重新匯出。
   - `wrapper`：函式或Method直接將工作委派給其他模組的函式。
3. 新增`symbol-definitions-api`模式與`e3-c-api-implementation`實驗設定。
4. 候選輸出會記錄Ticket名稱、公開API、來源檔案、關係種類、底層Symbol、底層檔案與行號。
5. 實驗方法識別資訊已加入E3-C權重與上限，方法版本更新為`fault-localization-method-v15`。

## 安全限制

- 只使用Ticket與修正前程式碼，不使用Gold、Patch或修正後內容計算排名。
- 只接受能由AST及Code Index解析到具體定義的Python關係。
- 每個Ticket名稱最多連到4個實作檔案。
- 每個候選檔案最多保留4筆API證據。
- Wrapper最多分析4個有效陳述式，且只追蹤直接`return target(...)`或直接呼叫。
- 只追蹤一層關係，不做無限制遞迴。
- 語法無法解析時跳過該檔案，保留原本Legacy結果。

本輪固定工程假設如下；這些數值不是文獻給定權重：reexport加分0.04、wrapper加分0.05、單一檔案最高API加分0.08。

## 測試結果

- E3相關及既有測試共49項，全部通過。
- 專用測試涵蓋：重新匯出、直接wrapper、索引序列化、證據追蹤、模糊API超過4個檔案時不加分。

## Development 40筆Smoke Test

- 資料：Development前40筆，全部來自`astropy/astropy`。
- 比較：Legacy E3-B與E3-C使用相同40個Ticket。
- 兩組皆完成40筆，失敗0筆。
- E3-C每筆都有20個不重複候選檔案。
- `repository_path`皆為動態路徑`.`。
- 未使用Holdout。

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 完全／部分／未命中 |
|---|---:|---:|---:|---:|---:|
| Legacy E3-B | 100.00% | 95.54% | 77.50% | 0.8471 | 35／5／0 |
| E3-C | 100.00% | 95.54% | 77.50% | 0.8471 | 35／5／0 |

四項指標的成對差異皆為0，95%信賴區間也都是0～0。這只能表示E3-C沒有破壞這40筆結果，不能證明它能改善其他Repository。

## API證據初步檢查

| 項目 | 結果 |
|---|---:|
| 產生API證據的Ticket | 22／40 |
| 唯一API證據列 | 44 |
| Reexport證據列 | 34 |
| Wrapper證據列 | 10 |
| 至少一筆API證據對到Gold檔案的Ticket | 8／22 |
| API證據未對到Gold檔案的Ticket | 14／22 |

Gold只在實驗完成後用來分析證據品質，沒有參與候選排名。

E3-C使1筆Ticket的Top-20候選集合發生變化，但新增與移除的檔案都不是Gold，因此整體指標不變。雖然8筆的API證據確實連到修改檔案，但另外14筆只有非Gold證據，尚未證明目前規則具有足夠精確度。

## 本輪判定

- E3-C工程核心與小批執行流程完成。
- 本輪不選擇或淘汰E3-C，因為40筆只包含Astropy且指標沒有變化。
- 暫時固定目前規則與權重，不根據這40筆調高加分。
- 下一步從22筆有API證據的案例抽取並人工分類，確認哪些是正確對應、無關對應或API關係正確但不屬於本次修改。

## 後續30筆人工分類結果

為避免只檢查單一Repository，另外執行Development後續資料，將API證據池擴充為37筆：Astropy 28筆、Django 9筆。使用固定seed `20260822`抽取30筆，分布為Astropy 21筆、Django 9筆。

| 分類 | 筆數 | 比例 |
|---|---:|---:|
| 正確對應 | 8 | 26.67% |
| 關係正確但非本次修改位置 | 13 | 43.33% |
| 無關對應 | 9 | 30.00% |

主要無關模式包括：

- `fits`被對到`astropy.units.format.Fits`，而Ticket實際指的是`astropy.io.fits`。
- `p.group`被對到FITS的`Group`類別。
- `io.html`來自文件網址，卻被當成ASCII HTML API。
- `Angle.to_string`被同名碰撞到OGIP單位格式器。
- `timezone.now`被錯對到Django資料庫函式`Now`。

目前E3-C的API關係本身大多可由AST證明，但「關係存在」不代表它是本次錯誤的修改位置。30%無關案例仍可能干擾候選排序，因此在正式500筆Validation前，應先限制帶有模組前綴名稱的leaf fallback：只有前綴能對上API來源模組時才允許擴充。

完整逐案紀錄位於`reports/fault_localization/stage1_next_iteration/e3_c_api_evidence_review_30/E3_C_API_EVIDENCE_REVIEW_30_ZH.md`。

## Namespace前綴限制複驗結果

已新增`symbol-definitions-api-namespace`模式，並使用上列同一組30筆Development案例重新執行：

- 30筆全部成功，0筆失敗。
- 8筆正確對應全部保留。
- 無關對應由9筆降為6筆，移除`p.group`、`io.html`與`timezone.now`造成的3筆錯誤擴充。
- API證據由83列降為58列。
- Hit@20、Recall@20、Top-1與MRR@20前後完全相同。

此結果代表namespace規則通過小批證據品質檢查，但尚未證明整體準確率提升。下一步是在相同500筆Development上與原始E3-C正式比較。完整結果位於`reports/fault_localization/stage1_next_iteration/e3_c_api_namespace_review_30/E3_C_API_NAMESPACE_REVIEW_30_ZH.md`。

## 正式500筆Development結果

原始E3-C與Namespace版皆完成相同500筆、12個Repository，失敗0筆。兩版的Hit@20、Recall@20、Top-1與MRR@20完全相同，分別為91.40%、84.72%、60.80%與0.7024。

Namespace版把Top-20 API證據由701列降為567列，但也讓4筆Ticket失去原本指向Gold檔案的API證據，且Recall@20沒有提高。因此正式決定不合併Namespace限制，保留原始E3-C作為E3-C實驗基準；本輪不使用Holdout重新調整。完整報告位於`reports/fault_localization/stage1_next_iteration/e3_c_validation_500/E3_C_ORIGINAL_VS_NAMESPACE_VALIDATION_500_RESULTS_ZH.md`。

## 結果檔案

- `e3_c_development_smoke_40/test_predictions.jsonl`
- `e3_c_development_smoke_40/test_metrics.json`
- `e3_c_development_smoke_40/test_failures.jsonl`
- `e3_c_development_smoke_40/paired_analysis.json`
- `e3_c_api_evidence_review_30/e3_c_api_evidence_review_30.json`
- `e3_c_api_evidence_review_30/e3_c_api_evidence_review_30.csv`
- `e3_c_api_evidence_review_30/manual_decisions.json`
- `e3_c_api_namespace_review_30/test_predictions.jsonl`
- `e3_c_api_namespace_review_30/test_metrics.json`
- `e3_c_api_namespace_review_30/comparison.json`
- `e3_c_validation_500/paired_analysis.json`
- `e3_c_validation_500/selection.json`
