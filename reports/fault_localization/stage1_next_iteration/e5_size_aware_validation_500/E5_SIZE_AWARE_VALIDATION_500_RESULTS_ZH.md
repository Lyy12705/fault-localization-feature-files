# E5 Repository 大小感知候選池：500 筆 Validation 正式實驗

## 一、實驗目的

本次使用相同 500 筆 Validation，正式比較固定候選池與 Repository 大小感知候選池，確認增加送入 SBERT 的候選檔案數量，是否能提高第一階段 Top-20 錯誤定位結果。

- 評估範圍：第一階段 Top-20 候選檔案。
- Repository 分組：Small、Medium、Large 各 4 個 Repository；分組在實驗前固定。
- Gold 使用方式：排序完成後才用來計算指標。
- 本次沒有使用 Holdout。

## 二、比較方法

| 方法 | Small 候選池 | Medium 候選池 | Large 候選池 | 最終輸出 |
|---|---:|---:|---:|---:|
| E5-A 固定候選池 | 50 | 50 | 50 | Top-20 |
| E5-B 大小感知 75 | 50 | 75 | 75 | Top-20 |
| E5-C 大小感知 100 | 50 | 100 | 100 | Top-20 |

三種方法皆使用 TF-IDF 初步檢索、SBERT 語意重新排序，以及 E3-C 的 API／Symbol 擴充設定。本次唯一研究變因是送入 SBERT 的候選檔案數量。

E5-A 重用已凍結的 500 筆 E3-C 輸出；在正式比較前，另以目前 runner 對固定 30 筆重跑 E5-A，30 筆結果與既有輸出完全一致。

## 三、執行完整性

- E5-A、E5-B、E5-C 都涵蓋相同 500 張 Ticket。
- E5-B 與 E5-C 都成功 500 筆、失敗 0 筆。
- 每張 Ticket 都輸出 20 個不重複候選檔案。
- E5-B 實際使用 Small=50、Medium/Large=75。
- E5-C 實際使用 Small=50、Medium/Large=100。

## 四、整體評估結果

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 完全命中／部分命中／未命中 |
|---|---:|---:|---:|---:|---:|
| E5-A 固定 50 | 91.40% | 84.72% | 60.80% | 0.7024 | 384／73／43 |
| E5-B 50／75／75 | 91.60% | 84.91% | 60.80% | 0.7020 | 384／74／42 |
| E5-C 50／100／100 | 91.60% | 84.97% | 60.80% | 0.7015 | 384／74／42 |

相較 E5-A 的成對差異：

| 方法 | Hit@20 差異（95% CI） | Recall@20 差異（95% CI） | Top-1 差異 | MRR@20 差異（95% CI） |
|---|---:|---:|---:|---:|
| E5-B | +0.20（0.00～+0.60）個百分點 | +0.19（-0.24～+0.73）個百分點 | 0.00 | -0.0003（-0.0012～+0.0003） |
| E5-C | +0.20（-0.40～+1.00）個百分點 | +0.25（-0.43～+0.94）個百分點 | 0.00 | -0.0009（-0.0021～+0.0001） |

E5-B 與 E5-C 的 Recall@20 點估計都略高，但信賴區間包含 0，表示目前不能排除改善只是樣本波動。兩種方法的 Top-1 都沒有提升，MRR@20 則略微下降。

## 五、Repository 大小分組結果

| 大小組別 | Ticket 數 | E5-A Recall@20 | E5-B Recall@20 | E5-C Recall@20 |
|---|---:|---:|---:|---:|
| Small | 42 | 88.73% | 88.73% | 88.73% |
| Medium | 133 | 81.53% | 81.23% | 80.85% |
| Large | 325 | 85.51% | 85.92% | 86.17% |

與 E5-A 相比：

- Small 沿用 50 個候選，因此三種方法結果完全相同。
- Medium 的 E5-B 下降 0.30 個百分點；E5-C 下降 0.67 個百分點。
- Large 的 E5-B 增加 0.41 個百分點，95% CI 為 -0.23～+1.24。
- Large 的 E5-C 增加 0.66 個百分點，95% CI 為 -0.03～+1.51。

結果顯示大型 Repository 有正向訊號，但提升尚未達到可明確區分於 0 的程度；將中型 Repository 的候選池一起增加，沒有帶來整體好處。

## 六、執行成本

| 方法 | 完整實驗牆鐘時間 | 約略分鐘 |
|---|---:|---:|
| E5-A 固定 50 | 1362.15 秒 | 22.7 分鐘 |
| E5-B 50／75／75 | 1296.02 秒 | 21.6 分鐘 |
| E5-C 50／100／100 | 1394.83 秒 | 23.2 分鐘 |

三次實驗在不同時間獨立執行，牆鐘時間會受系統負載與平行排程影響，因此不能把 E5-B 較快解讀為擴大候選池能加速。相同本輪中，E5-C 比 E5-B 多約 7.6% 牆鐘時間，符合候選池增加會提高重排成本的方向。

## 七、正式方法選擇

本輪維持 **E5-A 固定 50 個候選檔案** 作為第一階段正式方法，不保留 E5-B 或 E5-C。

判斷依據：

1. E5-B／E5-C 整體 Recall@20 只增加 0.19／0.25 個百分點，95% 信賴區間都包含 0。
2. Top-1 完全沒有改善，MRR@20 略微下降。
3. 大型 Repository 的小幅提升同時伴隨中型 Repository 退步。
4. E5-C 增加更多重排成本，但沒有形成可信且一致的準確率提升。

大型 Repository 單獨擴大候選池可列為後續探索性實驗，但不得使用本次 Validation 再調整後宣稱為已驗證的正式提升。

## 八、下一步

E5 Repository 大小實驗已完成。下一步凍結 E5-A 的方法設定、資料處理流程與評估程式，再依計劃建立新的 Final Holdout；Holdout 只在所有設定固定後執行一次。

## 九、可重現產物

- E5-B 輸出：`reports/fault_localization/stage1_next_iteration/e5_size_aware_validation_500/e5_b/`
- E5-C 輸出：`reports/fault_localization/stage1_next_iteration/e5_size_aware_validation_500/e5_c/`
- 整體成對分析：`reports/fault_localization/stage1_next_iteration/e5_size_aware_validation_500/paired_analysis.json`
- 大小分組分析：`reports/fault_localization/stage1_next_iteration/e5_size_aware_validation_500/size_group_analysis.json`
- 分組設定：`configs/fault_localization/e5_repository_size_groups.json`

