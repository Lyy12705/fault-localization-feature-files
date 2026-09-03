# E3-C原始版與Namespace限制版：500筆Development正式比較

## 一句話結論

Namespace限制版不納入正式方法：它確實減少19.1%的API證據，但500筆的Recall@20、Hit@20、Top-1與MRR@20完全沒有提升，且4筆Ticket失去原本指向Gold檔案的API證據。E3-C實驗保留原始`symbol-definitions-api`設定作為基準，不使用Holdout繼續調整。

## 實驗設定

- 資料：固定500筆Development，沒有使用Holdout。
- Repository：12個。
- 原始版：`e3-c-api-implementation`／`symbol-definitions-api`。
- 比較版：`e3-c-api-namespace`／`symbol-definitions-api-namespace`。
- 共同設定：TF-IDF Top-50、SBERT重新排序、Top-20候選檔案、basic file aggregation。
- 兩版皆完成500筆、失敗0筆，每筆都有20個不重複候選檔案。
- 統計：以同一Ticket成對比較，執行10,000次bootstrap計算95%信賴區間。

Gold檔案只在候選排序完成後用於評估；候選檢索本身只讀取Ticket與base commit的修正前程式碼。

## Stage-1 Top-20正式結果

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 | 完整／部分／未命中 |
|---|---:|---:|---:|---:|---:|
| 原始E3-C | 91.40% | 84.72% | 60.80% | 0.7024 | 384／73／43 |
| Namespace限制版 | 91.40% | 84.72% | 60.80% | 0.7024 | 384／73／43 |
| 成對差異 | 0.00個百分點 | 0.00個百分點 | 0.00個百分點 | 0.0000 | 0／0／0 |

四項成對差異的bootstrap 95%信賴區間全部為0～0。12個Repository的四項指標也全部相同，表示Namespace限制沒有改變任何Ticket的正確檔案找回結果或第一個正確檔案排名。

## Namespace規則實際改變了什麼

| 證據檢查 | 原始E3-C | Namespace限制版 | 變化 |
|---|---:|---:|---:|
| 具有API證據的Ticket | 264 | 255 | -9 |
| Top-20中的API證據列 | 701 | 567 | -134（-19.1%） |
| API證據指向Gold的Ticket | 137 | 133 | -4 |
| 指向Gold的API證據列 | 232 | 202 | -30 |

Namespace版在101筆Ticket中拒絕162個點號名稱。500筆中只有5筆的Top-20候選集合改變，分布於Django 1筆、Matplotlib 1筆、Scikit-learn 2筆與SymPy 1筆；這些替換都沒有加入或移除Gold檔案，且所有Ticket的Top-1檔案都沒有改變。

## 發現的限制

固定30筆人工複驗曾顯示8筆正確對應全部保留，但完整500筆找到4筆新的反例：

- `django__django-16070`：移除`obj.query`指向`django/db/models/sql/query.py`的正確證據。
- `pallets__flask-4160`：移除`fjson.dumps`與`sjson.dumps`指向`src/flask/json/__init__.py`的正確證據。
- `pydata__xarray-4419`：移除`xr.concat`指向`xarray/core/concat.py`的正確證據。
- `sympy__sympy-19713`：移除`domain.field`指向`sympy/polys/fields.py`的正確證據。

這表示「前綴沒有出現在檔案命名空間」不能直接判定API關係無效，因為前綴也可能是Ticket範例中的變數別名、套件別名或物件名稱。

## 正式判定

計劃書要求新方法的Validation Recall@20至少提高0.50個百分點。Namespace版的Recall差異為0，因此未通過主要門檻；雖然降噪本身有效，也不能取代準確率與正確證據保留條件。

本輪決定如下：

1. 不將Namespace限制合併到正式候選檢索方法。
2. 保留原始E3-C作為E3-C實驗基準。
3. Namespace結果保留為探索性負面結果，不再根據這500筆修改規則。
4. 不使用Holdout重新調參。

下一個計劃步驟是E4 Call Graph實驗，先做可明確解析的一層靜態呼叫關係與小批smoke test。

## 結果檔案

- `original/run_manifest.json`：原始E3-C正式執行設定。
- `original/predictions.jsonl`：原始E3-C的500筆輸出。
- `namespace/run_manifest.json`：Namespace版正式執行設定。
- `namespace/predictions.jsonl`：Namespace版的500筆輸出。
- `paired_analysis.json`：四項指標、各Repository結果及成對95%信賴區間。
- `selection.json`：驗收條件與正式方法選擇。
