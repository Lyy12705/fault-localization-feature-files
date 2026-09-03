# E3 Development 30筆證據案例分類

## 本次目的

從Development的E3-B輸出中抽取30筆具有Symbol definition證據的Ticket，檢查程式名稱是否被對應到正確修改檔案。這是錯誤分析，不是正式準確率實驗。

Gold檔案只在候選排序完成後用於分類，沒有輸入模型，也沒有參與排名。

## 分類規則

- **正確對應**：E3對應到的檔案全部都是Gold修改檔案。
- **名稱過度模糊**：E3找到Gold修改檔案，但同時對應到其他檔案。
- **錯誤對應**：E3對應的檔案與Gold修改檔案完全沒有交集。

這是以Gold檔案重疊為準的工程檢查。非Gold檔案仍可能與問題有關，但無法證明它是本Ticket真正需要修改的位置。

## 分類結果

- 證據池：39筆
- 固定亂數種子抽樣：30筆（seed=20260822）
- Repository分布：astropy/astropy 30筆
- 正確對應：8筆（26.7%）
- 名稱過度模糊：14筆（46.7%）
- 錯誤對應：8筆（26.7%）
- Exact證據：71列；Leaf證據：20列

## 30筆逐案結果

| # | Ticket | 分類 | Gold命中 | 額外對應檔案 | Exact／Leaf |
|---:|---|---|---|---|---:|
| 1 | `astropy__astropy-7671` | 正確對應 | astropy/utils/introspection.py | — | 1／0 |
| 2 | `astropy__astropy-13462` | 正確對應 | astropy/time/utils.py | — | 1／0 |
| 3 | `astropy__astropy-7336` | 錯誤對應 | — | astropy/io/misc/yaml.py | 1／0 |
| 4 | `astropy__astropy-14995` | 錯誤對應 | — | astropy/constants/constant.py<br>astropy/nddata/nddata_withmixins.py | 2／0 |
| 5 | `astropy__astropy-8747` | 名稱過度模糊 | astropy/units/quantity.py | astropy/modeling/parameters.py<br>astropy/nddata/nduncertainty.py<br>astropy/table/column.py | 1／3 |
| 6 | `astropy__astropy-12962` | 名稱過度模糊 | astropy/nddata/ccddata.py | astropy/io/fits/hdu/hdulist.py<br>astropy/io/fits/hdu/image.py<br>astropy/io/fits/hdu/nonstandard.py<br>astropy/io/fits/hdu/table.py | 7／1 |
| 7 | `astropy__astropy-14365` | 名稱過度模糊 | astropy/io/ascii/qdp.py | astropy/extern/ply/yacc.py | 1／1 |
| 8 | `astropy__astropy-14598` | 錯誤對應 | — | astropy/units/format/fits.py | 1／0 |
| 9 | `astropy__astropy-14182` | 名稱過度模糊 | astropy/io/ascii/rst.py | astropy/io/ascii/connect.py<br>astropy/io/ascii/core.py<br>astropy/io/ascii/ui.py<br>astropy/io/registry/core.py | 5／1 |
| 10 | `astropy__astropy-14253` | 名稱過度模糊 | astropy/units/quantity.py | astropy/io/fits/convenience.py<br>astropy/io/votable/tree.py | 4／0 |
| 11 | `astropy__astropy-13572` | 名稱過度模糊 | astropy/coordinates/earth_orientation.py | astropy/coordinates/matrix_utilities.py<br>astropy/units/core.py | 6／0 |
| 12 | `astropy__astropy-7606` | 正確對應 | astropy/units/core.py | — | 1／0 |
| 13 | `astropy__astropy-14528` | 名稱過度模糊 | astropy/io/fits/hdu/image.py | astropy/units/format/fits.py | 2／0 |
| 14 | `astropy__astropy-13404` | 錯誤對應 | — | astropy/table/table.py<br>astropy/time/core.py<br>astropy/time/formats.py<br>astropy/uncertainty/core.py<br>astropy/utils/masked/core.py | 2／3 |
| 15 | `astropy__astropy-14590` | 名稱過度模糊 | astropy/utils/masked/core.py | astropy/stats/funcs.py<br>astropy/utils/data_info.py | 3／0 |
| 16 | `astropy__astropy-13838` | 錯誤對應 | — | astropy/io/votable/tree.py<br>astropy/table/table.py | 2／0 |
| 17 | `astropy__astropy-14213` | 錯誤對應 | — | astropy/io/votable/converters.py<br>astropy/units/core.py<br>astropy/units/quantity_helper/converters.py | 4／0 |
| 18 | `astropy__astropy-14539` | 名稱過度模糊 | astropy/io/fits/diff.py | astropy/io/fits/fitsrec.py<br>astropy/io/fits/hdu/table.py<br>astropy/io/votable/converters.py<br>astropy/io/votable/tree.py | 4／2 |
| 19 | `astropy__astropy-14701` | 錯誤對應 | — | astropy/cosmology/io/table.py<br>astropy/io/votable/tree.py | 4／1 |
| 20 | `astropy__astropy-7218` | 名稱過度模糊 | astropy/io/fits/hdu/hdulist.py | astropy/io/fits/hdu/nonstandard.py | 1／1 |
| 21 | `astropy__astropy-7441` | 正確對應 | astropy/time/core.py | — | 1／1 |
| 22 | `astropy__astropy-13668` | 名稱過度模糊 | astropy/wcs/wcs.py | astropy/nddata/ccddata.py | 2／1 |
| 23 | `astropy__astropy-14042` | 正確對應 | astropy/units/format/fits.py | — | 1／0 |
| 24 | `astropy__astropy-12907` | 正確對應 | astropy/modeling/separable.py | — | 1／0 |
| 25 | `astropy__astropy-13638` | 名稱過度模糊 | astropy/units/quantity.py | astropy/units/decorators.py | 2／0 |
| 26 | `astropy__astropy-14369` | 名稱過度模糊 | astropy/units/format/cds.py | astropy/io/ascii/cds.py<br>astropy/io/ascii/mrt.py | 3／0 |
| 27 | `astropy__astropy-7973` | 名稱過度模糊 | astropy/wcs/wcs.py | astropy/nddata/ccddata.py<br>astropy/nddata/nddata.py<br>astropy/units/format/fits.py<br>cextern/cfitsio/lib/fitscore.c | 3／4 |
| 28 | `astropy__astropy-14413` | 正確對應 | astropy/units/format/console.py<br>astropy/units/format/unicode_format.py | — | 2／0 |
| 29 | `astropy__astropy-8519` | 錯誤對應 | — | astropy/units/core.py | 2／0 |
| 30 | `astropy__astropy-8339` | 正確對應 | astropy/stats/bayesian_blocks.py | — | 1／1 |

## 結果判讀

若『名稱過度模糊』或『錯誤對應』比例偏高，下一版應先限制leaf-name對應，例如不要把`self.version`、`other.version`或模組路徑的最後一段，直接對應到Repository內所有同名Method。

本次樣本來自目前已完成的Development證據池；其Repository涵蓋範圍應與正式500筆Validation分開報告，不能用本表取代正式方法比較。
