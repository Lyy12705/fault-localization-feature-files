# E3-B點號名稱Leaf Fallback改進實驗

## 實驗目的

第一輪30筆Development證據檢查發現，`self.version`、`other.version`與`printer.flush`等點號名稱，會在完整名稱找不到定義時，直接退回最後一段名稱，並對Repository內無關的同名Method加分。

本次只調整點號名稱的leaf fallback規則，其餘Ticket、Code Index、TF-IDF、SBERT、候選數量與檔案聚合設定完全相同。沒有使用Holdout。

## 三種規則

| 版本 | 點號名稱Leaf Fallback規則 |
|---|---|
| Legacy | 完整名稱找不到時，直接使用最後一段名稱 |
| Strict | 完全禁止點號名稱退回最後一段 |
| Guarded | 阻止receiver、單字過短與泛用名稱；保留具辨識力的API名稱 |

Guarded會阻止以下類型：

- Receiver開頭：`self`、`other`、`cls`、`super`。
- 單字母receiver，例如`q.decompose`的`q`。
- 最後一段少於5個字元。
- `version`、`name`、`copy`、`write`、`view`、`group`、`flush`等泛用名稱。

完整Symbol能在Index直接找到時不受此規則影響。

## 相同40筆Development結果

| 方法 | Hit@20 | Recall@20 | Top-1 | Top-3 | Top-5 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 100.00% | 95.54% | 77.50% | 90.00% | 95.00% | 0.8404 |
| Strict | 100.00% | 95.54% | 72.50% | 87.50% | 90.00% | 0.7967 |
| Guarded | 100.00% | 95.54% | 75.00% | 87.50% | 95.00% | 0.8217 |

三種方法的Hit@20與Recall@20相同，表示本次規則修改沒有改變40筆中的Top-20找回結果。Strict的Top-1下降5個百分點；Guarded的Top-1下降2.5個百分點。

## 相同30筆證據案例結果

三份報告使用相同seed `20260822`，並確認30個Ticket ID完全一致。

| 方法 | 正確對應 | 名稱過度模糊 | 錯誤對應 | Gold證據檔案 | 非Gold證據檔案 | Leaf證據列 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 6 | 19 | 5 | 26 | 75 | 87 |
| Strict | 8 | 14 | 8 | 23 | 49 | 20 |
| Guarded | 8 | 17 | 5 | 26 | 55 | 45 |

相較Legacy，Guarded：

- 保留全部26個Gold證據檔案，沒有遺失Gold證據。
- 非Gold證據檔案由75降為55，減少20個（26.7%）。
- Leaf證據由87列降為45列，減少42列（48.3%）。
- 正確對應由6筆增加為8筆；過度模糊由19筆降為17筆；錯誤對應維持5筆。

Strict雖然移除更多噪音，但同時遺失3個Gold證據檔案，並使錯誤對應由5筆增加為8筆，因此不採用Strict作為下一輪正式候選。

## 本輪決定

保留`symbol-definitions-guarded`作為下一輪500筆Validation候選，並保留Legacy作對照組。Guarded在本次小樣本中成功減少無關擴充且沒有遺失Gold證據，但Top-1與MRR仍低於Legacy，必須以完整Validation及成對信賴區間決定是否正式取代Legacy。

本次40筆與30筆案例都只包含`astropy/astropy`，不能宣稱具有跨Repository泛化效果，也不能取代正式500筆Validation。

## 結果檔案

- Legacy 40筆：`reports/fault_localization/stage1_next_iteration/e3_b_development_evidence_pool_40/`
- Strict 40筆：`reports/fault_localization/stage1_next_iteration/e3_b_strict_development_evidence_pool_40/`
- Guarded 40筆：`reports/fault_localization/stage1_next_iteration/e3_b_guarded_development_evidence_pool_40/`
- Strict 30筆證據表：`reports/fault_localization/stage1_next_iteration/e3_b_strict_evidence_review_30/`
- Guarded 30筆證據表：`reports/fault_localization/stage1_next_iteration/e3_b_guarded_evidence_review_30/`
