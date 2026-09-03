# E7 Development錯誤分層與實驗設定

> 本報告只使用Development。現有Final Holdout未被讀取，也不得用於E7調參。

## 一、分層結果

- 失敗案例：217筆。
- 初步檢索相關失敗：114筆。
- 大型多模組失敗：117筆。
- 大型多模組門檻：Top-level模組數至少5個。

| 優先層級 | 說明 | Ticket數 |
|---|---|---:|
| P0_large_multimodule_retrieval | 大型多模組專案的初步檢索遺漏 | 81 |
| P1_other_retrieval | 其他初步檢索遺漏 | 33 |
| P2_large_multimodule_other | 大型多模組專案的其他遺漏 | 36 |
| P3_other_failure | 其他失敗案例 | 67 |

## 二、E7固定比較

| 實驗 | 設定 |
|---|---|
| E7-A | E6固定50候選＋Symbol/API＋Call Graph Top-3 |
| E7-B | 小型50、中型50、大型100；其餘與E7-A相同 |

## 三、方法選擇規則

1. 整體Recall@20至少提高0.50個百分點。
2. 成對95%信賴區間下限不得小於0。
3. Hit@20下降不得超過0.50個百分點。
4. 所有Ticket都必須輸出20個不重複檔案。
5. 同時報告P0與全部初步檢索失敗案例的Recall@20。

## 四、下一步

在相同1,294筆Development依序執行E7-A與E7-B，再進行成對比較。
