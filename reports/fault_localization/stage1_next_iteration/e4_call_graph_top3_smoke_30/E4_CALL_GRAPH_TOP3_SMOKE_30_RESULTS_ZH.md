# E4 Call Graph Top-3來源限制：固定30筆Validation複驗

## 結論

依固定30條證據人工分類結果，E4改良版只把Call Graph來源候選由前5名限制為前3名，其他解析類型、加分與fan-out參數完全不變。固定Validation前30筆全部成功，Recall@20增益維持不變；Call Graph證據邊減少31.6%，獲加分候選檔案減少29.0%，MRR@20比Top-5版本提高0.0083。

因此Top-3版本通過本輪工程smoke條件，可進入500筆Validation正式比較；目前仍不能宣稱Call Graph應納入正式方法。

## 實驗設定

| 項目 | 設定 |
|---|---|
| 資料 | 與前一輪完全相同的Validation前30筆 |
| 基準 | 原始E3-C |
| E4 Top-5 | Call Graph來源為排序前5名 |
| E4 Top-3 | Call Graph來源為排序前3名 |
| 其他參數 | 全部固定不變 |
| 輸出 | 每筆20個不重複候選檔案 |
| 執行結果 | 30筆成功、0筆失敗 |
| Holdout | 未使用 |

## 準確率比較

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 |
|---|---:|---:|---:|---:|
| 原始E3-C | 96.67% | 86.83% | 66.67% | 0.7589 |
| E4 Top-5 | 96.67% | 87.66% | 63.33% | 0.7243 |
| E4 Top-3 | 96.67% | 87.66% | 63.33% | 0.7326 |

Top-3相較Top-5：Hit@20、Recall@20與Top-1差異均為0；MRR@20增加0.0083，成對bootstrap 95%信賴區間為0.0000～0.0222。

Top-3相較原始E3-C：Recall@20增加0.83個百分點，95%信賴區間為0.00～2.50個百分點；Top-1下降3.33個百分點，MRR@20下降0.0263。這些結果只來自30筆，不用於正式保留決策。

## 噪音影響範圍

| 檢查項目 | E4 Top-5 | E4 Top-3 | 變化 |
|---|---:|---:|---:|
| 有Call Graph證據的Ticket | 30 | 29 | -1（-3.3%） |
| 獲加分的Top-20候選檔案 | 162 | 115 | -47（-29.0%） |
| Top-20中的Call Graph證據邊 | 402 | 275 | -127（-31.6%） |
| 相較E3-C排序改變的Ticket | 29 | 28 | -1 |
| 相較E3-C Top-20集合改變的Ticket | 27 | 24 | -3 |

限制來源排名確實減少了約三成Call Graph證據，但大部分Ticket的候選排序仍會受到影響。因此是否保留Call Graph，必須交由完整500筆的Recall@20、Hit@20、Top-1、MRR與成對信賴區間判定。

## 工程驗證

- 新增`outgoing-top3`模式，原Top-5模式維持不變，可分開重現。
- Method manifest正確記錄`reference_file_k=3`與方法版本v18。
- 新增Top-3邊界測試；錯誤定位相關測試共60項全部通過。
- 30筆執行時間約4分48秒，30次Call Graph快取全部命中，沒有重新建圖。
- Gold只在預測完成後用於評估，沒有輸入檢索或Call Graph。

## 判定與下一步

Top-3版本保留為E4正式Validation候選。下一步使用相同500筆Validation完整比較原始E3-C與E4 Top-3，依計劃書最低條件決定保留、淘汰或列為探索性結果；正式比較完成前不使用Holdout。

## 結果檔案

- `test_predictions.jsonl`：Top-3的30筆輸出。
- `test_metrics.json`：Top-3單組評估結果。
- `test_failures.jsonl`：失敗紀錄，本次為0筆。
- `test_run_manifest.json`：固定方法設定與執行資訊。
- `paired_analysis.json`：E3-C、Top-5與Top-3三方法比較。
- `paired_top5_vs_top3.json`：Top-5與Top-3成對差異。
