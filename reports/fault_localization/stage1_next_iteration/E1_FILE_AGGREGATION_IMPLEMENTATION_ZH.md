# E1 檔案分數整合：實作與實驗設定

## 實作目的

修正原流程在「每個檔案只留下1個代表程式碼區塊」後，無法再利用同檔案其他相關區塊的問題。新版仍只讓SBERT處理每個檔案的代表區塊，以控制運算量；檔案最終排序時，則保留原本TF-IDF階段的多區塊證據。

## 四組固定比較

| 實驗 | 模式 | 加入的證據 |
|---|---|---|
| E1-A | `basic` | 原始TF-IDF Top-50＋SBERT基準 |
| E1-B | `supporting-chunks` | 同檔案多個相關程式碼區塊 |
| E1-C | `supporting-symbols` | E1-B＋不同函式或類別名稱 |
| E1-D | `supporting-symbols-package` | E1-C＋相同套件或目錄關係 |

## 預先固定參數

- 每個檔案最多採用5個彼此不高度重疊的證據區塊。
- 證據分數至少為該檔案最佳TF-IDF區塊的80%，且不得低於0.05。
- 每多1個有效區塊加0.0125，最多加0.05。
- 每多1個不同Symbol加0.01，最多加0.04。
- 套件鄰近加分最多0.10。
- 行數範圍重疊達50%的區塊視為重複，不重複累計。

以上數值是待Development驗證的工程假設，不是引用文獻得到的固定權重。執行Validation前須先固定設定，舊Frozen Holdout不得用來選擇權重。

## 評估輸出

正式主要指標仍為原始`Recall@20`。另外輸出「修正前已存在檔案的Recall@20」作為輔助說明；只有在base commit不存在的新增檔案會從輔助指標排除，修正前存在但被Code Index排除的檔案仍算錯誤。

## 程式入口

完整實驗可由`run_swebench_full_stage1_experiment.py`分別選擇下列方法：

```text
tfidf-sbert
e1-b-supporting-chunks
e1-c-supporting-symbols
e1-d-supporting-symbols-package
```

每次執行均會把聚合模式與完整參數寫入method manifest，避免不同實驗設定混在一起。

## 100筆Smoke Test結果

E1-D已在Validation前100筆完成工程檢查，100筆皆成功執行，每筆均輸出20個不重複檔案。這批資料只用來確認程式與初步方向，不能代替完整500筆Validation實驗。

| 指標 | E1-A基準 | E1-D | 差異 |
|---|---:|---:|---:|
| Hit@20 | 91.00% | 94.00% | +3.00百分點 |
| Recall@20 | 88.24% | 88.95% | +0.71百分點 |
| Top-1 | 59.00% | 58.00% | -1.00百分點 |
| MRR@20 | 0.6767 | 0.6703 | -0.0064 |
| 修正前已存在檔案Recall@20 | 88.49% | 89.87% | +1.38百分點 |

Recall@20成對差異的95%信賴區間為-1.67～+3.55百分點，仍包含0。因此這100筆結果只能視為工程smoke test，不能宣稱正式優於基準。

## 完整Validation結論

E1-A～E1-D已完成相同500筆Validation比較。E1-B的Recall@20最高，從82.98%提高到83.94%，但成對95%信賴區間為-0.31～+2.27百分點，未達事前設定的保留門檻。E1-C與E1-D造成Top-1及MRR下降。因此E1不更換正式方法，下一階段仍使用E1-A基準。

完整結果見`reports/fault_localization/stage1_next_iteration/e1_validation_500/E1_VALIDATION_500_RESULTS_ZH.md`。
