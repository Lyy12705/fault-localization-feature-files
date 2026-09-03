# E5 Repository 大小感知候選池：固定 30 筆 Smoke Test

## 一、實驗目的

本次實驗只確認 E5-B 與 E5-C 的程式、設定及輸出是否能正常運作，尚不作為正式方法選擇依據。

- 資料來源：既有 500 筆 Validation。
- 固定樣本：Small、Medium、Large 各 10 筆，共 30 筆。
- 抽樣方式：使用固定 seed `20260823` 與 SHA-256 排序，確保可重現。
- 最終輸出：每張 Ticket 固定輸出 20 個不重複候選檔案。
- 本次沒有使用 Holdout。

## 二、比較方法

| 方法 | Small 候選池 | Medium 候選池 | Large 候選池 | 最終輸出 |
|---|---:|---:|---:|---:|
| E5-A 固定候選池 | 50 | 50 | 50 | Top-20 |
| E5-B 大小感知 75 | 50 | 75 | 75 | Top-20 |
| E5-C 大小感知 100 | 50 | 100 | 100 | Top-20 |

三種方法皆沿用 E3-C 的 TF-IDF、SBERT 與 API／Symbol 擴充設定；本次只改變送入 SBERT 的候選檔案數量。

## 三、程式與輸出驗證

- E5-B：30 筆成功、0 筆失敗；Small 實際使用 50，Medium／Large 實際使用 75。
- E5-C：30 筆成功、0 筆失敗；Small 實際使用 50，Medium／Large 實際使用 100。
- 每筆結果皆包含 20 個不重複的 `stage1_candidate_files`。
- E5-B 與 E5-C 產生不同的 `method_id`，可避免實驗結果混用。
- 方法清單保存 Repository 大小分組，不保存本機絕對路徑，可在不同環境重現。

## 四、Smoke Test 結果

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 完全命中／部分命中／未命中 |
|---|---:|---:|---:|---:|---:|
| E5-A 固定 50 | 93.33% | 85.94% | 66.67% | 0.7597 | 22／6／2 |
| E5-B 50／75／75 | 93.33% | 86.41% | 66.67% | 0.7597 | 22／6／2 |
| E5-C 50／100／100 | 93.33% | 86.41% | 66.67% | 0.7597 | 22／6／2 |

依 Repository 大小分組的 Recall@20：

| 方法 | Small（10筆） | Medium（10筆） | Large（10筆） |
|---|---:|---:|---:|
| E5-A 固定 50 | 89.00% | 90.00% | 78.81% |
| E5-B 50／75／75 | 89.00% | 90.00% | 80.24% |
| E5-C 50／100／100 | 89.00% | 90.00% | 80.24% |

E5-B 與 E5-C 相較 E5-A 的 Recall@20 都增加 0.48 個百分點；成對 bootstrap 95% 信賴區間為 0.00～1.43 個百分點，區間包含 0，因此不能從 30 筆 smoke test 宣稱方法已穩定提升。

本次改善來自 Astropy 案例多找回一個正確檔案。E5-B 與 E5-C 的排名結果完全相同，表示在這 30 筆中，把候選池由 75 再增加到 100 沒有帶來額外收益。

## 五、執行時間

以下為 30 筆逐筆推論時間加總與平均，不包含不同平行排程造成的等待差異：

| 方法 | 加總時間 | 平均每筆 | 相對 E5-A |
|---|---:|---:|---:|
| E5-A 固定 50 | 156.35 秒 | 5.21 秒 | 基準 |
| E5-B 50／75／75 | 161.29 秒 | 5.38 秒 | +3.2% |
| E5-C 50／100／100 | 172.29 秒 | 5.74 秒 | +10.2% |

## 六、結果判讀與下一步

E5-B 與 E5-C 已通過工程 smoke test，可以進入相同 500 筆 Validation 的正式比較。30 筆結果顯示擴大候選池具有小幅正向訊號，但樣本太少，而且 E5-B 與 E5-C 尚無準確率差異，因此目前不淘汰任何版本，也不更動正式方法。

下一步固定使用同一套程式與分組設定，在完整 500 筆 Validation 執行 E5-A、E5-B、E5-C 成對比較；正式選擇必須同時檢查 Recall@20、各大小分組結果、95% 信賴區間及執行成本。

## 七、可重現產物

- 分組設定：`configs/fault_localization/e5_repository_size_groups.json`
- 固定樣本：`reports/fault_localization/stage1_next_iteration/e5_size_aware_smoke_30/sample/`
- E5-A 輸出：`reports/fault_localization/stage1_next_iteration/e5_size_aware_smoke_30/e5_a/`
- E5-B 輸出：`reports/fault_localization/stage1_next_iteration/e5_size_aware_smoke_30/e5_b/`
- E5-C 輸出：`reports/fault_localization/stage1_next_iteration/e5_size_aware_smoke_30/e5_c/`
- 成對分析：`reports/fault_localization/stage1_next_iteration/e5_size_aware_smoke_30/paired_analysis.json`
