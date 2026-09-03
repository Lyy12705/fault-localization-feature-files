# E5 Repository大小分組與E3-C基準診斷

## 一句話結論

已依Code Index檔案數將12個Repository固定分為小、中、大三組，每組4個Repository。分組只使用修正前程式碼索引大小，不使用Gold；Gold只在分組完成後計算既有E3-C基準指標。

## 分組方法

1. 取得每張Validation Ticket在base commit的Code Index不重複檔案數。
2. 對同一Repository的不同base commit取檔案數中位數。
3. 依中位數由小到大排序12個Repository。
4. 每4個Repository依序分為小型、中型與大型。

此方法讓三組的Repository數量相同，且不會使用準確率或Gold決定分組。

## Repository分組結果

| 分組 | Repository | Ticket數 | Code Index檔案數中位數 | 範圍 |
|---|---|---:|---:|---:|
| 小型 | pallets/flask | 2 | 31 | 31～31 |
| 小型 | psf/requests | 9 | 75 | 73～116 |
| 小型 | pydata/xarray | 26 | 104 | 92～114 |
| 小型 | mwaskom/seaborn | 5 | 109 | 83～110 |
| 中型 | pylint-dev/pylint | 13 | 147 | 113～1003 |
| 中型 | pytest-dev/pytest | 25 | 224 | 185～236 |
| 中型 | sphinx-doc/sphinx | 43 | 286 | 269～294 |
| 中型 | scikit-learn/scikit-learn | 52 | 577 | 529～637 |
| 大型 | astropy/astropy | 22 | 710 | 616～883 |
| 大型 | sympy/sympy | 78 | 746 | 614～886 |
| 大型 | django/django | 184 | 811 | 747～821 |
| 大型 | matplotlib/matplotlib | 41 | 1012 | 1007～1030 |

## 各大小組的E3-C基準結果

| 分組 | Repository數 | Ticket數 | Hit@20 | Ticket加權Recall@20 | Repository等權Recall@20 | Top-1 | MRR@20 | 完整／部分／未命中 | Top-50候選池占索引中位比例 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 小型 | 4 | 42 | 97.62% | 88.73% | 92.76% | 64.29% | 0.7488 | 30／11／1 | 49.02% |
| 中型 | 4 | 133 | 87.22% | 81.53% | 80.25% | 60.90% | 0.6799 | 100／16／17 | 17.06% |
| 大型 | 4 | 325 | 92.31% | 85.51% | 84.48% | 60.31% | 0.7056 | 254／46／25 | 6.17% |

Ticket加權結果反映500筆資料的實際平均；Repository等權結果讓每個Repository各占相同比例，可避免Ticket較多的Django主導大型組。

整體E3-C基準為：Hit@20 91.40%、Recall@20 84.72%、Top-1 60.80%、MRR@20 0.7024。

## 結果判讀限制

「Top-50候選池占索引比例」只是50個候選相對於Code Index檔案數的比例，不是正確檔案進入TF-IDF Top-50的準確率。

下一個E5步驟必須逐筆計算TF-IDF Top-50 Hit@50與Recall@50，才能判斷大型Repository是否真的因候選池固定為50而遺漏正確檔案。

本分析沒有使用Holdout，也沒有改動E3-C或E4的正式設定。
