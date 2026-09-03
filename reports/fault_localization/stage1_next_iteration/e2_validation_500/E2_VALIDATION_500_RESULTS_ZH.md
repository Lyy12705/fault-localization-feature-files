# E2 Import Graph：500筆Validation結果

## 執行完整性

- E2-B與E2-C皆執行相同500筆Validation。
- 兩組皆產生500筆預測，執行失敗皆為0筆。
- 每筆皆輸出20個不重複候選檔案。
- 只使用Ticket與修正前Code Index建立Import Graph，未使用Holdout、Gold檔名、Patch或修正後程式碼進行排名。
- 成對95%信賴區間使用10,000次bootstrap，seed為20260822。

## 整體結果

| 方法 | Hit@20 | Recall@20 | 修正前存在檔案Recall@20 | Top-1 | MRR@20 | 完全／部分／未命中 |
|---|---:|---:|---:|---:|---:|---:|
| E2-A 基準 | 89.80% | 82.98% | 83.32% | 56.20% | 0.6597 | 376／73／51 |
| E2-B 單向Import | **90.20%** | **83.60%** | **83.98%** | 49.40% | 0.6136 | 381／70／49 |
| E2-C 雙向Import | 89.40% | 83.17% | 83.53% | 53.00% | 0.6384 | 381／66／53 |

本批共有23個Gold檔案在base commit尚不存在，因此另呈現「修正前存在檔案Recall@20」作為輔助指標；正式主要指標仍是原始Recall@20。

## 與E2-A的成對差異

| 方法 | Recall@20差異 | 成對95%信賴區間 | Hit@20差異 | Top-1差異 | MRR@20差異 | 判定 |
|---|---:|---:|---:|---:|---:|---|
| E2-B | +0.62百分點 | -1.56～+2.72 | +0.40百分點 | -6.80百分點 | -0.0461 | 僅列探索性結果 |
| E2-C | +0.19百分點 | -1.84～+2.26 | -0.40百分點 | -3.20百分點 | -0.0213 | 不保留 |

E2-B達到「Recall@20至少提高0.50百分點」與「Hit@20下降不超過0.50百分點」兩項條件，但Recall差異信賴區間下限為-1.56百分點，未達下限不得小於0的條件。E2-C的Recall增幅不足0.50百分點，信賴區間下限也小於0。

E2-B與E2-C的Top-1及MRR@20都下降。成對信賴區間顯示E2-B的Top-1與MRR下降均不包含0；E2-C亦相同，表示Import加分會把部分原本排名靠前的正確檔案往後推。

## 多檔案Ticket判讀

Validation共有143筆多檔案Ticket：

| 方法 | 多檔案Recall@20差異 | 改善筆數 | 退步筆數 | 部分命中轉完整命中 |
|---|---:|---:|---:|---:|
| E2-B | +1.47百分點 | 23 | 18 | 10 |
| E2-C | +1.35百分點 | 22 | 19 | 12 |

Import Graph確實能找回部分跨檔案修改點，但也會引入其他關聯檔案並擠掉原候選，因此整體改善無法穩定重現。E2-B另有12筆從完全未命中變成完整命中，但同時有17筆原本完整命中退為部分命中或完全未命中。

## 各Repository Recall@20變化

| Repository | E2-A | E2-B | E2-C |
|---|---:|---:|---:|
| astropy/astropy | 86.85% | 86.85% | 86.85% |
| django/django | 87.11% | 85.33% | 85.03% |
| matplotlib/matplotlib | 72.63% | 78.18% | 76.02% |
| mwaskom/seaborn | 86.67% | 93.33% | 93.33% |
| pallets/flask | 100.00% | 100.00% | 100.00% |
| psf/requests | 100.00% | 100.00% | 100.00% |
| pydata/xarray | 84.36% | 89.50% | 89.29% |
| pylint-dev/pylint | 80.13% | 72.44% | 70.51% |
| pytest-dev/pytest | 76.67% | 78.00% | 80.67% |
| scikit-learn/scikit-learn | 88.94% | 88.94% | 89.42% |
| sphinx-doc/sphinx | 70.76% | 82.97% | 75.42% |
| sympy/sympy | 79.76% | 77.01% | 79.44% |

結果顯示E2-B對Matplotlib、Xarray與Sphinx有明顯幫助，但Django、Pylint與SymPy退步。Import關係的有效性依Repository差異很大，不適合直接加入所有專案的正式排名。

## 正式決定

E2不修改目前正式方法，下一階段仍使用E2-A，也就是TF-IDF Top-50＋SBERT與基本檔案聚合。

- E2-B保留為探索性研究結果，不合併進正式方法。
- E2-C不保留。
- 因E2-B與E2-C皆未通過全部條件，不執行E2-D組合實驗。
- 不使用Holdout重新選擇Import權重。
- 下一步進入E3「功能名稱到實作位置」的查詢擴充。

## 結果檔案

- `reports/fault_localization/stage1_next_iteration/e2_validation_500/e2_b/predictions.jsonl`
- `reports/fault_localization/stage1_next_iteration/e2_validation_500/e2_b/metrics.json`
- `reports/fault_localization/stage1_next_iteration/e2_validation_500/e2_c/predictions.jsonl`
- `reports/fault_localization/stage1_next_iteration/e2_validation_500/e2_c/metrics.json`
- `reports/fault_localization/stage1_next_iteration/e2_validation_500/paired_comparison.json`
- `reports/fault_localization/stage1_next_iteration/e2_validation_500/selection.json`
