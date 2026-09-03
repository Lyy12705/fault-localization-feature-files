# E4 Call Graph：固定30筆Validation Smoke Test

## 結論

E4一層靜態Call Graph已完成核心實作，固定Validation前30筆皆成功產生20個候選檔案，沒有執行失敗。相較原始E3-C，Recall@20由86.83%提高至87.66%，增加0.83個百分點；但Top-1由66.67%降至63.33%，MRR@20由0.7589降至0.7243。

目前版本不直接進入500筆正式比較。原因是30筆中有29筆排序改變，所有Ticket都收到Call Graph證據，Top-20中共有162個檔案獲得Call Graph加分；這與「不得造成大範圍候選加分」的驗收方向不一致。下一步先抽查證據並縮小觸發範圍，再重跑相同30筆。

## 本次完成的功能

- 使用Python AST建立靜態函式呼叫關係。
- 支援本地函式、直接匯入函式、`module.function()`與`self.method()`。
- 只使用一層呼叫關係，不進行遞迴展開。
- 動態呼叫、反射或無法唯一解析的呼叫不加入候選加分。
- Call Graph可寫入Code Index，也可使用與環境無關的sidecar快取重複使用。

Call Graph只作為候選排序的輔助訊號。本次沒有啟用Import Graph、Repository大小調整，也沒有使用Holdout。

## 實驗設定

| 項目 | 設定 |
|---|---|
| 資料 | 固定Validation前30筆 |
| Repository | Astropy 22筆、Django 8筆 |
| 基準 | 原始E3-C：TF-IDF Top-50＋SBERT＋Symbol／API擴充 |
| E4方法 | 原始E3-C＋一層outgoing Call Graph |
| 輸出 | 每筆20個不重複候選檔案 |
| 執行結果 | 30筆成功、0筆失敗 |
| Holdout | 未使用 |

## Stage-1 Top-20結果

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 |
|---|---:|---:|---:|---:|
| 原始E3-C | 96.67% | 86.83% | 66.67% | 0.7589 |
| E4 Call Graph | 96.67% | 87.66% | 63.33% | 0.7243 |
| 成對差異 | 0.00個百分點 | +0.83個百分點 | -3.33個百分點 | -0.0347 |

成對bootstrap 95%信賴區間：

| 指標 | 差異95%信賴區間 |
|---|---:|
| Hit@20 | 0.00～0.00個百分點 |
| Recall@20 | 0.00～+2.50個百分點 |
| Top-1 | -10.00～0.00個百分點 |
| MRR@20 | -0.0748～-0.0080 |

Recall@20的增加來自`django__django-13841`：四個正確檔案中多找回一個，因此該筆Recall增加25個百分點。其他29筆Recall沒有增加。`astropy__astropy-8292`的第一個正確檔案則由第1名降至第2名，使整體Top-1少一筆。

## Call Graph影響範圍

| 檢查項目 | 結果 |
|---|---:|
| 有Call Graph證據的Ticket | 30／30 |
| 獲得Call Graph加分的Top-20檔案 | 162個 |
| 每筆平均獲得加分的Top-20檔案 | 5.4個 |
| 排序或Top-20集合改變的Ticket | 29／30 |
| 平均Call Graph加分 | 0.0628 |
| 最大Call Graph加分 | 0.0720 |

這組數字顯示目前規則雖然有找到一個額外正確檔案，但也廣泛改變原本排序。30筆樣本不足以決定整體準確率，而且MRR下降表示正確檔案平均被排得較後面。

## 工程驗證

- E4專屬測試3項通過。
- 錯誤定位、E3證據與E4回歸測試共56項通過。
- 30筆執行時間約5分26秒。
- Code Index命中30次；Call Graph建立29次、快取命中1次。
- 重複程式碼版本已確認可直接讀取Call Graph快取。

## 判定與下一步

本輪判定為「工程smoke test通過、目前參數尚未通過研究驗收」。不把這30筆結果當成整體準確率，也不以目前設定直接執行500筆正式比較。

下一步固定抽查30筆Call Graph證據，將每筆關係分成「指向Gold修改檔案」、「功能相關但非本次修改位置」與「無關」。依結果加入觸發限制後，重跑同一批30筆；只有影響範圍明顯縮小且Recall增益沒有消失，才進入500筆Validation。

## 後續證據抽查結果（2026-08-23）

已從402條Call Graph證據邊以固定seed抽取30條並完成逐條分類：5條指向Gold、10條功能相關但非本次修改位置、15條完全無關。兩種解析類型的無關率均為50%，但來源排名4–5的無關率達66.7%，高於來源排名1的33.3%。

因此下一個改良版只把Call Graph來源由前5名限制為前3名，其他參數不變，再重跑相同30筆。完整分類位於`../e4_call_graph_evidence_review_30/E4_CALL_GRAPH_EVIDENCE_REVIEW_30_ZH.md`。

Top-3複驗已完成：Recall@20維持87.66%，MRR@20由0.7243提高至0.7326，證據邊減少31.6%，獲加分候選檔案減少29.0%。Top-3已保留為E4正式500筆比較候選，完整結果位於`../e4_call_graph_top3_smoke_30/E4_CALL_GRAPH_TOP3_SMOKE_30_RESULTS_ZH.md`。

## 結果檔案

- `test_predictions.jsonl`：E4的30筆候選輸出。
- `test_metrics.json`：E4單組評估結果。
- `test_failures.jsonl`：失敗紀錄，本次為0筆。
- `test_run_manifest.json`：固定方法設定與執行資訊。
- `paired_analysis.json`：原始E3-C與E4的成對比較及95%信賴區間。
