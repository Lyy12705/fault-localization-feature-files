# E4 Call Graph Top-3：500筆Validation正式結果

## 一句話結論

E4 Top-3通過計劃書預先設定的全部最低條件：Recall@20由84.72%提高至85.92%，增加1.20個百分點，成對95%信賴區間為+0.09～+2.36個百分點。此方法保留到E6組合實驗，但Top-1與MRR@20顯著下降，因此目前不能直接宣稱為最終模型，也不再使用本組Validation調整Call Graph參數。

## 實驗設定

- 資料：固定500筆Validation、12個Repository，沒有使用Holdout。
- 基準：原始E3-C（`e3-c-api-implementation`）。
- 比較方法：E4 Top-3（`e4-c-call-outgoing-top3`）。
- Call Graph：使用修正前Python程式碼建立一層靜態呼叫關係，只從E3-C前3名檔案向外擴充。
- 共同設定：TF-IDF Top-50、SBERT重新排序、E3-C Symbol/API擴充、basic file aggregation、輸出Top-20候選檔案。
- 統計：同一Ticket成對比較，使用10,000次bootstrap與固定seed `20260817`計算95%信賴區間。
- 執行時間：1,729.645秒（約28分50秒），使用3個Repository分片。

兩組方法皆完成500筆。E4失敗0筆，而且每筆均輸出20個不重複候選檔案。Gold檔案只在排序完成後用於評估；候選檢索只讀取Ticket與base commit的修正前程式碼，沒有讀取Patch或修正後內容。

## Stage-1 Top-20正式結果

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 完整／部分／未命中 |
|---|---:|---:|---:|---:|---:|
| 原始E3-C | 91.40% | 84.72% | 60.80% | 0.7024 | 384／73／43 |
| E4 Top-3 | **91.80%** | **85.92%** | 56.20% | 0.6775 | **392／67／41** |
| 成對差異 | +0.40個百分點 | **+1.20個百分點** | -4.60個百分點 | -0.0249 | +8／-6／-2 |

| 成對差異 | 95%信賴區間 | 判讀 |
|---|---:|---|
| Hit@20 | -0.60～+1.60個百分點 | 平均值提高，但區間包含0 |
| Recall@20 | **+0.09～+2.36個百分點** | 改善區間不包含負值 |
| Top-1 | -7.20～-2.20個百分點 | 明確下降 |
| MRR@20 | -0.0388～-0.0112 | 明確下降 |

逐筆比較中，Recall@20有19筆改善、5筆退步、476筆不變；Hit@20有5筆由未命中變成命中，同時有3筆由命中變成未命中。Top-1有9筆改善、32筆退步，說明Call Graph較有利於把遺漏的正確檔案帶進前20名，但可能把原本第一名的正確檔案往後推。

## 各Repository的Recall@20

| Repository | 原始E3-C | E4 Top-3 | 差異 |
|---|---:|---:|---:|
| astropy/astropy | 87.72% | 87.72% | 0.00 |
| django/django | 88.20% | 89.26% | +1.06 |
| matplotlib/matplotlib | 81.17% | 83.60% | +2.44 |
| mwaskom/seaborn | 86.67% | 86.67% | 0.00 |
| pallets/flask | 100.00% | 100.00% | 0.00 |
| psf/requests | 100.00% | 100.00% | 0.00 |
| pydata/xarray | 84.36% | 87.88% | +3.53 |
| pylint-dev/pylint | 80.13% | 80.13% | 0.00 |
| pytest-dev/pytest | 77.33% | 81.33% | +4.00 |
| scikit-learn/scikit-learn | 92.79% | 93.75% | +0.96 |
| sphinx-doc/sphinx | 70.76% | 77.02% | +6.26 |
| sympy/sympy | 80.83% | 78.16% | -2.67 |

E4在Django、Matplotlib、Xarray、Pytest、Scikit-learn與Sphinx提高Recall@20，其中Sphinx增幅最大；SymPy則退步2.67個百分點。這表示整體提升並非每個Repository都一致，E6組合實驗仍須逐Repository檢查退步情況。

## Call Graph實際影響範圍

| 檢查項目 | 結果 |
|---|---:|
| 具有Call Graph證據的Ticket | 453／500（90.6%） |
| Top-20中獲得Call Graph證據的候選檔案 | 1,858 |
| Top-20中的Call Graph證據邊 | 4,396 |
| 排名順序改變的Ticket | 451／500（90.2%） |
| Top-20候選集合改變的Ticket | 399／500（79.8%） |
| 第一名候選改變的Ticket | 86／500（17.2%） |

Top-3限制已比原Top-5縮小證據範圍，但在完整500筆中仍會改變多數Ticket的排序。這能解釋為何Recall@20提高的同時，Top-1與MRR@20下降；Call Graph訊號有效，但對排名前段的影響仍偏大。

## 正式判定

| 計劃書最低條件 | E4 Top-3結果 | 判定 |
|---|---:|---|
| Recall@20至少提高0.50個百分點 | +1.20個百分點 | 通過 |
| Recall差異95%信賴區間下限不小於0 | +0.09個百分點 | 通過 |
| Hit@20下降不超過0.50個百分點 | 實際提高0.40個百分點 | 通過 |
| 500筆成功且每筆20個不重複檔案 | 500筆、0失敗 | 通過 |
| 排名不讀取Gold、Patch或修正後程式碼 | 只在事後評估讀取Gold | 通過 |

E4 Top-3依預先規則正式保留，作為E6最終組合實驗的候選訊號。這個決定表示「Call Graph對Top-20找回率有幫助」，不表示目前E4已是最終版本，也不忽略Top-1與MRR退步。

後續處理固定如下：

1. 不再根據這500筆Validation修改E4權重或來源數量。
2. E3-C保留為無Call Graph的比較基準。
3. E4 Top-3保留到E6，檢查與其他通過方法合併後是否仍提升Recall@20。
4. 下一個計劃步驟進入E5 Repository大小與SBERT候選池50／75／100比較。
5. Holdout保持封存；v2全部設定固定後才建立或執行新的Final Holdout。

## 結果檔案

- `top3/run_manifest.json`：E4 Top-3完整執行設定與版本。
- `top3/predictions.jsonl`：500筆Stage-1預測結果。
- `top3/metrics.json`：正式執行摘要。
- `paired_analysis.json`：四項Stage-1指標、各Repository結果與成對95%信賴區間。
- `selection.json`：五項驗收條件與正式保留決定。
