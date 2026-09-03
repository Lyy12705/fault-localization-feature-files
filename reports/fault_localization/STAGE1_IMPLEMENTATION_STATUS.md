# Stage 1 錯誤定位：實作與初步驗證狀態

日期：2026-08-15

## 結論

第一階段已具備可獨立執行、保存與評估的明確邊界。預設流程為：

```text
Ticket production fields
  -> repository code chunks
  -> TF-IDF + stack/path/keyword/symbol/domain signals
  -> optional SBERT rerank of Top 50 chunks
  -> file aggregation
  -> Stage-1 Top 20 files (saved before any LLM rerank)
```

正式輸出欄位是 `stage1_candidate_files`，評估欄位是
`candidate_hit_at_20` 與 `candidate_recall_at_20`。最終 Top-K 的
`localized_files` 不再被拿來代替第一階段候選。

## 本次改進

1. 新增 `candidate_file_k=20`，並串接 localizer、CLI 與 SWE-bench runner。
2. 在任何 LLM rerank 前保存 Top-20 file candidates 與每一筆 scoring evidence。
3. 新增 Candidate Hit@20、Candidate Recall@20、平均候選數，以及 full/partial/miss 分類。
4. 排除 ticket ID、benchmark hints、failing-test labels 與重複文字，避免資料洩漏或不合理加權。
5. 新增 domain-path routing，將 Ticket 中的框架概念對應到可能的 source region；觸發原因會寫入 `matching_domain_intents`。
6. 方法版本升為 `fault-localization-method-v6`，避免舊 prediction 被 resume 混入。

## 初步結果

| 資料 | 用途 | Candidate Hit@20 | Candidate Recall@20 | Full / Partial / Miss | File Hit@5 |
|---|---|---:|---:|---:|---:|
| Development 1–30，改進前 | miss 分析基準 | 0.800 | 0.800 | 24 / 0 / 6 | 0.667 |
| Development 1–30，改進後 | 同批 before/after | 1.000 | 1.000 | 30 / 0 / 0 | 0.767 |
| Development 31–60 | 未查看的初步驗證 | 1.000 | 1.000 | 30 / 0 / 0 | 0.900 |
| 7-repository smoke | 跨專案執行檢查 | 1.000 | 1.000 | 7 / 0 / 0 | 0.857 |

所有 run 都是 0 failure，且每張 Ticket 都輸出 20 個候選檔案。

## 正確判讀

- Candidate Hit@20 = 1.00：每張 Ticket 的 Top 20 至少包含一個正確修改檔案。
- Candidate Recall@20 = 1.00：每張 Ticket 的所有正確修改檔案平均都被 Top 20 找回。
- 本批資料的 gold 都是單一修改檔案，所以 Hit@20 與 Recall@20 數值相同；多檔案 patch 時才會分開。
- File Hit@5 是第一階段候選經排序後的前五名命中率，不應與 Candidate Hit@20 混用。

## 限制與下一個決策點

Development 1–30 是用來分析並修正 miss 的資料，因此改進後的 1.00 只能證明「已知錯誤被修復」，不能證明泛化。Development 31–60 與跨 repository smoke 提供初步支持，但樣本仍小。

製作教授簡報前應完成：

1. 跑完整 frozen development set，依 repository 分層報告 Hit/Recall@20。
2. 固定所有權重與規則後，只執行一次 frozen holdout。
3. 報告 bootstrap 95% confidence interval，並列出 Top-20 miss case。
4. 比較 TF-IDF baseline 與 `Top 50 TF-IDF chunks -> SBERT -> Top 20 files`，確認 SBERT 是否真正提高 Recall@20。

## 可稽核產物

- 改進前 metrics：`stage1_preliminary_tfidf_30/test_metrics.json`
- 改進後 metrics：`stage1_improved_tfidf_30/test_metrics.json`
- before/after 比較：`stage1_improved_tfidf_30/before_after_comparison.json`
- 未查看 validation：`stage1_validation_tfidf_30_offset30/test_metrics.json`
- 跨 repository smoke：`stage1_cross_repo_smoke/test_metrics.json`
