# WP3 呼叫關係擴展固定設定實驗

決策：實驗已完成，未採用 call-neighborhood-v1；保留 coverage-aware-v1。

## 固定規則

沿用相同 Stage-2 Top-5、B1 排序分數與候選池。保留 global prefix 與每檔 module 名額，以最多 5 個名額替代原本 class-family expansion。依 prefix 順序，每個非 module anchor 補入一個尚未選入的一跳 caller 或 callee；多個目標依原 B1 排序，名額不足則 global backfill。新加入的目標不再成為 anchor。

重用 build_call_graph，從候選池的 source chunks 重建靜態呼叫圖。只使用池內可解析目標，不使用 gold、patch 或 LLM；設定在評分前固定，評分後未調參。這個實驗測試的是「ticket 排序所得 anchor 的呼叫鄰居」，不是新增 ticket-to-symbol 學習模型。

限制：候選 source chunks 不一定含完整檔案，動態派送與無法解析的 import 可能缺邊；既有解析器並非完整 Python 語意分析。結果只適用於這個固定實作。development set 已用於多次探索，本結果並非獨立 holdout 驗證。

## 結果

61 筆 development tickets，46 筆 conditional eligible，137 個 conditional gold symbols。

| 指標 | coverage-aware-v1 | call-neighborhood-v1 |
|---|---:|---:|
| Conditional Exact Candidate Recall@30 | 68.64% | 66.02% |
| Conditional Hit@30 | 89.13% | 91.30% |
| Exact symbol hits | 88 | 84 |
| Pool-reachable ranking misses | 30 | 34 |

逐筆配對保留 82 個命中、找回原 30 個 misses 中的 2 個、失去 6 個既有命中。原 30 個 misses 尚有 28 個未找回；加上 6 個新 misses，實驗 variant 共 34 個。Hit@30 雖提升，主要採用指標 Recall@30 下降 2.62 個百分點，因此保留原 baseline，其 ranking misses 仍為 30 個。

AST pool oracle 維持 90.41%，G2 未通過，WP4 尚未開始。187/187 測試通過，包含雙向呼叫擴展、排除純文字提及、可達性分類與無邊主因分類。

## 剩餘 30 個 misses 的呼叫圖可達性

| 分類 | 數量 | 意義 |
|---|---:|---|
| Prefix 一跳可達 | 3 | 1 個由呼叫擴展找回；2 個受名額或每-anchor 競爭排除 |
| 只連到 prefix 外候選 | 5 | 呼叫圖有邊，但目前 anchor 覆蓋不到 |
| 無已解析 incident edge | 22 | 目前靜態圖沒有可用呼叫證據 |

call variant 找回的 2 個 misses 中，只有 1 個有 prefix call edge；另 1 個是選取與 global backfill 改變造成，不能算成呼叫擴展的收益。22 個無邊案例不等於執行時沒有呼叫關係：候選 source 不完整、動態派送與 import 解析限制都可能造成缺邊。逐筆證據位於 `call_reachability_details.csv`，摘要位於 `CALL_REACHABILITY_REPORT_ZH.md` 與 `call_reachability_analysis.json`。

## 重現

```powershell
python scripts/run_stage3_deterministic_g2.py --config configs/fault_localization/stage3_call_neighborhood_v1.json
python scripts/analyze_stage3_symbol_pool_oracle.py --config configs/fault_localization/stage3_call_neighborhood_v1.json --variant b1_call_neighborhood_v1
python scripts/compare_stage3_oracle_outcomes.py --baseline reports/fault_localization/stage3_deterministic_g2_dev_v1/oracle_symbol_classification.csv --experiment reports/fault_localization/stage3_call_neighborhood_dev_v1/oracle_symbol_classification.csv --output reports/fault_localization/stage3_call_neighborhood_dev_v1/paired_symbol_outcomes.csv
python scripts/analyze_stage3_call_reachability.py
```

REPORT_ZH.md 記錄比較後選定 baseline；ORACLE_REPORT_ZH.md 診斷未採用的 call variant。paired_symbol_outcomes.csv 保留全部 conditional gold 的前後狀態，summary.json 保存設定及輸入雜湊。

## 22 個無邊案例審核

base-commit source 與目標定義 22/22 完整存在；reconstructed source 22/22 可解析且能找到目標。完整 repository index graph 在 21 個案例有 incident edge，其中 20 個案例的相鄰 symbol 也在 Stage-2 candidate pool。主因分類如下：

| 主因 | 數量 |
|---|---:|
| 同檔 source／graph reconstruction loss | 15 |
| 跨檔 import resolution loss | 5 |
| Stage-2 candidate-pool scope | 1 |
| Dynamic dispatch | 1 |
| 確實無靜態呼叫證據 | 0 |

因此主要問題不是 base source 缺失，而是 call-neighborhood-v1 從 symbol-only candidate pool 重新建圖時丟失既有邊。完整逐筆分類位於 `NO_EDGE_AUDIT_ZH.md` 與 `no_edge_case_audit.csv`。

下一個行動：建立 call-neighborhood-v2，直接使用 index 已保存的 repository-level call graph，再以 candidate-pool identities 過濾 caller/callee。
