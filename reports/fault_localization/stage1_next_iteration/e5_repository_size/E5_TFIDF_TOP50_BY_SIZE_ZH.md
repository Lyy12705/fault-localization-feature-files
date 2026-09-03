# E5：TF-IDF Top-50候選涵蓋率分組結果

## 一句話結論

完整500筆Validation的純TF-IDF Top-50候選已建立。本結果用來判斷固定50個候選是否較容易在大型Repository遺漏正確檔案，沒有使用Holdout。

## 評估方法

- 使用Ticket與base commit修正前Code Index進行純TF-IDF檔案排序。
- 同一檔案只保留TF-IDF分數最高的代表程式碼區塊，再取前50個檔案。
- 不使用SBERT、Symbol/API擴充、Import Graph或Call Graph。
- Repository大小分組沿用上一輪固定結果，不使用Gold重新分組。
- Gold只在Top-50產生後計算Hit@50、Recall@50與MRR@50。

## 三組正式診斷結果

| 分組 | Repository數 | Ticket數 | Index Recall | Hit@50 | Ticket加權Recall@50 | Index→Top-50遺失 | Repository等權Recall@50 | MRR@50 | 完整／部分／未命中 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 小型 | 4 | 42 | 98.06% | 100.00% | 94.98% | 3.09% | 95.28% | 0.6855 | 34／8／0 |
| 中型 | 4 | 133 | 99.44% | 90.23% | 85.79% | 13.65% | 84.95% | 0.5749 | 107／13／13 |
| 大型 | 4 | 325 | 99.38% | 94.77% | 89.45% | 9.93% | 87.20% | 0.6392 | 270／38／17 |

整體結果：Index Recall 99.28%、Hit@50 94.00%、Recall@50 88.94%、Index到Top-50遺失 10.35%、MRR@50 0.6260。

## 各Repository結果

| 分組 | Repository | Ticket數 | Index Recall | Hit@50 | Recall@50 | MRR@50 |
|---|---|---:|---:|---:|---:|---:|
| 小型 | mwaskom/seaborn | 5 | 96.67% | 100.00% | 86.67% | 0.7667 |
| 小型 | pallets/flask | 2 | 100.00% | 100.00% | 100.00% | 1.0000 |
| 小型 | psf/requests | 9 | 100.00% | 100.00% | 100.00% | 0.6898 |
| 小型 | pydata/xarray | 26 | 97.51% | 100.00% | 94.45% | 0.6441 |
| 中型 | pylint-dev/pylint | 13 | 100.00% | 84.62% | 82.05% | 0.3528 |
| 中型 | pytest-dev/pytest | 25 | 99.33% | 92.00% | 88.00% | 0.4995 |
| 中型 | scikit-learn/scikit-learn | 52 | 98.88% | 94.23% | 93.75% | 0.7774 |
| 中型 | sphinx-doc/sphinx | 43 | 100.00% | 86.05% | 76.00% | 0.4411 |
| 大型 | astropy/astropy | 22 | 95.83% | 95.45% | 90.64% | 0.7035 |
| 大型 | django/django | 184 | 100.00% | 97.83% | 94.21% | 0.6714 |
| 大型 | matplotlib/matplotlib | 41 | 97.29% | 92.68% | 82.38% | 0.5335 |
| 大型 | sympy/sympy | 78 | 100.00% | 88.46% | 81.58% | 0.6008 |

## 判讀方式

Index Recall代表修正前Code Index理論上能找回多少Gold檔案；Recall@50與Index Recall之間的差距，代表檔案存在但沒有進入純TF-IDF前50名。

本結果只診斷純TF-IDF候選池，不等同完整E3-C模型。診斷結果支持對中型與大型Repository正式執行候選池75與100。

## 下一步實驗設定

1. 小型Repository維持候選池50，避免增加沒有必要的計算。
2. 中型Repository比較候選池50、75與100。
3. 大型Repository比較候選池50、75與100。
4. 三種設定的最終輸出皆固定Top-20，並以Recall@20與執行時間判定。

## 執行完整性

- 完整快取：500筆。
- 重用既有快取：124筆。
- 本輪新計算：376筆。
- 執行時間：931.641秒。
- Holdout使用：否。
