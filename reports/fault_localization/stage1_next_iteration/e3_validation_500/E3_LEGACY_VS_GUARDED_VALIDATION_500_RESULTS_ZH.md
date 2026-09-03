# E3 Legacy與Guarded：500筆Validation正式比較

## 一句話結論

Guarded確實減少模糊的Symbol leaf對應，但沒有提高Top-20找回率；正式方法維持Legacy，Guarded不保留。

## 比較內容

- **Legacy**：點號名稱可直接用最後一段名稱搜尋定義。例如`self.version`可再用`version`尋找同名Symbol。
- **Guarded**：遇到`self`、`other`等receiver、過短名稱或常見泛用名稱時，不進行最後一段名稱的擴充。
- 兩種方法只差上述保護規則，其餘檢索流程、權重、Code Index與Validation資料完全相同。

## 執行完整性

- 使用相同500筆Validation，共12個Repository。
- Legacy與Guarded皆產生500筆預測，失敗皆為0筆。
- 每筆都輸出20個不重複的候選檔案。
- 兩組涵蓋完全相同的500個Ticket ID。
- `repository_path`皆輸出為動態路徑`.`，未保存本機絕對路徑。
- 未使用Holdout、Patch或修正後程式碼選擇方法。
- 成對95%信賴區間使用10,000次bootstrap，seed為20260822。

## 整體結果

| 方法 | Hit@20 | Recall@20 | 修正前存在檔案Recall@20 | Top-1 | MRR@20 | 完全／部分／未命中 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | **91.40%** | **84.72%** | **85.23%** | 60.80% | 0.7024 | 384／73／43 |
| Guarded | **91.40%** | 84.55% | 85.07% | **61.20%** | **0.7043** | 383／74／43 |

本批資料有23個Gold檔案在修正前版本尚不存在，因此另列「修正前存在檔案Recall@20」協助判讀；正式主要指標仍是原始Recall@20。

## 成對差異與結果判讀

| 指標 | Guarded相對Legacy | 成對95%信賴區間 | 判讀 |
|---|---:|---:|---|
| Hit@20 | 0.00百分點 | 0.00～0.00 | 完全相同 |
| Recall@20 | **-0.17百分點** | **-0.43～0.00** | 沒有改善，未通過保留條件 |
| Top-1 | +0.40百分點 | -0.60～+1.60 | 小幅上升，但差異不穩定 |
| MRR@20 | +0.0019 | -0.0044～+0.0084 | 小幅上升，但差異不穩定 |

預先設定的保留條件要求Recall@20至少增加0.50個百分點，且成對95%信賴區間下限不得小於0。Guarded的Recall不升反降，兩項條件皆未通過，因此不能因Top-1的小幅上升而取代Legacy。

## 實際影響範圍

- 500筆中有90筆的Top-20排序發生變化。
- 44筆的Top-20候選檔案集合發生變化。
- 13筆的第1名候選檔案發生變化。
- Recall@20：0筆改善、2筆退步、498筆不變。
- Top-1：5筆改善、3筆退步、492筆不變。
- MRR@20：12筆改善、7筆退步、481筆不變。
- 其中`sympy__sympy-21952`由完整找回變成只找回一半；`sympy__sympy-18168`由找回三分之二降為三分之一。

## Symbol證據變化

| 項目 | Legacy | Guarded | 變化 |
|---|---:|---:|---:|
| Top-20中有Symbol證據的Ticket | 428 | 419 | -9 |
| Top-20中的全部Symbol證據列 | 2,375 | 2,115 | -260 |
| Leaf對應證據列 | 1,370 | 1,109 | -261 |

Guarded有達成「減少模糊leaf對應」的工程目標，但減少噪音不等於提高錯誤定位準確率。這次刪除的線索中仍包含少量對SymPy有用的對應，因此Top-20 Recall反而下降。

## 各Repository Recall@20

| Repository | Legacy | Guarded | 差異 |
|---|---:|---:|---:|
| astropy/astropy | 87.72% | 87.72% | 0.00 |
| django/django | 88.20% | 88.20% | 0.00 |
| matplotlib/matplotlib | 81.17% | 81.17% | 0.00 |
| mwaskom/seaborn | 86.67% | 86.67% | 0.00 |
| pallets/flask | 100.00% | 100.00% | 0.00 |
| psf/requests | 100.00% | 100.00% | 0.00 |
| pydata/xarray | 84.36% | 84.36% | 0.00 |
| pylint-dev/pylint | 80.13% | 80.13% | 0.00 |
| pytest-dev/pytest | 77.33% | 77.33% | 0.00 |
| scikit-learn/scikit-learn | 92.79% | 92.79% | 0.00 |
| sphinx-doc/sphinx | 70.76% | 70.76% | 0.00 |
| sympy/sympy | **80.83%** | 79.76% | **-1.07百分點** |

11個Repository的Recall完全相同；整體下降全部來自SymPy。這表示目前的固定Guard規則無法在不同專案間穩定改善結果。

## 正式決定

- 保留`e3-b-symbol-definitions`（Legacy）作為下一個E3實驗的基準。
- 不將`e3-b-symbol-definitions-guarded`合併至正式方法。
- Guarded保留為「降低模糊證據」的分析版本，不再用Validation調整其阻擋清單。
- 不查看或使用Holdout重新選擇規則。
- 下一步依計劃實作E3-C：處理API重新匯出與wrapper，使Ticket中的公開功能名稱能連到真正實作檔案。

## 結果檔案

- `legacy/predictions.jsonl`：Legacy 500筆候選結果。
- `guarded/predictions.jsonl`：Guarded 500筆候選結果。
- `analysis.json`：整體、各Repository及10,000次成對bootstrap結果。
- `selection.json`：保留條件與正式方法選擇。
