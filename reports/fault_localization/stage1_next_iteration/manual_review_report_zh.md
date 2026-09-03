# 第一階段30筆失敗案例抽查報告

- 抽查案例：30筆
- 分類確認：30筆
- 需要修正：0筆
- 已完成人工閱讀：30筆

## 索引缺漏原因

| 原因 | 檔案數 |
|---|---:|
| 修正前已存在，但被索引規則排除 | 1 |
| 修正前版本尚不存在，可能是新增或改名檔案 | 8 |

## 抽查明細

| # | Ticket | 自動分類 | 審查結果 | 備註 |
|---:|---|---|---|---|
| 1 | astropy__astropy-13075 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=1。 |
| 2 | astropy__astropy-14439 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 3 | astropy__astropy-13158 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含2個初步檢索遺漏與4個SBERT重排遺漏。 |
| 4 | astropy__astropy-14566 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第21名，重排後未進Top-20。 |
| 5 | astropy__astropy-13398 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=1。 |
| 6 | astropy__astropy-8715 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 7 | django__django-11539 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含1個初步檢索遺漏與1個SBERT重排遺漏。 |
| 8 | astropy__astropy-12842 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第43名，重排後未進Top-20。 |
| 9 | pydata__xarray-6971 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=1。 |
| 10 | django__django-17046 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 11 | astropy__astropy-14907 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含1個初步檢索遺漏與1個SBERT重排遺漏。 |
| 12 | astropy__astropy-8707 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第6名，重排後未進Top-20。 |
| 13 | astropy__astropy-13132 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=2。 |
| 14 | astropy__astropy-13438 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 15 | django__django-13841 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含2個初步檢索遺漏與1個SBERT重排遺漏。 |
| 16 | django__django-16117 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第17名，重排後未進Top-20。 |
| 17 | pylint-dev__pylint-4661 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：existing_file_excluded_by_index_rules=1。 |
| 18 | django__django-5470 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；2個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 19 | django__django-11281 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含20個初步檢索遺漏與1個SBERT重排遺漏。 |
| 20 | django__django-12198 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第17, 44名，重排後未進Top-20。 |
| 21 | matplotlib__matplotlib-25515 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=1。 |
| 22 | django__django-14387 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 23 | django__django-10301 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含2個初步檢索遺漏與1個SBERT重排遺漏。 |
| 24 | django__django-11740 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第26名，重排後未進Top-20。 |
| 25 | pytest-dev__pytest-7122 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=1。 |
| 26 | django__django-11532 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
| 27 | django__django-12431 | 同一Ticket同時包含初步檢索與重新排序遺漏 | confirmed | 分類正確；包含2個初步檢索遺漏與1個SBERT重排遺漏。 |
| 28 | django__django-10910 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | confirmed | 分類正確；正確檔案原在TF-IDF第33名，重排後未進Top-20。 |
| 29 | matplotlib__matplotlib-24691 | 正確檔案未進入Code Index | confirmed | 分類正確；至少一個正確檔案不在Code Index。原因：file_absent_at_base_commit=1。 |
| 30 | django__django-14681 | 正確檔案未進入TF-IDF前50名 | confirmed | 分類正確；1個遺漏檔案存在索引中，但未進入TF-IDF前50名。 |
