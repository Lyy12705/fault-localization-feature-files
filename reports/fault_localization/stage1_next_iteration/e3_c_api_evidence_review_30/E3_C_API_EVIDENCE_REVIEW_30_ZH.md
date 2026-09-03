# E3-C Development 30筆API證據人工分類

## 本次目的

從Development輸出中固定抽取30筆具有API重新匯出或wrapper證據的Ticket，逐筆確認證據是否真的指向本次錯誤的實作位置。這是錯誤分析，不是正式準確率實驗。

Gold檔案只在候選排序完成後用於人工分類，沒有輸入模型或參與排名。

## 分類規則

- **正確對應**：底層實作檔案屬於Gold修改檔案。
- **關係正確但非本次修改位置**：API關係成立且與功能相關，但底層檔案不是本次修改點。
- **無關對應**：名稱或API關係不是Ticket主要問題的有效線索。

## 分類結果

- 證據池：37筆
- 固定抽樣：30筆（seed=20260822）
- Repository分布：astropy/astropy 21筆、django/django 9筆
- 正確對應：8筆（26.7%）
- 關係正確但非本次修改位置：13筆（43.3%）
- 無關對應：9筆（30.0%）
- 待人工確認：0筆

## 30筆逐案結果

| # | Ticket | Repository | 分類 | API→實作 | Gold檔案 | 判定理由 |
|---:|---|---|---|---|---|---|
| 1 | `astropy__astropy-14995` | astropy/astropy | 無關對應 | constant→Constant (astropy/constants/constant.py) | astropy/nddata/mixins/ndarithmetic.py | Ticket重點是NDDataRef的mask傳遞；constant被對到constants套件，與錯誤流程無關。 |
| 2 | `astropy__astropy-12880` | astropy/astropy | 關係正確但非本次修改位置 | BinnedTimeSeries.read→read (astropy/io/ascii/ui.py)<br>myBinnedTimeSeries.write→write (astropy/io/ascii/ui.py)<br>self.registry.read→read (astropy/io/ascii/ui.py)<br>myBinnedTimeSeries.write→BaseData.write (astropy/io/ascii/core.py) | astropy/io/ascii/ecsv.py | read/write確實是表格I/O入口，但證據指向通用ascii UI與core，本次修改位置是ecsv.py。 |
| 3 | `astropy__astropy-12962` | astropy/astropy | 關係正確但非本次修改位置 | HDUList→HDUList (astropy/io/fits/hdu/hdulist.py)<br>fits.HDUList→HDUList (astropy/io/fits/hdu/hdulist.py)<br>ImageHDU→ImageHDU (astropy/io/fits/hdu/image.py)<br>PrimaryHDU→PrimaryHDU (astropy/io/fits/hdu/image.py) | astropy/nddata/ccddata.py | HDU類別的重新匯出關係正確且與需求相關，但本次新增轉換邏輯位於ccddata.py。 |
| 4 | `astropy__astropy-14598` | astropy/astropy | 無關對應 | fits→Fits (astropy/units/format/fits.py) | astropy/io/fits/card.py | Ticket中的fits套件名稱被錯對到units.format.Fits；真正問題在FITS Card。 |
| 5 | `astropy__astropy-14182` | astropy/astropy | 正確對應 | get_writer→get_writer (astropy/io/ascii/ui.py)<br>write→write (astropy/io/ascii/ui.py)<br>self.registry.write→write (astropy/io/ascii/ui.py)<br>tbl.write→write (astropy/io/ascii/ui.py) | astropy/io/ascii/rst.py | rst公開格式名稱直接連到Gold檔案astropy/io/ascii/rst.py。 |
| 6 | `astropy__astropy-13572` | astropy/astropy | 關係正確但非本次修改位置 | nutation_matrix→matrix_product (astropy/coordinates/matrix_utilities.py) | astropy/coordinates/earth_orientation.py | nutation_matrix確實委派matrix_product，但本次錯誤應修改wrapper所在的earth_orientation.py。 |
| 7 | `astropy__astropy-14528` | astropy/astropy | 正確對應 | ImageHDU→ImageHDU (astropy/io/fits/hdu/image.py)<br>fits.ImageHDU→ImageHDU (astropy/io/fits/hdu/image.py)<br>fits→Fits (astropy/units/format/fits.py)<br>corrupted.fits→Fits (astropy/units/format/fits.py) | astropy/io/fits/hdu/image.py | ImageHDU公開名稱直接連到Gold檔案astropy/io/fits/hdu/image.py。 |
| 8 | `astropy__astropy-13465` | astropy/astropy | 無關對應 | fits→Fits (astropy/units/format/fits.py) | astropy/io/fits/diff.py<br>astropy/utils/diff.py | fits字樣被錯對到units格式類別，與FITSDiff容差計算無關。 |
| 9 | `astropy__astropy-13838` | astropy/astropy | 無關對應 | p.group→Group (astropy/io/fits/hdu/groups.py) | astropy/table/pprint.py | 程式片段中的p.group被錯對到FITS Group，與Table列印問題無關。 |
| 10 | `astropy__astropy-14539` | astropy/astropy | 關係正確但非本次修改位置 | bintablehdu→BinTableHDU (astropy/io/fits/hdu/table.py)<br>fits.bintablehdu→BinTableHDU (astropy/io/fits/hdu/table.py) | astropy/io/fits/diff.py | BinTableHDU是問題涉及的資料型別，但本次比較邏輯修改在diff.py，不在table.py。 |
| 11 | `astropy__astropy-14701` | astropy/astropy | 無關對應 | io.html→HTML (astropy/io/ascii/html.py) | astropy/cosmology/io/__init__.py<br>astropy/cosmology/io/latex.py | io.html來自說明中的文件網址，錯對到ascii HTML，與Cosmology latex輸出無關。 |
| 12 | `astropy__astropy-12825` | astropy/astropy | 正確對應 | group_by→column_group_by (astropy/table/groups.py)<br>group_by→table_group_by (astropy/table/groups.py)<br>table.group_by→table_group_by (astropy/table/groups.py)<br>Table→Table (astropy/table/table.py) | astropy/table/column.py<br>astropy/table/groups.py<br>astropy/utils/data_info.py | group_by wrapper直接連到Gold檔案astropy/table/groups.py。 |
| 13 | `astropy__astropy-13234` | astropy/astropy | 關係正確但非本次修改位置 | t.write→BaseData.write (astropy/io/ascii/core.py)<br>t.write→BaseHeader.write (astropy/io/ascii/core.py)<br>t.write→BaseReader.write (astropy/io/ascii/core.py)<br>Column→Column (astropy/io/ascii/core.py) | astropy/table/serialize.py | Table read/write是序列化入口，但證據只連到通用ascii I/O，本次修改在table/serialize.py。 |
| 14 | `astropy__astropy-13933` | astropy/astropy | 無關對應 | to_string→_to_string (astropy/units/format/generic.py)<br>ang.to_string→_to_string (astropy/units/format/generic.py)<br>angle.to_string→_to_string (astropy/units/format/generic.py)<br>pang.to_string→_to_string (astropy/units/format/generic.py) | astropy/coordinates/angles.py<br>astropy/visualization/wcsaxes/formatter_locator.py | Angle.to_string被同名碰撞到OGIP單位格式器，並非Ticket中的Angle實作。 |
| 15 | `astropy__astropy-13477` | astropy/astropy | 關係正確但非本次修改位置 | ICRS→ICRS (astropy/coordinates/builtin_frames/icrs.py) | astropy/coordinates/baseframe.py<br>astropy/coordinates/sky_coordinate.py | ICRS是比較案例使用的座標框架，重新匯出關係正確，但修改點在baseframe與sky_coordinate。 |
| 16 | `astropy__astropy-7973` | astropy/astropy | 無關對應 | fits→Fits (astropy/units/format/fits.py) | astropy/wcs/wcs.py | fits名稱再次被錯對到units.format.Fits，與WCS資料尺寸記錄無關。 |
| 17 | `astropy__astropy-14413` | astropy/astropy | 正確對應 | unicode→Unicode (astropy/units/format/unicode_format.py)<br>console→Console (astropy/units/format/console.py) | astropy/units/format/console.py<br>astropy/units/format/latex.py<br>astropy/units/format/unicode_format.py | Unicode與Console公開格式名稱直接連到兩個Gold修改檔案。 |
| 18 | `astropy__astropy-13417` | astropy/astropy | 正確對應 | FITS_rec→FITS_rec (astropy/io/fits/fitsrec.py)<br>fits.open→fitsopen (astropy/io/fits/hdu/hdulist.py)<br>BinTableHDU→BinTableHDU (astropy/io/fits/hdu/table.py)<br>io.fits→Fits (astropy/units/format/fits.py) | astropy/io/fits/column.py<br>astropy/io/fits/fitsrec.py | FITS_rec重新匯出直接連到Gold檔案astropy/io/fits/fitsrec.py。 |
| 19 | `astropy__astropy-13306` | astropy/astropy | 關係正確但非本次修改位置 | table.vstack→vstack (astropy/table/operations.py) | astropy/utils/metadata.py | vstack是問題的公開操作，連到operations.py的關係正確，但實際修正位於utils/metadata.py。 |
| 20 | `astropy__astropy-13073` | astropy/astropy | 正確對應 | __init__→BaseData.__init__ (astropy/io/ascii/core.py)<br>__init__→BaseHeader.__init__ (astropy/io/ascii/core.py)<br>__init__→BaseReader.__init__ (astropy/io/ascii/core.py)<br>__init__→Column.__init__ (astropy/io/ascii/core.py) | astropy/io/ascii/core.py<br>astropy/io/ascii/docs.py | ASCII讀取流程的wrapper證據連到Gold檔案astropy/io/ascii/core.py。 |
| 21 | `astropy__astropy-14702` | astropy/astropy | 正確對應 | table.table→Table (astropy/table/table.py)<br>astropy.table→Table (astropy/table/table.py)<br>votable→Table (astropy/io/votable/tree.py) | astropy/io/votable/tree.py | VOTable公開名稱連到Gold檔案astropy/io/votable/tree.py。 |
| 22 | `django__django-15018` | django/django | 關係正確但非本次修改位置 | basecommand→BaseCommand (django/core/management/base.py) | django/core/management/__init__.py | BaseCommand是call_command流程中的有效API，來源檔即Gold，但底層base.py不是本次修改位置。 |
| 23 | `django__django-11356` | django/django | 正確對應 | get_deleted_objects→get_deleted_objects (django/contrib/admin/utils.py)<br>foreignkey→ForeignKey (django/db/models/fields/related.py)<br>models.foreignkey→ForeignKey (django/db/models/fields/related.py) | django/db/models/fields/related.py | ForeignKey重新匯出直接連到Gold檔案django/db/models/fields/related.py。 |
| 24 | `django__django-15098` | django/django | 無關對應 | HttpResponse→HttpResponse (django/http/response.py) | django/utils/translation/trans_real.py | HttpResponse只出現在重現範例，與語系解析錯誤及translation實作無關。 |
| 25 | `django__django-15483` | django/django | 關係正確但非本次修改位置 | admin.modeladmin→ModelAdmin (django/contrib/admin/options.py)<br>modeladmin→ModelAdmin (django/contrib/admin/options.py)<br>register→register (django/contrib/admin/decorators.py)<br>admin.site.register→register (django/contrib/admin/decorators.py) | django/contrib/admin/sites.py | ModelAdmin與register是相關admin公開API，但AppAdmin功能的修改位置是sites.py。 |
| 26 | `django__django-11749` | django/django | 關係正確但非本次修改位置 | commanderror→CommandError (django/core/management/base.py) | django/core/management/__init__.py | CommandError是call_command錯誤路徑的有效API，來源檔為Gold，但base.py並非修改點。 |
| 27 | `django__django-12961` | django/django | 無關對應 | timezone.now→Now (django/db/models/functions/datetime.py) | django/db/models/sql/compiler.py | timezone.now只是查詢範例中的運算式，錯誤核心是union後的order_by編譯。 |
| 28 | `django__django-13267` | django/django | 關係正確但非本次修改位置 | foreignkey→ForeignKey (django/db/models/fields/related.py)<br>models.ForeignKey→ForeignKey (django/db/models/fields/related.py) | django/db/models/base.py | ForeignKey是錯誤情境的核心欄位API，但本次修正是Model實例化流程的base.py。 |
| 29 | `django__django-17045` | django/django | 關係正確但非本次修改位置 | noreversematch→NoReverseMatch (django/urls/exceptions.py) | django/urls/resolvers.py | NoReverseMatch是錯誤表現且重新匯出關係正確，但應修改RoutePattern所在的resolvers.py。 |
| 30 | `django__django-13401` | django/django | 關係正確但非本次修改位置 | models.model→Model (django/db/models/base.py)<br>field.model→Model (django/db/models/base.py) | django/db/models/fields/__init__.py | Model基底類別與抽象模型情境相關，但本次欄位相等性修正在fields/__init__.py。 |
