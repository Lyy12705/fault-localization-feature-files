# Stage-3 Deterministic Candidate G2（Development v1）

- 狀態：FAIL
- 選定設定：`b1_coverage_aware_v1`
- Conditional Exact Candidate Recall@30：68.64%
- G2 門檻：90%
- Eligible tickets：46
- Development tickets：61

## 比較結果

| Variant | Retrieval | Selection | Quota | Eligible | Hit@10 | Recall@10 | Hit@30 | Recall@30 | Coverage |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `b0_tfidf` | `b0-tfidf` | `global` | 0 | 46 | 67.39% | 41.80% | 86.96% | 60.60% | 100.00% |
| `b1_structured` | `b1-structured` | `global` | 0 | 46 | 76.09% | 47.80% | 91.30% | 64.36% | 100.00% |
| `b1_coverage_aware_v1` | `b1-structured` | `coverage-aware-v1` | 0 | 46 | 76.09% | 47.80% | 89.13% | 68.64% | 100.00% |
| `b1_call_neighborhood_v1` | `b1-structured` | `call-neighborhood-v1` | 0 | 46 | 76.09% | 47.80% | 91.30% | 66.02% | 100.00% |

## 決策

G2 未通過；維持 WP3，先改善 deterministic candidate retrieval，不調整 LLM prompt。

本報告只使用 development data，且所有 variant 共用同一份已保存的 Stage-2 Top-5；沒有呼叫 LLM。
