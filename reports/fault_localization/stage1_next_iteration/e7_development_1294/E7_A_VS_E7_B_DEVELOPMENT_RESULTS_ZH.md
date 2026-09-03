# E7-A 與 E7-B Development 成對比較結果

> 結論：不保留 E7-B。E7 正式選擇維持 E7-A 固定 TF-IDF 候選池 50。這次只使用 1,294 筆 Development；既有 Final Holdout 未被讀取、未被重跑，也未用於方法選擇。

## 一、比較設定

- E7-A：所有 Repository 的 TF-IDF 初始候選池固定為 50。
- E7-B：small／medium 維持 50，large 擴大為 100。
- 其餘 SBERT、Symbol／API、Call Graph Top-3 與最終 Top-20 設定完全相同。
- 成對 bootstrap：10,000 次，seed `20260825`。

## 二、整體結果

| 指標 | E7-A | E7-B | E7-B − E7-A | 成對 95% CI |
|---|---:|---:|---:|---:|
| Hit@20 | 92.504% | 92.736% | +0.232 百分點 | -0.077～+0.618 |
| Recall@20 | 87.892% | 87.997% | +0.106 百分點 | -0.224～+0.459 |
| Top-1 | 56.105% | 56.105% | 0.000 百分點 | 0.000～0.000 |
| MRR@20 | 0.677282 | 0.677583 | +0.000301 | -0.000154～+0.000967 |

| 結果類型 | E7-A | E7-B |
|---|---:|---:|
| 完全找回 | 1,077 | 1,077 |
| 部分找回 | 120 | 123 |
| 完全未命中 | 97 | 94 |

## 三、large Repository 與目標失敗群組

| 範圍 | Ticket | E7-A Recall@20 | E7-B Recall@20 | 差異 |
|---|---:|---:|---:|---:|
| large Repository | 866 | 88.480% | 88.637% | +0.158 百分點 |
| P0 大型多模組初始檢索失敗 | 81 | 22.885% | 24.509% | +1.624 百分點 |
| 全部初始檢索相關失敗 | 114 | 25.881% | 27.035% | +1.154 百分點 |

- large Repository Recall 差異的成對 95% CI 為 -0.322～+0.685 百分點。
- P0 中 6 筆改善、2 筆退步、73 筆不變；Hit@20 從 50.617% 提高至 53.086%。
- 全部初始檢索相關案例同樣為 6 筆改善、2 筆退步、106 筆不變；Hit@20 從 54.386% 提高至 56.140%。
- 子群改善是探索性結果；整體 Recall 門檻與信賴區間門檻仍未通過。

## 四、事前保留門檻

| 門檻 | 實際結果 | 判定 |
|---|---:|---|
| 整體 Recall@20 至少 +0.50 百分點 | +0.106 | 未通過 |
| Recall 成對 95% CI 下限 ≥ 0 | -0.224 | 未通過 |
| Hit@20 下降不超過 0.50 百分點 | +0.232，未下降 | 通過 |
| 1,294 筆皆為 20 個唯一候選且 0 failure | 全部符合 | 通過 |

E7-B 未同時通過四項門檻，因此標記為 `not_retained`。E7-A 是固定後的 E7 方法；不得使用既有 Final Holdout 再選方法。

## 五、執行與資料完整性

- E7-A：1,294 個唯一 Ticket、缺漏 0、failure 0、候選數錯誤 0、候選路徑重複 0、rank 錯誤 0。
- E7-B：1,294 個唯一 Ticket、缺漏 0、failure 0、候選數錯誤 0、候選路徑重複 0、rank 錯誤 0。
- E7-A 的 8 個 small／medium Repository 共 428 筆與本輪 E7-B 在相同策略下逐項一致；Django 與 SymPy 由 checkpoint 在目前環境補齊。
- E7-B 尾段曾遇到一個 0-byte 舊 Code Index；移除該可重建 cache 後，唯一受影響 Ticket 重跑成功。

## 六、SHA-256

| Artifact | SHA-256 |
|---|---|
| E7-A predictions | `cc981101494872c3ae0f8e271d26acdb1731a9525449c4088523d3d514cf0922` |
| E7-A metrics | `15ee177a3aa856cb5129f52ad736c19602dc2d5b5edcab74e59c2f5f9f707c67` |
| E7-B predictions | `d8060c5efe833793fcd1b6785388bf7cd5a197f261745090e9c1e076b86b2620` |
| E7-B metrics | `9e67f983851bacdf4af2f6d2175b75d8e4fca19b72a662c2737c8bf3e0ac8022` |
| Paired analysis | `424a45981650368c5e7f5a622be43b68a21ad40b3172821051c0aa6c604a3a76` |
| Size-aware analysis | `dfc5c19612e5a620fd3d769449f44a7fe8a8bc364f91012270bb6b0ae6d26d8a` |

## 七、下一步

E7-A 已固定。下一個實驗是另建全新的未見 Holdout，僅用來評估固定後的 E7-A；不得重用既有 Final Holdout。
