# WP3 Call-neighborhood-v2 固定設定實驗

決策：v2 已完成並驗證，但不採用；選定 baseline 維持 `coverage-aware-v1`。

## 固定設定

- 沿用相同的 61 筆 development tickets、Stage-2 Top-5、B1 分數與 Top-30 上限。
- 保留 global prefix 與每個 Stage-2 檔案的 module 名額，最多配置 5 個一跳 caller／callee 擴展名額。
- 直接讀取 `CodeIndex.call_graph` 的 repository-level 呼叫圖；若舊 index 沒有保存呼叫圖，使用完整 index chunks 與 symbol definitions 建立一次。
- anchor 與擴展目標都必須存在於目前 Stage-2 Top-5 symbol candidate pool；多個目標依原 B1 排序決定。
- 設定在評分前固定；不使用 gold、patch 或 LLM，評分後未調參。

## 結果

61 筆 development tickets，46 筆 conditional eligible，137 個 conditional gold symbols。

| 指標 | coverage-aware-v1 | call-neighborhood-v1 | call-neighborhood-v2 |
|---|---:|---:|---:|
| Conditional Exact Candidate Recall@30 | **68.64%** | 66.02% | 68.20% |
| Conditional Hit@30 | 89.13% | 91.30% | 89.13% |
| Exact symbol hits | **88** | 84 | 87 |
| Pool-reachable ranking misses | **30** | 34 | 31 |

v2 相較 v1 增加 2.18 個 Recall@30 百分點，證實完整索引圖修復了 symbol-only graph reconstruction 的主要缺邊問題。相較選定 baseline，v2 保留 83 個命中、找回原 30 個 ranking misses 中的 4 個、失去 5 個既有命中；原 misses 尚有 26 個未找回，另產生 5 個新 misses，淨結果少 1 個 exact hit。因主要指標由 68.64% 降至 68.20%，不採用 v2。

AST pool oracle 維持 90.41%；G2 仍未達 90%，WP4 尚未開始。完整測試 188/188 通過。

## 重現與證據

```powershell
python scripts/run_stage3_deterministic_g2.py --config configs/fault_localization/stage3_call_neighborhood_v2.json
python scripts/analyze_stage3_symbol_pool_oracle.py --config configs/fault_localization/stage3_call_neighborhood_v2.json --variant b1_call_neighborhood_v2
python scripts/compare_stage3_oracle_outcomes.py --baseline reports/fault_localization/stage3_deterministic_g2_dev_v1/oracle_symbol_classification.csv --experiment reports/fault_localization/stage3_call_neighborhood_dev_v2/oracle_symbol_classification.csv --output reports/fault_localization/stage3_call_neighborhood_dev_v2/paired_symbol_outcomes.csv
```

`REPORT_ZH.md` 保存五個 variants 的比較；`ORACLE_REPORT_ZH.md` 保存 v2 loss decomposition；`paired_symbol_outcomes.csv` 保存逐 symbol 的 retained／recovered／lost／still-missed 狀態；`summary.json` 保存設定與輸入雜湊。

下一個行動：逐筆分析 v2 的 4 個 recoveries 與 5 個 losses，固定能保留 class-family coverage 的 guarded call expansion 規則。
