# WP3 Source-neighborhood 固定設定實驗

決策：保留 coverage-aware-v1。source-neighborhood-v1 已完成驗證但未採用。

## 評分前固定的設定

- 共用既有 Stage-2 Top-5、B1 分數與 development tickets。
- 保留 global prefix 與每檔一個 module；最多五個擴展名額。
- 依 prefix 順序，每個 anchor 補入一個同檔、互不重疊、間距不超過 100 行的最近定義；同距離依原排序決定。
- 不使用 gold、patch 或評分結果作為選取特徵；評分後未調參。
- 這是已多次使用的 development set 上的探索性比較，並非獨立 holdout 驗證。

## 結果

61 筆 development tickets，46 筆 conditional eligible；137 個 conditional gold symbols。

| 指標 | coverage-aware-v1 | source-neighborhood-v1 |
|---|---:|---:|
| Conditional Exact Candidate Recall@30 | 68.64% | 64.70% |
| Conditional Hit@30 | 89.13% | 86.96% |
| Exact symbol hits | 88 | 82 |
| Pool-reachable ranking misses | 30 | 36 |

逐筆配對：保留 81 個命中、找回原 30 個 misses 中的 1 個、失去原有 7 個命中。原 30 個 misses 尚有 29 個未找回；加上新失去的 7 個，實驗 variant 共 36 個 ranking misses。這不能解讀為部署後只剩 29 個 misses。

AST pool oracle 不變，G2 仍未達 90%。選定 baseline 維持 coverage-aware-v1 的 68.64% 與 30 個 ranking misses。全套測試 184/184 通過，包括同檔限制、100 行邊界與重疊排除。

## 重現

```powershell
python scripts/run_stage3_deterministic_g2.py --config configs/fault_localization/stage3_source_neighborhood_v1.json
python scripts/analyze_stage3_symbol_pool_oracle.py --config configs/fault_localization/stage3_source_neighborhood_v1.json --variant b1_source_neighborhood_v1
python scripts/compare_stage3_oracle_outcomes.py --baseline reports/fault_localization/stage3_deterministic_g2_dev_v1/oracle_symbol_classification.csv --experiment reports/fault_localization/stage3_source_neighborhood_dev_v1/oracle_symbol_classification.csv --output reports/fault_localization/stage3_source_neighborhood_dev_v1/paired_symbol_outcomes.csv
```

本目錄 REPORT_ZH.md 記錄比較後選定 baseline；ORACLE_REPORT_ZH.md 明確診斷未採用的 b1_source_neighborhood_v1；paired_symbol_outcomes.csv 保留全部 conditional gold 的前後狀態。

下一個研究動作：在 WP3 評估 ticket-to-symbol 呼叫關係證據是否能提供比單純原始碼距離更有效的擴展依據，先固定假設與設定再執行評分。
