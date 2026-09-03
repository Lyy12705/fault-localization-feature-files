# E6正式方法凍結與Final Holdout準備結果

## 一句話結論

E6正式方法、資料與評估程式已凍結，新Final Holdout的500筆Ticket、31個Repository及496個base commit均準備完成。本文件原為評估前紀錄；Final Holdout後續已執行一次，正式結果與輸出契約限制請以`FINAL_HOLDOUT_V2_RESULTS_ZH.md`為準。

## 一、E6最後採用哪一個方法？

正式方法為：

```text
Ticket
  → TF-IDF取固定50個候選檔案
  → SBERT重新排序
  → E3-C Symbol／API擴充
  → 從前3名候選向外擴充一層Call Graph關係
  → 輸出20個不重複候選檔案
```

方法標籤為`e4-c-call-outgoing-top3`。這個名稱代表E4 Top-3 Call Graph；同時沿用E5-A驗證後保留的固定50個候選池。

前一份E5報告寫「下一步凍結E5-A」，容易讓人以為Call Graph沒有被採用。依計劃書的E6定義，最後應合併所有通過驗收的項目，因此正式凍結內容是「E5-A固定50候選設定＋E4 Top-3 Call Graph」，不是只有不含Call Graph的E5-A。

## 二、為什麼選擇這個版本？

相同500筆Validation的正式結果如下：

| 方法 | Hit@20 | Recall@20 | Top-1 | MRR@20 |
|---|---:|---:|---:|---:|
| 無Call Graph的E3-C／E5-A | 91.40% | 84.72% | 60.80% | 0.7024 |
| E6採用的E4 Top-3 | **91.80%** | **85.92%** | 56.20% | 0.6775 |
| 差異 | +0.40個百分點 | **+1.20個百分點** | -4.60個百分點 | -0.0249 |

- 第一階段的主要目標是盡量把正確修改檔案保留在前20名，因此主要指標為Recall@20。
- Recall@20的成對95%信賴區間為+0.09～+2.36個百分點，符合事前設定的保留條件。
- E4 Top-3能找回更多正確檔案，但Top-1與MRR@20下降。後續報告必須同時呈現這個取捨，不可寫成所有排名能力都提高。
- E5-B與E5-C把中、大型Repository的候選池增加為75或100，但Recall@20只增加0.19或0.25個百分點，信賴區間皆包含0，因此正式方法仍使用固定50個候選。

## 三、凍結前的一致性檢查

從既有Validation固定抽取30筆，以目前程式重新執行E6：

| 檢查項目 | 結果 |
|---|---:|
| 成功完成 | 30／30 |
| 執行失敗 | 0 |
| Top-20檔案順序完全一致 | 30／30 |
| 檢索分數完全一致 | 30／30 |

這項檢查的用途是確認目前程式仍能重現方法選擇時的結果，不是再次調整模型，也不是新的準確率實驗。

## 四、新Final Holdout如何建立？

資料來源為官方`princeton-nlp/SWE-bench`的train split。選取規則只使用Ticket ID與Repository名稱，不使用Patch或正確修改檔案作為抽樣條件。

| 檢查項目 | 結果 |
|---|---:|
| 官方來源資料 | 19,008筆 |
| 新Final Holdout | 500筆 |
| Repository數量 | 31個 |
| 與既有2,294筆資料的Ticket重疊 | 0筆 |
| 與既有2,294筆資料的Repository重疊 | 0個 |
| Repository下載準備 | 31／31成功 |
| 不同base commit | 496個 |
| 可取得的base commit | 496／496 |

Repository完全不重疊，讓最後結果可以用來觀察模型面對未見專案時的泛化能力，而不只是面對同一專案的新Ticket。

## 五、如何避免誤用Final Holdout？

- 封存答案與模型輸入分開保存。
- 評估前狀態為`prepared_not_evaluated`；後續一次性評估狀態為`holdout_evaluated_once_output_contract_failed`。
- runner執行前會檢查方法參數、Ticket、封存答案與主要程式的SHA-256雜湊。
- 只允許寫入固定的Final Holdout輸出目錄。
- 正式完成紀錄一旦存在，runner會拒絕再次執行。
- 預測全部完成後，才可由完成程式讀取封存答案並計算一次正式指標。

最終凍結編號：`stage1-v2-9db2a1fbec61bf3d`

原凍結編號`stage1-v2-489d77c4473801a3`在執行前被取代，原因是預檢發現舊runner會先載入Gold。新版runner改為所有預測完成後才讀取封存答案，並以相同30筆確認Top-20順序及分數完全一致後重新凍結。

## 六、已產生的重現檔案

| 檔案 | 用途 |
|---|---|
| `stage1_v2_pre_holdout_freeze.json` | 保存正式方法、驗證依據、資料與程式雜湊 |
| `base_commit_preflight.json` | 保存31個Repository與496個base commit的可用性檢查 |
| `final_holdout_manifest.json` | 保存Final Holdout來源、選取規則與防洩漏檢查 |
| `repository_prefetch_manifest.json` | 保存Repository準備結果 |
| `final_holdout_tickets.jsonl` | 一次性評估的500筆模型輸入 |
| `sealed/final_holdout_gold.jsonl` | 封存的正確修改檔案，只能在預測完成後評估使用 |

所有路徑均以專案根目錄為基準，不綁定單一電腦的絕對路徑。

## 七、目前完成度與唯一下一步

- [x] E6正式方法已選定。
- [x] 30筆重現性檢查通過。
- [x] 方法、資料及主要程式雜湊已凍結。
- [x] 500筆跨Repository Final Holdout已建立。
- [x] 31個Repository與496個base commit均可用。
- [x] Final Holdout已執行一次，500筆預測成功、失敗0筆。
- [x] 最終觀察結果已產生。
- [ ] Top-20輸出契約未完全通過：497筆恰好20個候選，3筆只有7、7、18個候選。

本Final Holdout已使用凍結編號`stage1-v2-9db2a1fbec61bf3d`執行一次，不得再依結果修改參數或重跑。若要修正Top-20輸出問題，需另建E7與新的未見Holdout。
