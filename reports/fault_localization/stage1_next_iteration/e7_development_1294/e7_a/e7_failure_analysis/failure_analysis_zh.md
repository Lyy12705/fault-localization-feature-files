# 第一階段未命中案例分析

> 本報告只分析Top-20部分命中與完全未命中案例。舊Frozen Holdout只用於v1事後說明，不再作為v2獨立測試集。

## 一、資料範圍

| 資料組 | 用途 | 總Ticket | 完全找回 | 部分命中 | 完全未命中 |
|---|---|---:|---:|---:|---:|
| development | development_only | 1294 | 1077 | 120 | 97 |

## 二、失敗環節

### development

| 失敗環節 | Ticket數 |
|---|---:|
| 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 19 |
| 正確檔案未進入Code Index | 17 |
| 正確檔案未進入TF-IDF前50名 | 85 |
| 同一Ticket同時包含初步檢索與重新排序遺漏 | 29 |
| 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 67 |

## 三、結果判讀方式

- Index coverage failure：先修正索引範圍，排序模型無法找回不存在的候選。
- Initial retrieval miss：優先改善TF-IDF候選池、查詢擴充或Repository大小調整。
- Reranker demotion：優先檢查SBERT排序與檔案分數整合。
- Cross-file partial miss：優先檢查Import／Call Graph是否能補回其他檔案。
- Analysis unavailable：先補齊Code Index或TF-IDF前50資料，再做人工判讀。

## 四、案例清單

| 資料組 | Ticket | Repository | 結果 | 失敗環節 | 遺漏檔案 |
|---|---|---|---|---|---|
| development | astropy__astropy-8747 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | astropy/utils/compat/numpycompat.py |
| development | astropy__astropy-14701 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入Code Index | astropy/cosmology/io/latex.py |
| development | astropy__astropy-7008 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入Code Index | astropy/constants/utils.py |
| development | astropy__astropy-13933 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | astropy/visualization/wcsaxes/formatter_locator.py |
| development | astropy__astropy-14413 | astropy/astropy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | astropy/units/format/latex.py |
| development | astropy__astropy-12891 | astropy/astropy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | astropy/utils/masked/core.py |
| development | django__django-13884 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/urls/base.py |
| development | django__django-13495 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/backends/base/operations.py<br>django/db/backends/sqlite3/base.py<br>django/db/backends/sqlite3/operations.py |
| development | django__django-13512 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/admin/utils.py |
| development | django__django-11062 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/sql/query.py |
| development | django__django-13354 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/operations/utils.py |
| development | django__django-15388 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/template/autoreload.py |
| development | django__django-14894 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/postgres/aggregates/statistics.py |
| development | django__django-15401 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/related_lookups.py |
| development | django__django-11630 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/core/checks/model_checks.py |
| development | django__django-12771 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/migrations/autodetector.py<br>django/db/migrations/operations/utils.py |
| development | django__django-16032 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/related_lookups.py |
| development | django__django-14399 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/conf/__init__.py |
| development | django__django-14313 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/admin/views/main.py<br>django/db/models/sql/compiler.py |
| development | django__django-11138 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/backends/sqlite3/base.py |
| development | django__django-11677 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/models/sql/where.py |
| development | django__django-13250 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/base/features.py<br>django/db/backends/oracle/features.py |
| development | django__django-12125 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/migrations/serializer.py |
| development | django__django-17087 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/serializer.py |
| development | django__django-12113 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/backends/sqlite3/creation.py |
| development | django__django-13207 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/core/management/commands/inspectdb.py<br>django/db/backends/base/features.py<br>django/db/backends/base/introspection.py<br>django/db/backends/base/schema.py<br>django/db/backends/mysql/features.py<br>django/db/backends/mysql/introspection.py<br>django/db/backends/mysql/schema.py<br>django/db/backends/oracle/features.py<br>django/db/backends/oracle/introspection.py<br>django/db/backends/oracle/schema.py<br>django/db/backends/postgresql/features.py<br>django/db/backends/postgresql/introspection.py<br>django/db/backends/sqlite3/features.py<br>django/db/backends/sqlite3/introspection.py<br>django/db/backends/sqlite3/schema.py |
| development | django__django-11797 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/lookups.py |
| development | django__django-13530 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/postgres/aggregates/mixins.py<br>django/contrib/postgres/constraints.py<br>django/db/models/expressions.py<br>django/db/models/lookups.py |
| development | django__django-14997 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/backends/ddl_references.py |
| development | django__django-11359 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/lookups.py |
| development | django__django-12304 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/models/enums.py |
| development | django__django-16281 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/backends/sqlite3/schema.py |
| development | django__django-16311 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/utils/text.py |
| development | django__django-16816 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/contrib/admin/checks.py |
| development | django__django-12519 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/backends/mysql/base.py<br>django/db/backends/mysql/validation.py |
| development | django__django-14580 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/serializer.py |
| development | django__django-16229 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/forms/boundfield.py |
| development | django__django-11527 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/core/management/commands/sqlflush.py<br>django/core/management/commands/sqlmigrate.py |
| development | django__django-11885 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/admin/utils.py |
| development | django__django-12754 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/migrations/autodetector.py |
| development | django__django-12821 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/admin/helpers.py<br>django/contrib/admin/options.py |
| development | django__django-15629 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/base/schema.py<br>django/db/backends/oracle/features.py<br>django/db/backends/sqlite3/schema.py |
| development | django__django-15154 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/options.py |
| development | django__django-13344 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/sessions/middleware.py |
| development | django__django-14430 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/postgres/aggregates/statistics.py |
| development | django__django-15022 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/admin/options.py |
| development | django__django-15052 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/postgres/aggregates/mixins.py |
| development | django__django-12396 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/core/checks/database.py<br>django/core/management/commands/check.py<br>django/core/management/commands/migrate.py |
| development | django__django-12419 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/conf/global_settings.py |
| development | django__django-12313 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/fields/related.py |
| development | django__django-11815 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/serializer.py |
| development | django__django-11916 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/related_descriptors.py |
| development | django__django-15925 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/backends/sqlite3/schema.py |
| development | django__django-15352 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/views/debug.py |
| development | django__django-12928 | django/django | 只找回部分正確檔案 | 正確檔案未進入Code Index | django/template/__init__.py<br>django/template/autoreload.py<br>django/utils/translation/reloader.py |
| development | django__django-11564 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/conf/__init__.py |
| development | django__django-15139 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/sessions/backends/base.py |
| development | django__django-14722 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/autodetector.py |
| development | django__django-13569 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/models/functions/math.py |
| development | django__django-13350 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/http/multipartparser.py |
| development | django__django-12184 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/urls/resolvers.py |
| development | django__django-14149 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/conf/__init__.py |
| development | django__django-14019 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/indexes.py |
| development | django__django-13915 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/core/management/commands/compilemessages.py<br>django/db/backends/postgresql/base.py<br>django/db/backends/sqlite3/base.py<br>django/db/backends/sqlite3/client.py<br>django/db/migrations/questioner.py<br>django/http/cookie.py<br>django/http/request.py<br>django/utils/autoreload.py<br>django/utils/http.py<br>django/utils/module_loading.py<br>setup.py |
| development | django__django-15272 | django/django | 正確檔案未進入Code Index | 正確檔案未進入Code Index | django/core/management/commands/optimizemigration.py |
| development | django__django-16599 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/models/lookups.py |
| development | django__django-14785 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/__init__.py |
| development | matplotlib__matplotlib-25126 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/transforms.py |
| development | matplotlib__matplotlib-24749 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/contour.py |
| development | matplotlib__matplotlib-18869 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/__init__.py |
| development | matplotlib__matplotlib-25027 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/collections.py |
| development | matplotlib__matplotlib-26078 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/axes/_axes.py<br>lib/mpl_toolkits/mplot3d/axes3d.py |
| development | matplotlib__matplotlib-25551 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/mpl_toolkits/mplot3d/axes3d.py |
| development | matplotlib__matplotlib-23742 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | examples/user_interfaces/embedding_webagg_sgskip.py |
| development | matplotlib__matplotlib-22945 | matplotlib/matplotlib | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/collections.py |
| development | matplotlib__matplotlib-25311 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/offsetbox.py |
| development | matplotlib__matplotlib-25332 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/cbook.py |
| development | matplotlib__matplotlib-26122 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | galleries/examples/misc/demo_ribbon_box.py |
| development | matplotlib__matplotlib-24971 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/_tight_bbox.py |
| development | matplotlib__matplotlib-25775 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/text.py |
| development | matplotlib__matplotlib-25640 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/backends/backend_pgf.py |
| development | matplotlib__matplotlib-19553 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/contour.py |
| development | matplotlib__matplotlib-25779 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | galleries/examples/shapes_and_collections/ellipse_arrow.py |
| development | matplotlib__matplotlib-23031 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | setup.py |
| development | matplotlib__matplotlib-21238 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/artist.py<br>lib/matplotlib/axes/_base.py<br>lib/matplotlib/axis.py<br>lib/matplotlib/cbook/__init__.py<br>lib/matplotlib/cm.py<br>lib/matplotlib/colors.py<br>lib/matplotlib/container.py |
| development | matplotlib__matplotlib-26341 | matplotlib/matplotlib | 只找回部分正確檔案 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/sankey.py |
| development | matplotlib__matplotlib-20826 | matplotlib/matplotlib | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | 缺少Code Index或TF-IDF前50資料，暫時無法判定 | lib/matplotlib/axis.py |
| development | mwaskom__seaborn-2813 | mwaskom/seaborn | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | seaborn/regression.py |
| development | psf__requests-2153 | psf/requests | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | requests/compat.py |
| development | psf__requests-2678 | psf/requests | 只找回部分正確檔案 | 正確檔案未進入Code Index | requests/auth.py<br>requests/packages/__init__.py<br>requests/packages/urllib3/contrib/appengine.py<br>requests/packages/urllib3/contrib/pyopenssl.py<br>requests/packages/urllib3/util/ssl_.py |
| development | pydata__xarray-4684 | pydata/xarray | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/coding/times.py |
| development | pydata__xarray-7179 | pydata/xarray | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | xarray/backends/cfgrib_.py<br>xarray/backends/h5netcdf_.py<br>xarray/backends/netCDF4_.py<br>xarray/backends/pseudonetcdf_.py<br>xarray/backends/pydap_.py<br>xarray/backends/pynio_.py<br>xarray/backends/scipy_.py<br>xarray/backends/zarr.py<br>xarray/convert.py<br>xarray/core/_aggregations.py<br>xarray/core/duck_array_ops.py<br>xarray/core/missing.py<br>xarray/core/parallel.py<br>xarray/plot/utils.py<br>xarray/util/generate_aggregations.py |
| development | pydata__xarray-5662 | pydata/xarray | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | xarray/core/formatting.py |
| development | pydata__xarray-7112 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | xarray/core/formatting.py |
| development | pydata__xarray-4184 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | asv_bench/benchmarks/pandas.py<br>xarray/core/indexes.py |
| development | pydata__xarray-4248 | pydata/xarray | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/formatting.py |
| development | pydata__xarray-3239 | pydata/xarray | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/concat.py<br>xarray/core/merge.py |
| development | pydata__xarray-4683 | pydata/xarray | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | doc/conf.py |
| development | pydata__xarray-6548 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | asv_bench/benchmarks/polyfit.py |
| development | pydata__xarray-3733 | pydata/xarray | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | xarray/__init__.py<br>xarray/core/dask_array_ops.py |
| development | pydata__xarray-4911 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | xarray/core/dtypes.py |
| development | pylint-dev__pylint-8929 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | pylint/interfaces.py<br>pylint/reporters/__init__.py |
| development | pylint-dev__pylint-4551 | pylint-dev/pylint | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | pylint/pyreverse/inspector.py<br>pylint/pyreverse/utils.py |
| development | pylint-dev__pylint-7097 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/checkers/imports.py |
| development | pylint-dev__pylint-7114 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/lint/expand_modules.py |
| development | pylint-dev__pylint-7080 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/lint/expand_modules.py |
| development | pylint-dev__pylint-6358 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/checkers/similar.py |
| development | pylint-dev__pylint-7228 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/config/argument.py |
| development | pylint-dev__pylint-6517 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/config/argument.py |
| development | pylint-dev__pylint-4492 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案未進入Code Index | pylint/reporters/__init__.py<br>pylint/reporters/multi_reporter.py |
| development | pylint-dev__pylint-5201 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | pylint/config/option.py |
| development | pylint-dev__pylint-5136 | pylint-dev/pylint | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | pylint/checkers/misc.py<br>pylint/message/__init__.py<br>pylint/typing.py |
| development | pylint-dev__pylint-4516 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/lint/pylinter.py |
| development | pytest-dev__pytest-5479 | pytest-dev/pytest | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | src/_pytest/_code/code.py |
| development | pytest-dev__pytest-5787 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/reports.py |
| development | pytest-dev__pytest-8447 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/main.py |
| development | pytest-dev__pytest-7466 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/_io/terminalwriter.py |
| development | pytest-dev__pytest-8987 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/mark/expression.py |
| development | pytest-dev__pytest-8055 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入Code Index | src/_pytest/pytester.py<br>src/_pytest/threadexception.py<br>src/_pytest/unraisableexception.py<br>src/pytest/__init__.py |
| development | pytest-dev__pytest-8124 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/hookspec.py |
| development | pytest-dev__pytest-5356 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/mark/structures.py |
| development | pytest-dev__pytest-11148 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/pathlib.py |
| development | pytest-dev__pytest-7749 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/assertion/rewrite.py |
| development | pytest-dev__pytest-8399 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/python.py |
| development | pytest-dev__pytest-7158 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/skipping.py |
| development | pytest-dev__pytest-5980 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入Code Index | src/_pytest/report_log.py |
| development | pytest-dev__pytest-5221 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/python.py |
| development | pytest-dev__pytest-7046 | pytest-dev/pytest | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | src/_pytest/mark/__init__.py<br>src/_pytest/python.py |
| development | pytest-dev__pytest-5281 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/capture.py |
| development | pytest-dev__pytest-7220 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/nodes.py |
| development | pytest-dev__pytest-9249 | pytest-dev/pytest | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | src/_pytest/mark/expression.py |
| development | pytest-dev__pytest-9780 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/config/__init__.py |
| development | pytest-dev__pytest-8950 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | src/_pytest/scope.py |
| development | pytest-dev__pytest-6116 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/main.py |
| development | pytest-dev__pytest-7151 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | src/_pytest/debugging.py |
| development | scikit-learn__scikit-learn-10306 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sklearn/cross_decomposition/pls_.py<br>sklearn/gaussian_process/gpc.py<br>sklearn/gaussian_process/gpr.py<br>sklearn/linear_model/logistic.py<br>sklearn/linear_model/ransac.py<br>sklearn/linear_model/ridge.py |
| development | scikit-learn__scikit-learn-25308 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sklearn/feature_selection/_base.py |
| development | scikit-learn__scikit-learn-14024 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sklearn/utils/estimator_checks.py |
| development | scikit-learn__scikit-learn-13013 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sklearn/cluster/birch.py<br>sklearn/decomposition/online_lda.py<br>sklearn/ensemble/forest.py<br>sklearn/gaussian_process/gpr.py |
| development | scikit-learn__scikit-learn-13392 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | examples/model_selection/plot_roc.py<br>sklearn/linear_model/coordinate_descent.py<br>sklearn/linear_model/least_angle.py<br>sklearn/linear_model/ridge.py<br>sklearn/neighbors/regression.py |
| development | scikit-learn__scikit-learn-13628 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sklearn/calibration.py |
| development | scikit-learn__scikit-learn-13584 | scikit-learn/scikit-learn | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sklearn/utils/_pprint.py |
| development | scikit-learn__scikit-learn-15084 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sklearn/ensemble/_stacking.py<br>sklearn/ensemble/base.py |
| development | scikit-learn__scikit-learn-13618 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | examples/linear_model/plot_bayesian_ridge_curvefit.py |
| development | scikit-learn__scikit-learn-7760 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sklearn/utils/_unittest_backport.py |
| development | scikit-learn__scikit-learn-12656 | scikit-learn/scikit-learn | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sklearn/metrics/classification.py |
| development | scikit-learn__scikit-learn-10483 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | examples/plot_missing_values.py<br>sklearn/__init__.py<br>sklearn/impute.py<br>sklearn/utils/estimator_checks.py |
| development | scikit-learn__scikit-learn-25363 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | benchmarks/bench_saga.py<br>sklearn/calibration.py<br>sklearn/cluster/_mean_shift.py<br>sklearn/compose/_column_transformer.py<br>sklearn/covariance/_graph_lasso.py<br>sklearn/decomposition/_dict_learning.py<br>sklearn/decomposition/_lda.py<br>sklearn/ensemble/_forest.py<br>sklearn/ensemble/_voting.py<br>sklearn/feature_selection/_rfe.py<br>sklearn/inspection/_permutation_importance.py<br>sklearn/inspection/_plot/partial_dependence.py<br>sklearn/linear_model/_base.py<br>sklearn/linear_model/_coordinate_descent.py<br>sklearn/linear_model/_least_angle.py<br>sklearn/linear_model/_logistic.py<br>sklearn/linear_model/_omp.py<br>sklearn/linear_model/_stochastic_gradient.py<br>sklearn/linear_model/_theil_sen.py<br>sklearn/manifold/_mds.py<br>sklearn/metrics/pairwise.py<br>sklearn/model_selection/_search.py<br>sklearn/multiclass.py<br>sklearn/multioutput.py<br>sklearn/neighbors/_base.py<br>sklearn/utils/parallel.py |
| development | scikit-learn__scikit-learn-11542 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | examples/applications/plot_prediction_latency.py<br>examples/ensemble/plot_ensemble_oob.py<br>examples/ensemble/plot_voting_probas.py |
| development | scikit-learn__scikit-learn-25969 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | sklearn/utils/_plotting.py |
| development | scikit-learn__scikit-learn-12983 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | sklearn/ensemble/_gb_losses.py |
| development | sphinx-doc__sphinx-9828 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/application.py<br>sphinx/builders/__init__.py<br>sphinx/config.py |
| development | sphinx-doc__sphinx-7906 | sphinx-doc/sphinx | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sphinx/domains/c.py<br>sphinx/domains/cpp.py |
| development | sphinx-doc__sphinx-7234 | sphinx-doc/sphinx | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sphinx/ext/autodoc/__init__.py<br>sphinx/ext/autosummary/generate.py<br>sphinx/util/inspect.py |
| development | sphinx-doc__sphinx-10807 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/domains/c.py<br>sphinx/domains/cpp.py<br>sphinx/domains/javascript.py<br>sphinx/domains/python.py<br>sphinx/domains/rst.py<br>sphinx/environment/collectors/toctree.py |
| development | sphinx-doc__sphinx-8474 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/std.py |
| development | sphinx-doc__sphinx-8273 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/builders/manpage.py |
| development | sphinx-doc__sphinx-7757 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/util/inspect.py |
| development | sphinx-doc__sphinx-9260 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/builders/linkcheck.py |
| development | sphinx-doc__sphinx-7831 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/ext/autodoc/type_comment.py |
| development | sphinx-doc__sphinx-7454 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/python.py |
| development | sphinx-doc__sphinx-10097 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/domains/std.py |
| development | sphinx-doc__sphinx-8117 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/cpp.py |
| development | sphinx-doc__sphinx-9053 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/environment/adapters/toctree.py<br>sphinx/writers/html.py<br>sphinx/writers/html5.py |
| development | sphinx-doc__sphinx-8771 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入Code Index | sphinx/ext/autodoc/preserve_defaults.py |
| development | sphinx-doc__sphinx-8020 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/python.py |
| development | sphinx-doc__sphinx-10819 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/search/__init__.py |
| development | sphinx-doc__sphinx-10048 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/writers/html.py |
| development | sympy__sympy-20428 | sympy/sympy | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/polys/domains/expressiondomain.py |
| development | sympy__sympy-14024 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/numbers.py |
| development | sympy__sympy-22402 | sympy/sympy | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/functions/elementary/complexes.py |
| development | sympy__sympy-14564 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/printing/latex.py<br>sympy/printing/pretty/pretty.py<br>sympy/printing/str.py |
| development | sympy__sympy-15948 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/add.py<br>sympy/core/exprtools.py<br>sympy/core/operations.py<br>sympy/matrices/expressions/trace.py |
| development | sympy__sympy-13286 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/solvers/decompogen.py |
| development | sympy__sympy-13279 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/core/add.py |
| development | sympy__sympy-16906 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/printing/pretty/pretty.py<br>sympy/printing/str.py |
| development | sympy__sympy-12227 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/printing/repr.py |
| development | sympy__sympy-12144 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/core/symbol.py<br>sympy/printing/repr.py |
| development | sympy__sympy-21208 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/matrices/expressions/matexpr.py |
| development | sympy__sympy-13895 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/numbers.py |
| development | sympy__sympy-21260 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/basic.py<br>sympy/core/numbers.py<br>sympy/core/singleton.py<br>sympy/functions/elementary/miscellaneous.py<br>sympy/physics/paulialgebra.py<br>sympy/sets/fancysets.py<br>sympy/sets/sets.py |
| development | sympy__sympy-13744 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/combinatorics/rewritingsystem.py |
| development | sympy__sympy-13091 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/exprtools.py<br>sympy/physics/optics/medium.py<br>sympy/physics/vector/dyadic.py<br>sympy/physics/vector/frame.py<br>sympy/physics/vector/vector.py<br>sympy/polys/agca/modules.py<br>sympy/polys/domains/domain.py<br>sympy/polys/domains/expressiondomain.py<br>sympy/polys/domains/pythonrational.py<br>sympy/polys/domains/quotientring.py<br>sympy/polys/fields.py<br>sympy/polys/monomials.py<br>sympy/polys/polyclasses.py<br>sympy/polys/polytools.py<br>sympy/polys/rings.py<br>sympy/polys/rootoftools.py<br>sympy/tensor/array/ndim_array.py<br>sympy/utilities/enumerative.py |
| development | sympy__sympy-22080 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/codeprinter.py<br>sympy/printing/precedence.py |
| development | sympy__sympy-11862 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/printing/lambdarepr.py<br>sympy/utilities/decorator.py<br>sympy/utilities/runtests.py |
| development | sympy__sympy-17720 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/ntheory/factor_.py |
| development | sympy__sympy-18198 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入Code Index | sympy/combinatorics/permutations.py<br>sympy/core/__init__.py<br>sympy/core/add.py<br>sympy/core/numbers.py<br>sympy/core/parameters.py<br>sympy/core/power.py<br>sympy/core/relational.py<br>sympy/geometry/ellipse.py<br>sympy/geometry/point.py<br>sympy/series/sequences.py<br>sympy/sets/sets.py<br>sympy/simplify/radsimp.py<br>sympy/simplify/simplify.py<br>sympy/stats/symbolic_probability.py<br>sympy/tensor/functions.py |
| development | sympy__sympy-17022 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/pycode.py |
| development | sympy__sympy-17394 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/printing/codeprinter.py<br>sympy/stats/crv_types.py |
| development | sympy__sympy-16056 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/core/numbers.py<br>sympy/diffgeom/diffgeom.py |
| development | sympy__sympy-20322 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/mul.py |
| development | sympy__sympy-18087 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/exprtools.py |
| development | sympy__sympy-13001 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/solvers/ode.py |
| development | sympy__sympy-12945 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/basic.py<br>sympy/utilities/lambdify.py |
| development | sympy__sympy-13619 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/calculus/util.py<br>sympy/core/basic.py |
| development | sympy__sympy-21432 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/functions/elementary/complexes.py |
| development | sympy__sympy-11384 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/latex.py<br>sympy/printing/pretty/pretty.py |
| development | sympy__sympy-13146 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/operations.py |
| development | sympy__sympy-13840 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/rcode.py |
| development | sympy__sympy-16088 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/physics/continuum_mechanics/beam.py |
| development | sympy__sympy-17239 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/printing/codeprinter.py |
| development | sympy__sympy-12236 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/polys/domains/polynomialring.py |
| development | sympy__sympy-16864 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/sets/contains.py |
| development | sympy__sympy-20590 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/_print_helpers.py |
| development | sympy__sympy-21379 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/mod.py |
| development | sympy__sympy-14248 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/printing/pretty/pretty.py |
| development | sympy__sympy-12108 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/assumptions/ask_generated.py<br>sympy/assumptions/sathandlers.py<br>sympy/concrete/delta.py<br>sympy/core/sympify.py<br>sympy/functions/special/bsplines.py<br>sympy/integrals/meijerint.py<br>sympy/logic/inference.py<br>sympy/logic/utilities/dimacs.py<br>sympy/plotting/experimental_lambdify.py<br>sympy/printing/precedence.py<br>sympy/solvers/inequalities.py<br>sympy/solvers/solvers.py<br>sympy/stats/crv_types.py<br>sympy/stats/rv.py |
| development | sympy__sympy-13806 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/printing/pretty/pretty.py<br>sympy/printing/pretty/stringpict.py |
| development | sympy__sympy-21931 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/calculus/singularities.py<br>sympy/calculus/util.py<br>sympy/categories/baseclasses.py<br>sympy/core/function.py<br>sympy/logic/boolalg.py<br>sympy/printing/str.py<br>sympy/solvers/inequalities.py<br>sympy/solvers/solveset.py<br>sympy/stats/rv_interface.py<br>sympy/stats/stochastic_process_types.py<br>sympy/vector/implicitregion.py |
| development | sympy__sympy-20691 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/core/kind.py<br>sympy/core/power.py<br>sympy/functions/elementary/exponential.py<br>sympy/matrices/expressions/determinant.py |
| development | sympy__sympy-16963 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/evalf.py<br>sympy/ntheory/factor_.py<br>sympy/tensor/indexed.py |
| development | sympy__sympy-13915 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/mul.py |
| development | sympy__sympy-18478 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/add.py |
| development | sympy__sympy-21627 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/functions/elementary/complexes.py |
| development | sympy__sympy-22383 | sympy/sympy | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | bin/authors_update.py<br>bin/mailmap_update.py<br>setup.py<br>sympy/__init__.py<br>sympy/core/numbers.py |
| development | sympy__sympy-15085 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/ccode.py<br>sympy/printing/codeprinter.py<br>sympy/printing/fcode.py<br>sympy/printing/glsl.py<br>sympy/printing/jscode.py<br>sympy/printing/julia.py<br>sympy/printing/mathematica.py<br>sympy/printing/octave.py |
| development | sympy__sympy-13198 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/polys/factortools.py |
