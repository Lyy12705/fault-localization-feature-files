# E8-A SWE-bench-Live 全新未見 Holdout 一次性結果

## 一、結論

E8-A已完成一次性外部Holdout評估。100筆皆產生預測、執行失敗0筆，全部預測寫入後才解封Gold。原始結果為Hit@20 89.00%、Recall@20 68.89%、Top-1 54.00%與MRR 0.6143。

輸出契約從前一輪20/27筆完整（74.07%）提升為98/100筆完整（98.00%），但仍有2筆不足20個候選，因此不得標記為正式契約通過。結果已封存為`holdout_evaluated_once_output_contract_failed`，不得重跑或用於同一Holdout上的調參。

## 二、E8-A修正範圍

前一輪候選不足的診斷顯示：

- `JohnSnowLabs/spark-nlp`主要包含Scala來源，但舊Code Index不支援`.scala`。
- `python/typeshed`主要包含Python stub，但舊Code Index不支援`.pyi`。

E8-A只新增`.scala`與`.pyi`來源索引，並將index／method版本更新為v3／v20。TF-IDF候選數、SBERT重排、Symbol/API擴充、Call Graph Top-3與所有排序權重均維持E7-A設定。新方法標籤為`e8-a-source-extension-contract`，方法ID為`tfidf-sbert-rerank-a075b6f2b2d3`。

## 三、全新外部Holdout

資料來源為[SWE-bench-Live](https://huggingface.co/datasets/SWE-bench-Live/SWE-bench-Live)，固定於dataset commit `a3165f4df45702cdcb7225e70403d055f74d9d01`的Verified split：

- Verified來源：500筆、100個Repository。
- 排除所有先前2,821筆Ticket與47個Repository後：382筆、91個Repository仍符合未見條件。
- 盲選100筆、53個Repository；Ticket重疊0、Repository重疊0、Ticket ID全數唯一。
- 抽樣只使用`instance_id`與Repository，不使用patch或Gold內容。
- 固定parquet SHA-256：`080e36e46198bf9c177a6b077624d4028baf6ff04d661c332cc1fe1e5dfa50b2`。

## 四、凍結與執行證據

- 凍結ID：`stage1-e8-f7c5881d1a673480`。
- 53/53個Repository準備完成。
- 100/100個base commit可達；預檢未開啟Gold。
- 凍結前119項單元測試全數通過。
- prediction phase曾因commit cache缺少永久ref與Windows long-path設定而在0/100及99/100安全停止；兩次均未開啟Gold。
- 修復只調整Repository cache/ref與Git執行環境，沒有變更凍結方法、Ticket、Gold或排序程式；續跑會保留已完成預測。
- 最終100/100筆預測、0失敗，之後才開啟封存Gold評估。

## 五、原始評估結果

| 指標 | 結果 | 95% bootstrap CI |
|---|---:|---:|
| Hit@20 | 89.00% | 83.00%～94.00% |
| Recall@20 | 68.89% | 61.77%～75.50% |
| Top-1 | 54.00% | — |
| Top-3 | 68.00% | — |
| Top-5 | 73.00% | — |
| MRR | 0.6143 | — |

結果分布為51筆完全找回、38筆部分找回、11筆未命中。100筆都有base-commit可達Gold；排除22個在base commit不存在的Gold檔案後，輔助Recall@20為74.78%，主要指標仍採原始Gold定義。

## 六、輸出契約

| 候選數 | Ticket數 |
|---:|---:|
| 20 | 98 |
| 17 | 1 |
| 4 | 1 |

不足20個候選的兩筆為：

| Ticket | Repository | 候選數 | Index chunks |
|---|---|---:|---:|
| `jarun__buku-778` | jarun/buku | 17 | 725 |
| `networktocode__ntc-templates-2115` | networktocode/ntc-templates | 4 | 35 |

這兩個Repository顯示「支援的來源檔案數少於20」仍會使固定Top-20契約無法成立；其中`ntc-templates`以文字模板為主要內容。此觀察只作下一個Development實驗的問題定義，不得在本Holdout修正後重跑。

## 七、正式決策

- 專題實作版本採用E8-A，因為它完整保留E6的排名設定，並增加`.pyi`與`.scala`來源支援。
- 專題準確率基準仍採E6：E6具有相同500筆Validation的成對比較與500筆Final Holdout；E8使用另一組100筆外部Holdout，因此不得宣稱E8準確率優於E6。
- E8-A明顯改善輸出完整率，但未達100/100的硬性契約，因此不標記為正式驗收通過。
- 本100筆Holdout已使用一次，不得再評估E8-A或其修正版。
- 下一個實驗需在新的Development資料定義「少量程式檔／模板型Repository」的候選政策，再使用另一批Repository-disjoint資料評估。

## 八、研究限制：固定Top-20輸出契約

- 固定契約要求每張Ticket恰好輸出20個不重複候選檔案，但部分小型、stub型或模板型Repository本身不足20個可索引來源檔案，契約在這些Repository上無法成立。
- E6為497／500筆符合契約，E8為98／100筆符合契約；因Holdout不同，這兩個比例只能各自描述，不能作為E6／E8的受控優劣比較。
- 候選不足不等於模型執行失敗；E6與E8的預測執行失敗均為0筆，但兩者都不能標記為固定Top-20契約完全通過。
- 未來可在新的Development實驗評估`min(20, 可索引唯一檔案數)`與`candidate_pool_exhausted`標記，但不得用這項事後規則回頭把本次E8結果改判為通過。

## 九、產物

- `stage1_e8_pre_holdout_freeze.json`：方法、資料、程式與唯一輸出位置凍結紀錄。
- `base_commit_preflight.json`：100個base commit可達證據。
- `run/predictions.jsonl`：100筆E8-A預測。
- `run/metrics.json`：原始指標、信賴區間及Repository結果。
- `run/run_manifest.json`：prediction-before-gold證據。
- `FINAL_E8_HOLDOUT_V1_RECORD.json`：不可重跑與輸出契約失敗紀錄。
