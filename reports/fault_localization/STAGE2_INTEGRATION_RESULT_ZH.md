# 第一、二階段銜接與結果判讀

## 結論

正式結論：**7B 流程接通，但準確率不足，維持 baseline。**

`codellama:7b-instruct` 已能穩定完成 File 與 Symbol rerank，10/10 筆均無
fallback；但正式無 retrieval-score 洩漏的配對實驗中，File Hit@1、Hit@3、Hit@5
與 MRR 均比 baseline 低 0.1。因此目前正式設定保留 retrieval baseline，7B reranker
只作實驗選項，不設為預設流程。

第一階段與後續流程已在目前主程式中接通：

```text
Ticket
  -> Stage 1：Top-20 unique files
  -> Stage 2：Code Llama file rerank / retrieval fallback，保留 Top-5
  -> AST index：只取 Top-5 檔案內的唯一 qualified symbols
  -> Stage 3：Code Llama symbol rerank / symbol-retrieval fallback
```

組員交付的 10 筆既有輸出不能視為 Code Llama 的第二階段成績。每一筆都包含
`LLM reranking returned no usable candidates; retrieval ranking was kept.`，表示 File
Reranker 10/10 都回退到第一階段排序；`stage3_ranked_symbols` 也 10/10 為空。

## 已修正的銜接問題

1. 主流程現在明確保存 `stage1_candidate_files`、`stage2_localized_files` 與
   `stage3_ranked_symbols`，不再混用階段輸出。
2. Stage 2 預設可接收完整 Top-20，而不是原本 CLI 預設的 Top-10。
3. AST symbol 直接取自第一階段 `CodeIndex`。載入後的 portable index 會將
   `repository_path` 記為 `.`，因此不能再用它拼接 snapshot 路徑；這正是組員程式
   產生 0 個 symbol 的主要原因。
4. 相同 file + qualified symbol 的多個長程式 chunk 只保留相關度最高者，避免
   Symbol Top-K 重複出現同一個 class 或 method。
5. File 與 Symbol LLM 都必須回傳完整、有限分數且每個候選恰好一次；否則標記
   fallback，保留 retrieval 結果，不把 fallback 誤報為 LLM 成果。

## 組員 10 筆輸出的正確解讀

| 指標 | 數值 | 判讀 |
|---|---:|---|
| Stage-1 Candidate Hit@20 | 100% | 10 張票的 Top-20 都至少包含一個正確檔案。 |
| Stage-1 Candidate Recall@20 | 86.67% | 多檔案修正案例仍漏掉部分正確檔案。 |
| Full / Partial / Miss | 7 / 3 / 0 | 7 張找齊全部正確檔案，3 張只找回一部分。 |
| File Hit@1 / @3 / @5 | 60% / 70% / 80% | 這是 retrieval fallback 的 Top-5 表現，不是 Code Llama 改善。 |
| Symbol Hit@1 | 0% | 10 筆 `stage3_ranked_symbols` 全空，不能用來主張 Symbol reranker 效果。 |

這 10 筆全部來自 `astropy/astropy`，樣本太小且單一 repository，只能作 smoke
test。`test_metrics_recalculated.json` 使用完整 2,294 筆 gold、但只有 10 筆 prediction，
因此約 0.4% 的指標只是「缺 2,284 筆輸出」造成的 denominator 結果，不能用來代表
模型準確率。

## 整合後 smoke test

以 `astropy__astropy-11693` 與現有 index 測試，在本機沒有 Ollama 的情況下仍得到：

- Stage 1：20 files
- Stage 2：5 files
- Stage 3：5 個不重複 symbols
- `stage3_diagnostics.source = symbol_retrieval_fallback`

前五個 symbol fallback 包含 `WCS.all_world2pix`、`WCS._all_world2pix` 與
`FITSWCSAPIMixin`。這證明資料管線已接通，但不是 LLM 準確率實驗。

### Code Llama 7B 真模型測試（2026-09-02）

安裝 `codellama:7b-instruct`（3.8 GB）後，以同一張
`astropy__astropy-11693` 執行完整流程。兩次模型呼叫均完成，但結果為：

- `method.llm_rerank = false`
- `stage3_diagnostics.llm_rerank_used = false`
- Stage 2 與 Stage 3 均使用 retrieval fallback

File Reranker 的原始回應不是指定的 `{"candidates": [...]}`，而是一個單獨物件；
它還產生不在傳入 Top-20 內的 `astropy/coordinates/angle_utilities.py`。這不是輸出
token 截斷，而是 7B 模型未遵守候選約束與 JSON contract。嚴格驗證器拒絕該回應是
正確行為。

因此 `codellama:7b-instruct` 足以驗證模型服務與 fallback 保護，但在目前 prompt、
Top-20 候選量與嚴格輸出契約下，不足以產生可用的 Stage-2/Stage-3 rerank 結果。

### JSON Schema＋每批 5 個候選修正後

將 File Top-20 拆成 4 批、Symbol Top-30 拆成最多 6 批，並把 JSON Schema 直接
傳給 Ollama API 後，同一張票得到：

- 執行時間：55.97 秒
- `method.llm_rerank = true`
- `stage3_diagnostics.llm_rerank_used = true`
- `stage3_diagnostics.source = llm_blended_with_symbol_retrieval`
- warnings：空陣列，沒有 fallback

這證明 `codellama:7b-instruct` 在 schema-constrained small batches 下可以完成兩個
rerank 階段。這張票的 File Top-5 與 retrieval 原排序相同，因此只證明管線與格式
約束成功，不能用來主張準確率提升。

## 相同 10 張票的 baseline／LLM 配對比較

正式比較使用相同 10 張 `astropy/astropy` ticket、相同 Stage-1 Top-20 與相同 gold。
File Top-20 每批最多 5 個候選，Ollama 使用 JSON Schema；LLM 看不到 retrieval
score，避免直接複製第一階段分數。10/10 筆 File 與 Symbol 模型呼叫均成功，warnings
為 0，模型執行時間合計約 426.96 秒。

| 檔案層級指標 | baseline | Code Llama 7B | 差值（LLM − baseline） |
|---|---:|---:|---:|
| Candidate Hit@20 | 100% | 100% | 0 個百分點 |
| Candidate Recall@20 | 86.67% | 86.67% | 0 個百分點 |
| File Hit@1 | 60% | 50% | -10 個百分點 |
| File Hit@3 | 70% | 60% | -10 個百分點 |
| File Hit@5 | 80% | 70% | -10 個百分點 |
| File MRR | 0.675 | 0.575 | -0.100 |

配對名次結果為：改善 0 筆、相同 7 筆、惡化 1 筆、兩者皆未命中 2 筆。惡化的是
`astropy__astropy-12057`：baseline 的正確檔案原為第 1 名，LLM rerank 後掉出 Top-5。
因此這次實驗的結論是「流程可穩定執行，但 `codellama:7b-instruct` 使檔案定位變差」；
不應把 7B reranker 設為預設正式流程。

這 10 張票的 `fixed_symbols` 全部為空，因此有 symbol gold 的票數是 0；Symbol
Hit@K 與 MRR 正確值是 N/A，不能以 0% 解讀。10/10 Symbol LLM 呼叫成功只證明流程
可運行，不代表 Symbol 定位準確率。

第一次 10-ticket 執行曾把 retrieval score 放進 prompt。模型輸出的 50 個 File 分數
有 50 個直接複製輸入分數（Pearson correlation = 1.0），所以該輪只作資料洩漏稽核，
不列為正式成績。上表是移除 retrieval score 後重新完整執行的結果。

正式輸出位於
`reports/fault_localization/stage2_codellama_7b_paired_10_no_score_leak/`：

- `paired_summary.json`：配對指標、差值與逐票名次結果
- `baseline_predictions.jsonl`：同一批資料的 retrieval baseline
- `llm_predictions.jsonl`：無 retrieval-score 洩漏的 LLM 結果

## 執行完整模型流程

先啟動 Ollama 並確認已有 `codellama:7b-instruct`，再執行：

```powershell
.\.venv-e7\Scripts\python.exe scripts\fault_localization.py `
  --ticket ticket.json `
  --repo-path path\to\repository `
  --candidate-file-k 20 `
  --top-k 5 `
  --llm-rerank `
  --llm-candidate-k 20 `
  --symbol-rerank `
  --symbol-candidate-k 30 `
  --symbol-top-k 5 `
  --ollama-model codellama:7b-instruct `
  --output prediction.json
```

判讀模型成績前，必須確認每筆輸出同時滿足：

- `method.llm_rerank = true`
- `stage3_diagnostics.llm_rerank_used = true`
- warnings 沒有 file/symbol rerank fallback
- gold 與 prediction 使用完全相同的 ticket 子集合

## 驗證

`python -m unittest discover -s tests -v`：123/123 通過。
