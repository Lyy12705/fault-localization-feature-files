# WP3 剩餘 Ranking Misses 呼叫圖可達性

- Baseline ranking misses：30
- Prefix 一跳可達：3
- 池內呼叫圖有任一已解析相鄰節點：8
- call-neighborhood-v1 實際找回：2

## 分類

| 類別 | 數量 | 解讀 |
|---|---:|---|
| Prefix 一跳可達 | 3 | 其中 1 個找回、2 個受名額或每-anchor競爭限制 |
| 只連到 prefix 外 | 5 | anchor 覆蓋不足 |
| 無已解析 incident edge | 22 | 靜態圖沒有可用證據 |

call variant 共找回 2 個；其中 1 個沒有 prefix edge，是選取／回填改變造成，不能歸因於呼叫擴展。

「無已解析 edge」不代表執行時一定沒有呼叫關係；候選 source 不完整、動態派送或 import 解析限制都可能造成缺邊。
