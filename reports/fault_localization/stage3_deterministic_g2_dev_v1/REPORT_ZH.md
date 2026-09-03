# Stage-3 Deterministic Candidate G2（Development v1）

- 狀態：FAIL
- 選定設定：`b1_structured`
- Conditional Exact Candidate Recall@30：58.65%
- G2 門檻：90%
- Eligible tickets：46
- Development tickets：61

## 比較結果

| Variant | Mode | Quota | Eligible | Hit@10 | Recall@10 | Hit@30 | Recall@30 | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `b0_tfidf` | `b0-tfidf` | 0 | 46 | 65.22% | 41.44% | 84.78% | 57.81% | 100.00% |
| `b1_structured` | `b1-structured` | 0 | 46 | 73.91% | 47.06% | 89.13% | 58.65% | 100.00% |
| `b1_structured_q4` | `b1-structured` | 4 | 46 | 67.39% | 43.43% | 86.96% | 57.26% | 100.00% |
| `b1_structured_q6` | `b1-structured` | 6 | 46 | 69.57% | 44.16% | 82.61% | 52.43% | 100.00% |
| `b1_structured_q8` | `b1-structured` | 8 | 46 | 73.91% | 46.81% | 84.78% | 54.41% | 100.00% |

## 決策

G2 未通過；維持 WP3，先改善 deterministic candidate retrieval，不調整 LLM prompt。

本報告只使用 development data，且所有 variant 共用同一份已保存的 Stage-2 Top-5；沒有呼叫 LLM。
