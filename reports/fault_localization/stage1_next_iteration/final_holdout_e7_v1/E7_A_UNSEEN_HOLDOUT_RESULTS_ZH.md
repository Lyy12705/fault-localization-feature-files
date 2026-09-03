# E7-A 全新未見 Holdout 一次性評估結果

## 一、結論

E7-A 已在全新且Repository完全未見的Holdout執行一次。27筆皆完成預測、執行失敗0筆，且所有預測寫入後才解封Gold。原始結果為Hit@20 70.37%、Recall@20 62.63%、Top-1 40.74%、MRR 0.5031。

本次不可標記為正式輸出契約通過：只有20/27筆恰好產生20個候選，另有7筆候選不足。不可重跑紀錄已封存為`holdout_evaluated_once_output_contract_failed`。這批Holdout不得再用於修正後重跑或方法選擇。

## 二、為何只有27筆

資料來源為官方SWE-bench train split，共19,008筆。排除所有先前使用的2,794筆Ticket與其43個Repository後，只剩27筆、4個Repository：

| Repository | Ticket數 |
|---|---:|
| JohnSnowLabs/spark-nlp | 3 |
| apache/mxnet | 5 |
| kubeflow/pipelines | 14 |
| python/typeshed | 5 |

這27筆是該來源中全部剩餘的Repository-disjoint資料；沒有用舊Repository補足500筆。Ticket重疊為0、Repository重疊為0、Ticket ID全數唯一。選取只使用`instance_id`與Repository，不使用patch或Gold內容。

限制：樣本只有27筆且分布集中於4個Repository，信賴區間較寬，不足以單獨代表一般化表現。

## 三、凍結與執行順序

- 固定方法：E7-A／`e7-a-e6-development-baseline`。
- 方法ID：`tfidf-sbert-rerank-25ae3013f48f`。
- 凍結ID：`stage1-e7-047d563271a0fa02`。
- 方法設定：固定50個語意候選、SBERT重排、Symbol/API擴充、Call Graph outgoing Top-3，最終要求20個唯一檔案。
- 預檢：4/4個Repository準備完成，27/27個base commit可達；預檢未開啟Gold。
- 凍結前測試：111項單元測試全數通過。
- 執行順序：先以prediction-only shard產生27/27筆預測並寫入檔案；確認0失敗後才讀取封存Gold與計算指標。
- 正式執行時間：173.249秒。

## 四、原始評估結果

| 指標 | 結果 | 95% bootstrap CI |
|---|---:|---:|
| Hit@20 | 70.37% | 51.85%～85.19% |
| Recall@20 | 62.63% | 45.04%～79.63% |
| Top-1 | 40.74% | — |
| Top-3 | 59.26% | — |
| Top-5 | 62.96% | — |
| MRR | 0.5031 | — |

結果分布為15筆完全找回、4筆部分找回、8筆未命中。這些數字是一次性觀察結果；因輸出契約未通過，不視為正式成功驗收。

### Repository分組

| Repository | 筆數 | Hit@20 | Recall@20 | Top-1 | MRR |
|---|---:|---:|---:|---:|---:|
| JohnSnowLabs/spark-nlp | 3 | 0.00% | 0.00% | 0.00% | 0.0000 |
| apache/mxnet | 5 | 100.00% | 83.20% | 60.00% | 0.7000 |
| kubeflow/pipelines | 14 | 71.43% | 66.07% | 28.57% | 0.4345 |
| python/typeshed | 5 | 80.00% | 70.00% | 80.00% | 0.8000 |

輔助的base-commit可達Gold評估涵蓋22筆，Hit@20為86.36%、Recall@20為79.48%。另有31個Gold檔案在對應base commit不存在，因此這項只作診斷，主要指標仍採原始Gold定義。

## 五、輸出契約結果

| 候選數 | Ticket數 |
|---:|---:|
| 20 | 20 |
| 19 | 3 |
| 1 | 1 |
| 0 | 3 |

7筆不足20個候選：spark-nlp的3筆為0個；typeshed有3筆為19個、1筆為1個。全體平均候選數為16.963。標準封存器因此拒絕`holdout_evaluated_once`，改以輸出契約失敗狀態封存。

## 六、與Development的描述性差異

| 指標 | E7-A Development（1,294筆） | 新Holdout（27筆） |
|---|---:|---:|
| Hit@20 | 92.50% | 70.37% |
| Recall@20 | 87.89% | 62.63% |
| Top-1 | 56.11% | 40.74% |
| MRR | 0.6658 | 0.5031 |

此差異同時受全新Repository組成、27筆小樣本、Gold在base commit不可達，以及7筆候選不足影響，不能解讀為單一元件造成的因果退步。

## 七、不可重跑決策與後續

- 本Holdout已評估一次，不得以相同E7-A重跑。
- 若修正非Python／稀疏Python Repository的候選輸出，必須使用新實驗ID與另一個未見資料來源評估。
- 官方train split的Repository-disjoint剩餘資料已全部用完；下一輪須先取得新的外部未見資料，不能再從本批27筆抽測。

## 八、正式產物

- `stage1_e7_pre_holdout_freeze.json`：E7-A、資料、程式與唯一輸出位置的凍結紀錄。
- `base_commit_preflight.json`：27個base commit可達性證據。
- `run/predictions.jsonl`：27筆固定方法預測。
- `run/metrics.json`：原始指標、信賴區間與Repository分組。
- `run/run_manifest.json`：prediction-before-gold執行順序與完整方法設定。
- `FINAL_HOLDOUT_E7_V1_RECORD.json`：不可重跑及輸出契約失敗的最終紀錄。
