# E2 Import Graph：實作與100筆Smoke Test

## 本次完成內容

- 使用Python AST解析`import`、`from ... import ...`、相對引用與別名引用。
- 同時保存「檔案引用誰」與「誰引用此檔案」兩種關係。
- 支援`__init__.py`重新匯出與循環引用；每次排名只走一層，不會遞迴擴散。
- 只使用前5個高排名候選檔案作為關係證據。
- Import Graph加分上限固定為0.08，每個檔案最多記錄4項證據。
- 新Code Index會直接保存Import Graph；舊Code Index則建立獨立sidecar快取，第二次實驗可直接重用。
- 新增`--import-graph-mode off|outgoing|bidirectional`，可分別執行E2-A、E2-B與E2-C。
- 每個候選會記錄`import_graph_score`、`import_graph_bonus`與`import_graph_evidence`，可追查加分來源。

## 測試結果

- 全部45個單元與整合測試通過。
- 已涵蓋絕對import、相對import、別名、重新匯出、循環引用、找不到模組、雙向證據、快取重用與關閉功能不改變基準排名。
- E2-B與E2-C各執行相同100筆Validation子集，兩組皆為100筆成功、0筆失敗。
- 每筆皆輸出20個不重複候選檔案。

## 100筆初步結果

這100筆由Astropy 22筆與Django 78筆組成，只用來確認程式穩定性，不代表完整12個Repository的正式結果。

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 完全／部分／未命中 |
|---|---:|---:|---:|---:|---:|
| E2-A E1基準 | 91.00% | 88.24% | 59.00% | 0.6625 | 83／8／9 |
| E2-B 單向Import | 90.00% | 86.91% | 57.00% | 0.6683 | 82／8／10 |
| E2-C 雙向Import | 88.00% | 85.41% | 57.00% | 0.6727 | 81／7／12 |

相較相同100筆E2-A基準：

- E2-B Recall@20下降1.33個百分點，Hit@20下降1.00個百分點。
- E2-C Recall@20下降2.83個百分點，Hit@20下降3.00個百分點。
- E2-B與E2-C的MRR略高，但第一階段主要指標是Recall@20，因此不能只根據MRR改善判定方法有效。

## 初步判讀

E2工程功能已完成，而且輸出穩定；但目前固定加分設定在這100筆上沒有提高主要指標。雙向關係比單向關係加入更多候選，Recall@20下降也較明顯，表示「被其他檔案引用」的關係較容易帶入無關檔案。

目前不能把E2-B或E2-C加入正式方法。下一步應在相同500筆Validation完整執行E2-B與E2-C，並查看成對95%信賴區間及跨檔案案例找回數；在完整結果出來前，不執行E2-D，也不使用Holdout。

## 結果檔案

- `reports/fault_localization/stage1_next_iteration/e2_b_smoke_100/test_metrics.json`
- `reports/fault_localization/stage1_next_iteration/e2_b_smoke_100/test_predictions.jsonl`
- `reports/fault_localization/stage1_next_iteration/e2_c_smoke_100/test_metrics.json`
- `reports/fault_localization/stage1_next_iteration/e2_c_smoke_100/test_predictions.jsonl`
