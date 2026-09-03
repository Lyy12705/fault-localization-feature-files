# 筆電接手指南

這個 GitHub 儲存庫是目前 fault localization 三階段研究的可接手版本，重點是讓筆電能延續第三階段修改與實驗，同時保留第一、二階段的程式、設定、報告與計畫文件。

## 已完整保留

- `src/`、`scripts/`、`tests/`、`tools/`、`configs/`、`experiments/`。
- 專案自己的 Markdown 計畫書、規格、狀態與研究報告。
- `reports/fault_localization/` 的第一、二、三階段實驗輸出；JSONL 大型結果由 Git LFS 管理。
- 第三階段目前 G2 實驗直接使用的 tickets、symbol gold、Stage-2 E7-A predictions。
- 第三階段 61 張 development tickets 對應的 61 個 code indexes；這些檔案由 Git LFS 管理。

## 未上傳的本機可重建內容

原始資料夾約 98 GB，不能當成一般 GitHub 儲存庫直接推送。下列內容是虛擬環境、下載快取、外部 repository checkout、完整資料集索引或 snapshot，因此由 `.gitignore` 排除：

- `.venv-e7/`、`.hf-cache-e7/`。
- `data/repositories` junction 與各 SWE-bench repository checkout。
- 約 77.7 GB 的完整 `swebench_full/indexes/`；但目前第三階段需要的 61 個 index 已另外納入 Git LFS。
- final-holdout、live 與 lite 的大型可重建 indexes、repositories、snapshots。

這些排除項目不包含專案計畫書，也不會移除目前第三階段 deterministic G2 執行所需的 61 個 indexes。

## 筆電下載

```powershell
git lfs install
git clone https://github.com/Lyy12705/fault-localization-feature-files.git
cd fault-localization-feature-files
git lfs pull
```

## 建立 Python 環境

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 驗證第三階段目前基線

```powershell
python scripts/run_stage3_deterministic_g2.py --config configs/fault_localization/stage3_deterministic_g2_v1.json
```

目前狀態與下一步以 `STAGE3_SYMBOL_RERANKER_IMPLEMENTATION_PLAN_ZH.md` 及 `reports/fault_localization/stage3_deterministic_g2_dev_v1/REPORT_ZH.md` 為準。
