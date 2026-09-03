# E3-C Namespace前綴限制：固定30筆Development複驗

## 結論

Namespace前綴限制已完成實作，並使用原本人工分類的同一組30筆案例重新執行。8筆正確對應全部保留，9筆無關對應減少為6筆，且四項Stage-1 Top-20指標均未下降。因此本方法通過30筆證據品質檢查，可以進入正式500筆Development比較；目前尚不能宣稱整體準確率提升。

## 改進內容

原本只要Ticket中的點號名稱與API的最後一段名稱相同，就可能擴充到底層檔案。例如`timezone.now`的`now`會錯對到Django資料庫的`Now`。

新增的`symbol-definitions-api-namespace`模式會在使用點號名稱的leaf fallback前檢查前綴：前綴必須能在API來源檔案、實作檔案或來源Symbol的命名空間中找到，否則拒絕這筆API擴充。未帶點號的名稱與完全相符的API名稱維持原本行為。

## 實驗設定

- 資料：原本人工分類的固定30筆Development證據案例。
- Repository：Astropy 21筆、Django 9筆。
- 基準：`symbol-definitions-api`。
- 改良版：`symbol-definitions-api-namespace`。
- 候選數：每筆Ticket輸出20個不重複候選檔案。
- 執行結果：30筆成功、0筆失敗。
- 注意：這30筆是針對API證據挑選的錯誤分析樣本，不是正式500筆準確率實驗。

## 證據品質比較

| 人工分類 | 修改前 | Namespace限制後 | 變化 |
|---|---:|---:|---:|
| 正確對應 | 8 | 8 | 全數保留 |
| 無關對應 | 9 | 6 | 移除3筆（-33.3%） |
| 關係正確但非本次修改位置 | 13 | 12 | 移除1筆 |
| API證據列數 | 83 | 58 | 移除25列（-30.1%） |

被成功移除的3筆無關案例為：

- `astropy__astropy-13838`：拒絕`p.group`錯對到FITS `Group`。
- `astropy__astropy-14701`：拒絕文件網址中的`io.html`錯對到ASCII `HTML`。
- `django__django-12961`：拒絕`timezone.now`錯對到資料庫函式`Now`。

仍留下6筆無關案例，主要原因是`fits`、`constant`、`HttpResponse`與`to_string`也會以未帶前綴的名稱出現在Ticket中；namespace規則只處理點號名稱，無法安全地移除這些證據。

## 正確對應保留檢查

原本8筆「API證據指向Gold修改檔案」的案例，在新版本中仍有API證據指向相同Gold檔案，保留率為100%。因此本次降噪沒有犧牲已確認的8筆正確對應。

另外，`astropy__astropy-12880`的一組read／write關係雖然與Ticket功能相關，但不是本次Gold修改位置；namespace規則也將它移除。這是目前規則的取捨，正式500筆實驗仍須檢查是否會影響其他案例。

## Stage-1 Top-20結果

下表使用相同30筆進行成對比較，MRR只計算前20名：

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 |
|---|---:|---:|---:|---:|
| 原始E3-C | 96.67% | 90.56% | 46.67% | 0.6325 |
| Namespace限制版 | 96.67% | 90.56% | 46.67% | 0.6325 |
| 成對差異 | 0.00個百分點 | 0.00個百分點 | 0.00個百分點 | 0.0000 |

四項成對差異的bootstrap 95%信賴區間均為0～0。30筆中有25筆完整找回、4筆部分找回、1筆完全未命中，前後結果相同。

只有`django__django-12961`的Top-20集合改變：錯誤加入的`django/db/models/functions/datetime.py`被移除，由另一個非Gold檔案補入；該Ticket原本的正確檔案仍留在Top-20，所以整體指標不變。

## 判定與下一步

本輪達成兩個預定條件：

1. 8筆正確對應沒有損失。
2. 9筆無關案例確實減少，從9筆降為6筆。

因此保留Namespace版本作為E3-C正式比較候選。下一步應在同一組500筆Development上成對比較原始E3-C與Namespace版本，依Recall@20、Top-1、MRR@20及成對95%信賴區間決定是否正式採用。正式比較完成前不使用Holdout，也不將30筆結果當作整體準確率。

## 結果檔案

- `test_predictions.jsonl`：30筆Namespace版本輸出。
- `test_metrics.json`：本次執行的評估指標。
- `test_failures.jsonl`：失敗紀錄，本次為0筆。
- `test_run_manifest.json`：固定方法設定與執行資訊。
- `comparison.json`：原始E3-C與Namespace版的機器可讀比較結果。
