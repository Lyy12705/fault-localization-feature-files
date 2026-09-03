# E3-B Symbol Definition Expansion：實作與Smoke Test紀錄

## 本次完成範圍

本次完成E3的第一個實驗版本E3-B，目標是將Ticket中明確出現的程式名稱，對應到修正前Repository中真正定義該名稱的檔案。

已完成：

1. 從Ticket抽取反引號、函式呼叫、snake_case、CamelCase與點號形式的程式名稱。
2. 在Code Index建立`Symbol名稱 → 定義檔案`對照，並支援JSON保存與舊Index載入。
3. 在TF-IDF候選池形成前加入有限度的Symbol definition加分。
4. 在每個候選的`scoring_signals`與`stage1_diagnostics`保存原始名稱、對應Symbol、定義檔案與加分來源。
5. 在完整實驗執行器加入`e3-a-baseline`與`e3-b-symbol-definitions`方法。

尚未完成E3-C的API重新匯出與wrapper擴充，也尚未執行正式500筆Validation。

## 防止無關擴充的限制

- 一張Ticket最多保留20個程式名稱。
- 一個名稱若對應超過4個檔案，就不加分。
- 同一Ticket名稱對同一檔案最多加分一次。
- 單一檔案最多保存4項擴充證據。
- 完整名稱加分0.06，僅葉節點名稱加分0.04，總加分上限0.10。
- `bug_report`、`description`與`expected_behavior`等資料欄位名稱不視為程式Symbol。
- 只讀取Ticket與base commit的Code Index，不讀取Gold、Patch或修正後程式碼。

以上權重是第一次Development實驗前固定的工程假設，不是文獻提供的權重，也尚未被正式Validation證明有效。

## 自動化驗證

- 單元測試：48項全部通過。
- 新增E3測試：3項。
- 程式語法檢查：通過。
- 實驗執行器已能選擇`e3-a-baseline`與`e3-b-symbol-definitions`。

## 30筆Smoke Test

Smoke test使用Validation前30筆，只作整合與輸出檢查，不作正式方法選擇，也沒有使用Holdout。

| 指標 | E3-A基準 | E3-B Symbol definitions | 初步差異 |
|---|---:|---:|---:|
| Hit@20 | 90.00% | 96.67% | +6.67百分點 |
| Recall@20 | 84.52% | 86.83% | +2.30百分點 |
| Top-1 | 60.00% | 66.67% | +6.67百分點 |
| MRR（前5檔案） | 0.6694 | 0.7444 | +0.0750 |
| 完全／部分／未命中 | 23／4／3 | 23／6／1 | 未命中減少2筆 |

執行完整性：

- 30筆全部成功，失敗0筆。
- 每筆都有20個不重複候選檔案。
- 29筆抽到至少一個程式名稱。
- 26筆在前20候選中保留Symbol definition證據。

這30筆結果方向正面，但樣本只包含Astropy與Django，且沒有計算正式的500筆成對95%信賴區間，因此不能據此宣稱E3-B已通過驗收。

## 下一步

先在Development檢查E3-B的錯誤擴充案例與參數，再固定設定。設定固定後，才在相同500筆Validation完整比較E3-A與E3-B並計算10,000次成對bootstrap 95%信賴區間。

## 結果檔案

- `reports/fault_localization/stage1_next_iteration/e3_b_smoke_30/test_predictions.jsonl`
- `reports/fault_localization/stage1_next_iteration/e3_b_smoke_30/test_metrics.json`
- `reports/fault_localization/stage1_next_iteration/e3_b_smoke_30/test_failures.jsonl`
- `reports/fault_localization/stage1_next_iteration/e3_b_smoke_30/test_run_manifest.json`
