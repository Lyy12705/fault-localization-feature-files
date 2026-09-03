# E4 Call Graph固定30筆證據人工分類

## 本次目的

從固定Validation前30筆的E4輸出中，對實際影響Top-20排序的Call Graph證據邊做固定seed抽樣，逐筆確認關係是否有助於本次錯誤定位。這是事後證據分析，不是新的準確率實驗。

Gold檔案只在候選排序完成後用於分類，沒有輸入模型或參與排名。

## 分類規則

- **指向正確修改檔案**：Call Graph目標檔案屬於Gold修改檔案。
- **功能相關但非本次修改位置**：呼叫成立且和Ticket功能相關，但目標不是本次修改點。
- **完全無關**：呼叫雖成立，但來源或目標與Ticket主要問題無關。

## 分類結果

- 完整證據池：402條，來自30筆Ticket與162個候選檔案。
- 固定抽樣：30條（seed=20260823），涵蓋20筆Ticket。
- Repository分布：astropy/astropy 24條、django/django 6條
- 指向正確修改檔案：5條（16.7%）。
- 功能相關但非本次修改位置：10條（33.3%）。
- 完全無關：15條（50.0%）。
- 待人工確認：0條。

## 分類與參數判讀

| 分組 | 指向Gold | 功能相關 | 完全無關 |
|---|---:|---:|---:|
| 解析類型：imported_function | 3 | 8 | 11 |
| 解析類型：module_function | 2 | 2 | 4 |
| 來源排名1 | 2 | 2 | 2 |
| 來源排名2–3 | 2 | 6 | 7 |
| 來源排名4–5 | 1 | 2 | 6 |

`imported_function`與`module_function`的完全無關比例在本次樣本中都為50%，因此目前沒有證據支持只保留其中一種解析類型。來源排名則呈現較明確差異：第1名來源有2／6條無關，第2–3名有7／15條無關，第4–5名有6／9條無關。

後續已依此結果完成預先固定的Top-3改良版：Call Graph來源由前5名限制為前3名，其他解析類型、加分與fan-out參數保持不變。相同30筆的Recall增益維持不變，證據邊減少31.6%，因此Top-3進入500筆Validation正式比較。

## 30條逐案結果

| # | 證據ID | Ticket | 分類 | 來源呼叫 | 目標 | 候選／來源排名 | 判定理由 |
|---:|---|---|---|---|---|---|---|
| 1 | `e4cg-2183788c1ed6` | `astropy__astropy-7166` | 完全無關 | astropy/config/configuration.py::get_config → configobj.ConfigObj | astropy/extern/configobj/configobj.py::ConfigObj | 7／4 | Ticket處理InheritDocstrings屬性文件；設定檔讀取ConfigObj與此錯誤流程無關。 |
| 2 | `e4cg-6fe148a2bdd2` | `astropy__astropy-14966` | 完全無關 | astropy/table/table.py::Table.mask → FalseArray | astropy/table/column.py::FalseArray | 1／1 | Ticket重點是QTable分組鍵遺失單位；Table.mask到FalseArray的遮罩流程與分組鍵無關。 |
| 3 | `e4cg-bea83d88abb1` | `astropy__astropy-14966` | 完全無關 | astropy/table/table.py::Table.iloc → TableILoc | astropy/table/index.py::TableILoc | 15／1 | Table.iloc與TableILoc屬於索引存取，不是QTable group keys保留單位的處理流程。 |
| 4 | `e4cg-82bf78ef421b` | `astropy__astropy-8292` | 功能相關但非本次修改位置 | astropy/units/quantity.py::Quantity.to_value → is_effectively_unity | astropy/units/utils.py::is_effectively_unity | 5／2 | Quantity.to_value與單位轉換會使用is_effectively_unity，和littleh等價換算相關，但本次修改在equivalencies.py。 |
| 5 | `e4cg-540e163302e6` | `astropy__astropy-8292` | 功能相關但非本次修改位置 | astropy/units/core.py::UnitBase.__eq__ → is_effectively_unity | astropy/units/utils.py::is_effectively_unity | 5／4 | UnitBase相等判斷與單位換算相關，is_effectively_unity也是有效底層工具，但不是本次修改位置。 |
| 6 | `e4cg-64a22b0b8468` | `astropy__astropy-13398` | 功能相關但非本次修改位置 | astropy/coordinates/earth.py::EarthLocation._get_gcrs_posvel → matrix_transpose | astropy/coordinates/matrix_utilities.py::matrix_transpose | 3／3 | EarthLocation座標位置與矩陣轉置都屬ITRS轉換流程，但新增的直接轉換實作位於其他Gold檔案。 |
| 7 | `e4cg-f827b6b3e09d` | `astropy__astropy-13731` | 功能相關但非本次修改位置 | astropy/time/core.py::Time.strptime → _strptime._strptime | astropy/extern/_strptime.py::_strptime | 3／2 | Time.strptime呼叫_strptime是日期字串解析的有效路徑，但分數日解析錯誤的修改點在time/formats.py。 |
| 8 | `e4cg-951e4bf04f23` | `astropy__astropy-13731` | 完全無關 | astropy/coordinates/angle_formats.py::_check_hour_range → IllegalHourWarning | astropy/coordinates/errors.py::IllegalHourWarning | 6／4 | 座標小時角範圍警告與Time日期字串的分數日解析問題無關。 |
| 9 | `e4cg-5d1d37a76d57` | `astropy__astropy-14508` | 完全無關 | astropy/io/fits/convenience.py::info → fitsopen | astropy/io/fits/hdu/hdulist.py::fitsopen | 3／3 | FITS便利函式info開啟HDUList是通用I/O流程，與Card浮點數字串格式化問題無關。 |
| 10 | `e4cg-60cb03ca6f13` | `astropy__astropy-14508` | 功能相關但非本次修改位置 | astropy/io/fits/convenience.py::_makehdu → Header | astropy/io/fits/header.py::Header | 9／3 | Header會包含Card，_makehdu建立Header與FITS標頭功能相關，但浮點格式化修正在card.py。 |
| 11 | `e4cg-7f5bbaa3b1b5` | `astropy__astropy-14508` | 功能相關但非本次修改位置 | astropy/io/fits/card.py::Card._parse_value → _str_to_num | astropy/io/fits/util.py::_str_to_num | 16／1 | Card._parse_value呼叫_str_to_num屬Card數值處理的直接路徑，但目標util.py不是本次修改檔案。 |
| 12 | `e4cg-de5ffa73c5fa` | `astropy__astropy-13579` | 完全無關 | astropy/wcs/wcs.py::WCS → docstrings.RA_DEC_ORDER | astropy/wcs/docstrings.py::RA_DEC_ORDER | 8／3 | RA_DEC_ORDER只是WCS文件常數，與SlicedLowLevelWCS的world_to_pixel計算錯誤無關。 |
| 13 | `e4cg-fcdf0628e0b7` | `astropy__astropy-14379` | 功能相關但非本次修改位置 | astropy/units/core.py::UnitBase.to_string → unit_format.get_format | astropy/units/format/__init__.py::get_format | 19／5 | UnitBase.to_string到格式選擇屬單位輸出流程，與Angle字串中的值／單位間距相關，但非本次修改點。 |
| 14 | `e4cg-80c4932e6851` | `astropy__astropy-8715` | 指向正確修改檔案 | astropy/io/votable/table.py::validate → exceptions.parse_vowarning | astropy/io/votable/exceptions.py::parse_vowarning | 1／2 | VOTable驗證呼叫警告解析，目標exceptions.py屬本Ticket的Gold修改檔案。 |
| 15 | `e4cg-284dd1721e8c` | `astropy__astropy-8872` | 功能相關但非本次修改位置 | astropy/units/quantity.py::Quantity.to → Unit | astropy/units/core.py::Unit | 5／1 | Quantity.to與Unit是Quantity的核心單位處理流程，和dtype問題屬同一功能區域，但修改位置在quantity.py。 |
| 16 | `e4cg-63ef6ac0b643` | `astropy__astropy-14096` | 完全無關 | astropy/coordinates/sky_coordinate_parsers.py::_get_frame_without_data → _get_repr_cls | astropy/coordinates/baseframe.py::_get_repr_cls | 4／3 | 座標frame表示類別選擇與SkyCoord子類別__getattr__錯誤訊息無關。 |
| 17 | `e4cg-3fc32d920d1e` | `astropy__astropy-14096` | 完全無關 | astropy/wcs/utils.py::_celestial_frame_to_wcs_builtin → WCS | astropy/wcs/wcs.py::WCS | 10／5 | WCS座標框架轉換與SkyCoord子類別屬性存取錯誤無關。 |
| 18 | `e4cg-77752dc50235` | `astropy__astropy-13438` | 完全無關 | astropy/io/fits/hdu/hdulist.py::HDUList._verify → _ErrList | astropy/io/fits/verify.py::_ErrList | 7／5 | FITS驗證錯誤清單與jQuery套件安全漏洞及版本更新完全無關。 |
| 19 | `e4cg-626b497ce5f0` | `astropy__astropy-12318` | 指向正確修改檔案 | astropy/io/misc/asdf/tags/transform/physical_models.py::BlackBody.from_tree_transform → physical_models.BlackBody | astropy/modeling/physical_models.py::BlackBody | 1／2 | ASDF的BlackBody轉換直接呼叫BlackBody，目標physical_models.py是本Ticket的Gold修改檔案。 |
| 20 | `e4cg-44f1b643df05` | `astropy__astropy-14578` | 指向正確修改檔案 | astropy/io/fits/fitsrec.py::FITS_rec.from_columns → ColDefs | astropy/io/fits/column.py::ColDefs | 1／5 | FITS_rec.from_columns呼叫ColDefs，目標column.py是物件欄位寫入錯誤的Gold修改檔案。 |
| 21 | `e4cg-8b7c7c3f8e7d` | `astropy__astropy-14578` | 完全無關 | astropy/table/column.py::BaseColumn.groups → groups.ColumnGroups | astropy/table/groups.py::ColumnGroups | 14／3 | Table欄位分組功能與將object dtype寫入FITS失敗無關。 |
| 22 | `e4cg-1cbf3685d1a6` | `astropy__astropy-13162` | 功能相關但非本次修改位置 | astropy/coordinates/angle_formats.py::_check_hour_range → IllegalHourError | astropy/coordinates/errors.py::IllegalHourError | 3／2 | Angle格式檢查呼叫IllegalHourError屬角度輸入驗證流程，來源也是Gold檔案，但錯誤類別檔非修改位置。 |
| 23 | `e4cg-092782415232` | `astropy__astropy-13162` | 功能相關但非本次修改位置 | astropy/coordinates/angle_formats.py::_check_hour_range → IllegalHourWarning | astropy/coordinates/errors.py::IllegalHourWarning | 3／2 | Angle格式檢查呼叫IllegalHourWarning屬角度輸入驗證流程，來源也是Gold檔案，但警告類別檔非修改位置。 |
| 24 | `e4cg-40bf3da285f9` | `astropy__astropy-13162` | 完全無關 | astropy/units/quantity_helper/erfa.py::helper_ldn → _d | astropy/units/quantity_helper/helpers.py::_d | 7／5 | ERFA的ldn單位輔助函式與Angle的dms tuple符號處理無關。 |
| 25 | `e4cg-b26f9f879b2e` | `django__django-13121` | 完全無關 | django/db/models/sql/compiler.py::SQLCompiler.find_ordering_name → get_order_dir | django/db/models/sql/query.py::get_order_dir | 3／2 | 排序欄位名稱解析與duration expression的資料庫轉換錯誤無關。 |
| 26 | `e4cg-a0f9f6e546fe` | `django__django-13121` | 指向正確修改檔案 | django/db/models/query.py::QuerySet.bulk_update → Value | django/db/models/expressions.py::Value | 8／1 | QuerySet建立Value expression時目標expressions.py屬本Ticket的Gold修改檔案。 |
| 27 | `e4cg-37e32d8610d0` | `django__django-11539` | 完全無關 | django/core/management/__init__.py::ManagementUtility.execute → handle_default_options | django/core/management/base.py::handle_default_options | 7／4 | 管理命令預設選項處理與Index名稱檢查移至model system checks無關。 |
| 28 | `e4cg-6ede9fed4fd8` | `django__django-13841` | 完全無關 | django/template/defaulttags.py::verbatim → Context | django/template/context.py::Context | 18／2 | template的verbatim標籤與Context建立都不是延遲讀取__file__的五個問題模組。 |
| 29 | `e4cg-7ec113bd58c1` | `django__django-15292` | 完全無關 | django/contrib/admindocs/views.py::ViewDetailView.get_context_data → utils.parse_docstring | django/contrib/admindocs/utils.py::parse_docstring | 8／3 | admindocs解析view docstring與Technical 404頁面顯示CBV名稱錯誤無關。 |
| 30 | `e4cg-d8499fbea42a` | `django__django-16810` | 指向正確修改檔案 | django/utils/translation/trans_real.py::check_for_language → to_locale | django/utils/translation/__init__.py::to_locale | 2／1 | 語言檢查呼叫to_locale，目標translation/__init__.py屬本Ticket的Gold修改檔案。 |
