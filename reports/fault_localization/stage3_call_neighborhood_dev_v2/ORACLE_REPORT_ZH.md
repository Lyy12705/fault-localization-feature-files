# Stage-3 AST Symbol Pool Exact Oracle（Development v1）

- 診斷 variant：`b1_call_neighborhood_v2`
- Conditional eligible Tickets：46
- Conditional gold symbols：137
- Stage-2 file oracle macro recall：93.12%
- AST pool exact oracle macro recall：90.41%
- 實際 Top-30 macro recall：68.20%
- Pool 可達時 Top-30 micro recall：73.73%

## Loss decomposition

| Loss | 百分點 |
|---|---:|
| Stage-2 未涵蓋全部 gold files | 6.88% |
| AST／candidate policy 在已找到檔案後仍不可達 | 2.72% |
| Pool 已可達但掉出 Top-30 | 22.21% |

## Gold symbol 分類（conditional rows）

| 分類 | 數量 |
|---|---:|
| `pool_identity_mismatch` | 2 |
| `stage2_file_miss` | 17 |
| `top30_exact_hit` | 87 |
| `top30_ranking_miss` | 31 |

## 決策

主要 blocker：`top30_ranking_miss`。
AST pool oracle 已達 90%，下一輪只需改善 Top-30 排序。

本分析只讀取 development artifacts 與 base-commit indexes，沒有呼叫 LLM。
