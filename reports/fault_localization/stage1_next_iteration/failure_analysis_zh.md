# 第一階段未命中案例分析

> 本報告只分析Top-20部分命中與完全未命中案例。舊Frozen Holdout只用於v1事後說明，不再作為v2獨立測試集。

## 一、資料範圍

| 資料組 | 用途 | 總Ticket | 完全找回 | 部分命中 | 完全未命中 |
|---|---|---:|---:|---:|---:|
| validation | method_selection | 500 | 376 | 73 | 51 |
| frozen_holdout_v1_posthoc | posthoc_description_only | 500 | 387 | 78 | 35 |

## 二、失敗環節

### validation

| 失敗環節 | Ticket數 |
|---|---:|
| 正確檔案未進入Code Index | 13 |
| 正確檔案未進入TF-IDF前50名 | 61 |
| 同一Ticket同時包含初步檢索與重新排序遺漏 | 15 |
| 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 35 |

### frozen_holdout_v1_posthoc

| 失敗環節 | Ticket數 |
|---|---:|
| 正確檔案未進入Code Index | 9 |
| 正確檔案未進入TF-IDF前50名 | 44 |
| 同一Ticket同時包含初步檢索與重新排序遺漏 | 30 |
| 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 30 |

## 三、結果判讀方式

- Index coverage failure：先修正索引範圍，排序模型無法找回不存在的候選。
- Initial retrieval miss：優先改善TF-IDF候選池、查詢擴充或Repository大小調整。
- Reranker demotion：優先檢查SBERT排序與檔案分數整合。
- Cross-file partial miss：優先檢查Import／Call Graph是否能補回其他檔案。
- Analysis unavailable：先補齊Code Index或TF-IDF前50資料，再做人工判讀。

## 四、案例清單

| 資料組 | Ticket | Repository | 結果 | 失敗環節 | 遺漏檔案 |
|---|---|---|---|---|---|
| validation | astropy__astropy-13398 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入Code Index | astropy/coordinates/builtin_frames/itrs_observed_transforms.py |
| validation | astropy__astropy-8715 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | astropy/io/votable/validator/result.py |
| validation | astropy__astropy-12842 | astropy/astropy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | astropy/time/formats.py |
| validation | astropy__astropy-13132 | astropy/astropy | 正確檔案未進入Code Index | 正確檔案未進入Code Index | astropy/time/core.py<br>astropy/time/time_helper/__init__.py<br>astropy/time/time_helper/function_helpers.py |
| validation | astropy__astropy-13438 | astropy/astropy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | astropy/table/jsviewer.py |
| validation | django__django-11539 | django/django | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/models/base.py<br>django/db/models/indexes.py |
| validation | django__django-13841 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/auth/password_validation.py<br>django/forms/renderers.py<br>django/utils/version.py |
| validation | django__django-14387 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/utils/tree.py |
| validation | django__django-14681 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/middleware/csrf.py |
| validation | django__django-10853 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/backends/oracle/features.py |
| validation | django__django-16117 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/migrations/migration.py |
| validation | django__django-11740 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/migrations/autodetector.py |
| validation | django__django-12161 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/utils.py |
| validation | django__django-13240 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/auth/tokens.py |
| validation | django__django-11983 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/admin/views/main.py |
| validation | django__django-15248 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/contenttypes/management/commands/remove_stale_contenttypes.py |
| validation | django__django-11278 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/core/checks/model_checks.py |
| validation | django__django-10301 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/oracle/operations.py<br>django/db/models/functions/datetime.py<br>django/db/models/functions/text.py |
| validation | django__django-16037 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/expressions.py |
| validation | django__django-16735 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/utils/translation/__init__.py |
| validation | django__django-12734 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/backends/sqlite3/schema.py |
| validation | django__django-8119 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/base/operations.py<br>django/db/backends/oracle/operations.py |
| validation | django__django-11734 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/__init__.py<br>django/db/models/fields/related_lookups.py |
| validation | django__django-12508 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/backends/base/client.py<br>django/db/backends/mysql/client.py<br>django/db/backends/mysql/creation.py<br>django/db/backends/oracle/client.py<br>django/db/backends/postgresql/client.py<br>django/db/backends/sqlite3/client.py |
| validation | django__django-12671 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/core/management/commands/loaddata.py |
| validation | django__django-12091 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/views/debug.py<br>django/views/i18n.py |
| validation | django__django-16707 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/utils/functional.py |
| validation | django__django-14480 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/base/features.py<br>django/db/models/sql/__init__.py<br>django/db/models/sql/where.py |
| validation | django__django-13484 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/reverse_related.py |
| validation | django__django-11299 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/sql/query.py |
| validation | django__django-14351 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/lookups.py |
| validation | django__django-12910 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/core/management/base.py<br>django/core/management/commands/createcachetable.py<br>django/core/management/commands/runserver.py<br>django/core/management/templates.py |
| validation | django__django-14124 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/admindocs/utils.py<br>django/views/debug.py |
| validation | django__django-13371 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/utils.py |
| validation | django__django-11638 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/utils/http.py |
| validation | django__django-10904 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/auth/password_validation.py<br>django/contrib/gis/gdal/libgdal.py<br>django/contrib/sessions/backends/file.py<br>django/contrib/staticfiles/storage.py<br>django/core/files/move.py<br>django/core/files/storage.py<br>django/core/management/commands/compilemessages.py<br>django/core/management/templates.py<br>django/core/servers/basehttp.py<br>django/http/request.py<br>django/middleware/csrf.py<br>django/utils/translation/trans_real.py |
| validation | django__django-11991 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/gis/db/backends/postgis/schema.py<br>django/db/models/base.py<br>django/db/models/constraints.py |
| validation | django__django-12062 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/utils.py |
| validation | django__django-13682 | django/django | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/urls/conf.py<br>django/urls/resolvers.py |
| validation | matplotlib__matplotlib-25346 | matplotlib/matplotlib | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/text.py |
| validation | matplotlib__matplotlib-19743 | matplotlib/matplotlib | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | examples/text_labels_and_annotations/figlegend_demo.py<br>lib/matplotlib/axes/_axes.py |
| validation | matplotlib__matplotlib-24257 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | setup.py |
| validation | matplotlib__matplotlib-24250 | matplotlib/matplotlib | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | lib/matplotlib/figure.py |
| validation | matplotlib__matplotlib-23174 | matplotlib/matplotlib | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | lib/matplotlib/figure.py |
| validation | matplotlib__matplotlib-25515 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入Code Index | doc/conf.py<br>lib/matplotlib/sphinxext/figmpl_directive.py |
| validation | matplotlib__matplotlib-13980 | matplotlib/matplotlib | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/axes/_base.py |
| validation | matplotlib__matplotlib-24538 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | lib/matplotlib/patches.py |
| validation | matplotlib__matplotlib-20470 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/text.py |
| validation | matplotlib__matplotlib-24691 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入Code Index | galleries/examples/color/set_alpha.py<br>galleries/users_explain/colors/colors.py |
| validation | matplotlib__matplotlib-24619 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/collections.py |
| validation | matplotlib__matplotlib-26479 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/rcsetup.py |
| validation | matplotlib__matplotlib-24013 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入Code Index | lib/matplotlib/tri/_triangulation.py<br>lib/matplotlib/tri/_tricontour.py<br>lib/matplotlib/tri/_trifinder.py<br>lib/matplotlib/tri/_triinterpolate.py<br>lib/matplotlib/tri/_tripcolor.py<br>lib/matplotlib/tri/_triplot.py<br>lib/matplotlib/tri/_trirefine.py<br>lib/matplotlib/tri/_tritools.py<br>lib/matplotlib/tri/triangulation.py<br>lib/matplotlib/tri/tricontour.py<br>lib/matplotlib/tri/trifinder.py<br>lib/matplotlib/tri/triinterpolate.py<br>lib/matplotlib/tri/triplot.py<br>lib/matplotlib/tri/trirefine.py<br>lib/matplotlib/tri/tritools.py<br>lib/mpl_toolkits/mplot3d/axes3d.py |
| validation | matplotlib__matplotlib-23198 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/backends/qt_editor/figureoptions.py |
| validation | matplotlib__matplotlib-21550 | matplotlib/matplotlib | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/collections.py |
| validation | matplotlib__matplotlib-26466 | matplotlib/matplotlib | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | lib/matplotlib/text.py |
| validation | mwaskom__seaborn-3216 | mwaskom/seaborn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | seaborn/_compat.py |
| validation | mwaskom__seaborn-2766 | mwaskom/seaborn | 只找回部分正確檔案 | 正確檔案未進入Code Index | seaborn/external/version.py |
| validation | pydata__xarray-6804 | pydata/xarray | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | xarray/core/duck_array_ops.py<br>xarray/core/utils.py |
| validation | pydata__xarray-7444 | pydata/xarray | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/groupby.py<br>xarray/core/pdcompat.py |
| validation | pydata__xarray-7019 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | xarray/backends/api.py<br>xarray/backends/common.py<br>xarray/backends/plugins.py<br>xarray/backends/zarr.py<br>xarray/coding/strings.py<br>xarray/coding/variables.py<br>xarray/core/daskmanager.py<br>xarray/core/duck_array_ops.py<br>xarray/core/missing.py<br>xarray/core/parallelcompat.py<br>xarray/core/pycompat.py<br>xarray/core/rolling.py<br>xarray/core/utils.py |
| validation | pydata__xarray-7347 | pydata/xarray | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/merge.py |
| validation | pydata__xarray-5731 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | xarray/core/pycompat.py |
| validation | pydata__xarray-5455 | pydata/xarray | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/backends/cfgrib_.py |
| validation | pydata__xarray-7052 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | xarray/core/alignment.py<br>xarray/core/pycompat.py<br>xarray/plot/accessor.py<br>xarray/plot/dataarray_plot.py |
| validation | pydata__xarray-5187 | pydata/xarray | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/duck_array_ops.py |
| validation | pydata__xarray-5233 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | xarray/__init__.py<br>xarray/coding/calendar_ops.py |
| validation | pydata__xarray-2922 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | xarray/core/weighted.py |
| validation | pylint-dev__pylint-6412 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/reporters/base_reporter.py |
| validation | pylint-dev__pylint-8757 | pylint-dev/pylint | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | pylint/checkers/similar.py<br>pylint/lint/parallel.py |
| validation | pylint-dev__pylint-8898 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | pylint/utils/utils.py |
| validation | pylint-dev__pylint-6526 | pylint-dev/pylint | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | pylint/lint/caching.py |
| validation | pytest-dev__pytest-5840 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/config/__init__.py<br>src/_pytest/pathlib.py |
| validation | pytest-dev__pytest-8463 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入Code Index | src/_pytest/config/compat.py<br>src/_pytest/deprecated.py<br>src/_pytest/main.py<br>src/_pytest/python.py |
| validation | pytest-dev__pytest-6214 | pytest-dev/pytest | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | src/_pytest/setupplan.py |
| validation | pytest-dev__pytest-7985 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/main.py<br>src/_pytest/mark/structures.py |
| validation | pytest-dev__pytest-10758 | pytest-dev/pytest | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | src/_pytest/assertion/rewrite.py |
| validation | pytest-dev__pytest-7982 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/pathlib.py |
| validation | pytest-dev__pytest-9956 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | src/_pytest/warning_types.py<br>src/pytest/__init__.py |
| validation | scikit-learn__scikit-learn-15495 | scikit-learn/scikit-learn | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sklearn/tree/_classes.py |
| validation | scikit-learn__scikit-learn-14067 | scikit-learn/scikit-learn | 正確檔案未進入Code Index | 正確檔案未進入Code Index | sklearn/externals/_scipy_linalg.py<br>sklearn/linear_model/bayes.py<br>sklearn/utils/fixes.py |
| validation | scikit-learn__scikit-learn-25697 | scikit-learn/scikit-learn | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sklearn/linear_model/_bayes.py |
| validation | scikit-learn__scikit-learn-14125 | scikit-learn/scikit-learn | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sklearn/utils/multiclass.py |
| validation | scikit-learn__scikit-learn-13536 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sklearn/ensemble/gradient_boosting.py |
| validation | scikit-learn__scikit-learn-12557 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | examples/svm/plot_svm_tie_breaking.py |
| validation | scikit-learn__scikit-learn-25102 | scikit-learn/scikit-learn | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sklearn/base.py<br>sklearn/feature_selection/_base.py |
| validation | sphinx-doc__sphinx-8278 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/pycode/ast.py<br>sphinx/util/inspect.py |
| validation | sphinx-doc__sphinx-8265 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/pycode/ast.py |
| validation | sphinx-doc__sphinx-9987 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/pycode/parser.py |
| validation | sphinx-doc__sphinx-10353 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/util/inspect.py |
| validation | sphinx-doc__sphinx-8058 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/util/i18n.py |
| validation | sphinx-doc__sphinx-11510 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/directives/other.py |
| validation | sphinx-doc__sphinx-8674 | sphinx-doc/sphinx | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sphinx/writers/html.py<br>sphinx/writers/html5.py |
| validation | sphinx-doc__sphinx-7930 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/python.py |
| validation | sphinx-doc__sphinx-10207 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/builders/latex/transforms.py<br>sphinx/util/typing.py<br>sphinx/writers/html.py<br>sphinx/writers/latex.py |
| validation | sphinx-doc__sphinx-7356 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/util/nodes.py |
| validation | sphinx-doc__sphinx-9261 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/util/inspect.py |
| validation | sphinx-doc__sphinx-8075 | sphinx-doc/sphinx | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sphinx/domains/std.py<br>sphinx/events.py<br>sphinx/transforms/post_transforms/__init__.py |
| validation | sphinx-doc__sphinx-9997 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/python.py<br>sphinx/util/inspect.py |
| validation | sphinx-doc__sphinx-9665 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/util/typing.py |
| validation | sphinx-doc__sphinx-9459 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/util/typing.py |
| validation | sphinx-doc__sphinx-10360 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/util/cfamily.py |
| validation | sphinx-doc__sphinx-9654 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sphinx/util/inspect.py |
| validation | sympy__sympy-15586 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/matrices/expressions/inverse.py<br>sympy/printing/pycode.py<br>sympy/printing/str.py |
| validation | sympy__sympy-18477 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/printing/jscode.py |
| validation | sympy__sympy-17340 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/printing/pycode.py<br>sympy/printing/tensorflow.py |
| validation | sympy__sympy-18650 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/power.py |
| validation | sympy__sympy-19182 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/mul.py |
| validation | sympy__sympy-20134 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/pycode.py |
| validation | sympy__sympy-20438 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/sets/handlers/issubset.py |
| validation | sympy__sympy-19040 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/polys/factortools.py |
| validation | sympy__sympy-14166 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/latex.py |
| validation | sympy__sympy-21527 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/polys/constructor.py<br>sympy/polys/matrices/ddm.py<br>sympy/polys/matrices/dense.py<br>sympy/polys/matrices/sdm.py |
| validation | sympy__sympy-16901 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/codegen/pyutils.py<br>sympy/polys/numberfields.py<br>sympy/printing/lambdarepr.py<br>sympy/printing/str.py |
| validation | sympy__sympy-19601 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/simplify/radsimp.py |
| validation | sympy__sympy-20801 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/numbers.py |
| validation | sympy__sympy-21952 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/core/numbers.py |
| validation | sympy__sympy-13346 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/pycode.py |
| validation | sympy__sympy-13877 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/utilities/randtest.py |
| validation | sympy__sympy-18168 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/sets/fancysets.py<br>sympy/sets/handlers/union.py |
| validation | sympy__sympy-12881 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/solvers/polysys.py |
| validation | sympy__sympy-17223 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/mul.py |
| validation | sympy__sympy-15446 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/core/function.py<br>sympy/printing/precedence.py |
| validation | sympy__sympy-15933 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | examples/advanced/grover_example.py<br>sympy/physics/quantum/qexpr.py |
| validation | sympy__sympy-15596 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/calculus/util.py |
| frozen_holdout_v1_posthoc | astropy__astropy-14439 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | astropy/modeling/physical_models.py |
| frozen_holdout_v1_posthoc | astropy__astropy-13075 | astropy/astropy | 只找回部分正確檔案 | 正確檔案未進入Code Index | astropy/cosmology/io/html.py |
| frozen_holdout_v1_posthoc | astropy__astropy-13158 | astropy/astropy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | astropy/modeling/bounding_box.py<br>astropy/modeling/functional_models.py<br>astropy/modeling/parameters.py<br>astropy/modeling/powerlaws.py<br>astropy/modeling/rotations.py<br>astropy/modeling/utils.py |
| frozen_holdout_v1_posthoc | astropy__astropy-14566 | astropy/astropy | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | astropy/time/formats.py |
| frozen_holdout_v1_posthoc | astropy__astropy-14907 | astropy/astropy | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | astropy/table/index.py<br>astropy/time/core.py |
| frozen_holdout_v1_posthoc | astropy__astropy-8707 | astropy/astropy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | astropy/io/fits/card.py |
| frozen_holdout_v1_posthoc | django__django-17046 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/admin/views/main.py |
| frozen_holdout_v1_posthoc | django__django-11281 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/admin/models.py<br>django/contrib/admin/options.py<br>django/contrib/auth/forms.py<br>django/contrib/auth/password_validation.py<br>django/contrib/contenttypes/views.py<br>django/contrib/flatpages/forms.py<br>django/contrib/flatpages/migrations/0001_initial.py<br>django/contrib/flatpages/models.py<br>django/contrib/gis/db/models/fields.py<br>django/contrib/gis/views.py<br>django/contrib/postgres/fields/hstore.py<br>django/contrib/postgres/forms/jsonb.py<br>django/contrib/redirects/migrations/0001_initial.py<br>django/contrib/redirects/models.py<br>django/core/validators.py<br>django/db/models/fields/__init__.py<br>django/forms/models.py<br>django/forms/utils.py<br>django/views/generic/dates.py<br>django/views/generic/list.py<br>django/views/static.py |
| frozen_holdout_v1_posthoc | django__django-12431 | django/django | 同一Ticket同時包含初步檢索與重新排序遺漏 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/core/handlers/base.py<br>django/core/handlers/wsgi.py<br>django/http/response.py |
| frozen_holdout_v1_posthoc | django__django-5470 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/__init__.py<br>django/core/wsgi.py |
| frozen_holdout_v1_posthoc | django__django-11532 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/utils/html.py |
| frozen_holdout_v1_posthoc | django__django-15747 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/backends/mysql/features.py |
| frozen_holdout_v1_posthoc | django__django-14374 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/sessions/backends/file.py<br>django/contrib/sitemaps/views.py<br>django/contrib/syndication/views.py<br>django/core/cache/backends/db.py<br>django/http/response.py<br>django/utils/dateformat.py<br>django/utils/http.py<br>django/utils/version.py<br>django/views/decorators/http.py |
| frozen_holdout_v1_posthoc | django__django-12855 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/views/i18n.py |
| frozen_holdout_v1_posthoc | django__django-12198 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/sql/query.py<br>django/template/base.py |
| frozen_holdout_v1_posthoc | django__django-14463 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/mysql/introspection.py<br>django/db/backends/oracle/features.py<br>django/db/backends/postgresql/features.py<br>django/db/backends/postgresql/introspection.py<br>django/db/migrations/autodetector.py<br>django/db/migrations/operations/__init__.py<br>django/db/migrations/operations/models.py<br>django/db/models/base.py<br>django/db/models/options.py |
| frozen_holdout_v1_posthoc | django__django-10910 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/backends/sqlite3/base.py |
| frozen_holdout_v1_posthoc | django__django-15561 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/fields/__init__.py |
| frozen_holdout_v1_posthoc | django__django-16111 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/functions/datetime.py |
| frozen_holdout_v1_posthoc | django__django-15127 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/contrib/messages/apps.py |
| frozen_holdout_v1_posthoc | django__django-16657 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/backends/mysql/features.py |
| frozen_holdout_v1_posthoc | django__django-11808 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/postgres/constraints.py<br>django/core/validators.py<br>django/db/models/constraints.py<br>django/db/models/expressions.py<br>django/db/models/indexes.py<br>django/db/models/query.py<br>django/db/models/query_utils.py<br>django/template/context.py |
| frozen_holdout_v1_posthoc | django__django-13300 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/models/expressions.py |
| frozen_holdout_v1_posthoc | django__django-14026 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/postgres/aggregates/general.py<br>django/contrib/postgres/aggregates/statistics.py<br>django/db/backends/mysql/features.py |
| frozen_holdout_v1_posthoc | django__django-16092 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/db/backends/base/features.py<br>django/db/backends/mysql/features.py<br>django/db/backends/oracle/features.py<br>django/db/backends/oracle/introspection.py<br>django/db/backends/postgresql/features.py<br>django/db/backends/sqlite3/features.py<br>django/db/backends/sqlite3/schema.py<br>django/db/migrations/autodetector.py<br>django/db/models/expressions.py<br>django/db/models/functions/comparison.py<br>django/db/models/lookups.py<br>django/db/models/query.py |
| frozen_holdout_v1_posthoc | django__django-10989 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/contrib/gis/utils/layermapping.py<br>django/core/management/commands/loaddata.py<br>django/core/management/commands/migrate.py<br>django/core/management/commands/showmigrations.py<br>django/core/management/commands/squashmigrations.py<br>django/db/backends/base/creation.py<br>django/db/backends/mysql/creation.py<br>django/db/backends/oracle/creation.py<br>django/db/backends/postgresql/creation.py<br>django/db/backends/sqlite3/creation.py<br>django/db/models/query.py<br>django/db/models/sql/query.py |
| frozen_holdout_v1_posthoc | django__django-11214 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/serializer.py |
| frozen_holdout_v1_posthoc | django__django-13606 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/lookups.py |
| frozen_holdout_v1_posthoc | django__django-16263 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/expressions.py |
| frozen_holdout_v1_posthoc | django__django-15973 | django/django | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | django/db/migrations/autodetector.py |
| frozen_holdout_v1_posthoc | django__django-16757 | django/django | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/contrib/admin/checks.py |
| frozen_holdout_v1_posthoc | django__django-12518 | django/django | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | django/db/migrations/loader.py |
| frozen_holdout_v1_posthoc | django__django-16952 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/db/models/options.py |
| frozen_holdout_v1_posthoc | django__django-16938 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/core/serializers/xml_serializer.py |
| frozen_holdout_v1_posthoc | django__django-15774 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/utils/translation/trans_null.py |
| frozen_holdout_v1_posthoc | django__django-16302 | django/django | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | django/core/management/commands/inspectdb.py<br>django/db/backends/base/features.py<br>django/db/backends/postgresql/base.py<br>django/db/backends/postgresql/features.py |
| frozen_holdout_v1_posthoc | django__django-15316 | django/django | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | django/contrib/admindocs/utils.py |
| frozen_holdout_v1_posthoc | matplotlib__matplotlib-21490 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | examples/units/basic_units.py |
| frozen_holdout_v1_posthoc | matplotlib__matplotlib-25859 | matplotlib/matplotlib | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | lib/matplotlib/axes/_axes.py<br>lib/matplotlib/pyplot.py |
| frozen_holdout_v1_posthoc | matplotlib__matplotlib-13983 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | lib/matplotlib/axis.py |
| frozen_holdout_v1_posthoc | matplotlib__matplotlib-14623 | matplotlib/matplotlib | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/axes/_base.py<br>lib/matplotlib/ticker.py<br>lib/mpl_toolkits/mplot3d/axes3d.py |
| frozen_holdout_v1_posthoc | matplotlib__matplotlib-23573 | matplotlib/matplotlib | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | lib/matplotlib/_constrained_layout.py<br>lib/matplotlib/axes/__init__.py<br>lib/matplotlib/colorbar.py<br>lib/matplotlib/figure.py<br>lib/matplotlib/pyplot.py<br>lib/mpl_toolkits/axes_grid1/axes_divider.py<br>lib/mpl_toolkits/axes_grid1/axes_rgb.py<br>lib/mpl_toolkits/axes_grid1/parasite_axes.py<br>lib/mpl_toolkits/axisartist/__init__.py<br>lib/mpl_toolkits/axisartist/axislines.py<br>lib/mpl_toolkits/axisartist/floating_axes.py<br>lib/mpl_toolkits/axisartist/parasite_axes.py<br>tutorials/intermediate/artists.py |
| frozen_holdout_v1_posthoc | matplotlib__matplotlib-20518 | matplotlib/matplotlib | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | lib/matplotlib/artist.py |
| frozen_holdout_v1_posthoc | mwaskom__seaborn-3394 | mwaskom/seaborn | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | seaborn/_core/plot.py<br>seaborn/_core/rules.py<br>seaborn/_oldcore.py |
| frozen_holdout_v1_posthoc | pydata__xarray-6971 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入Code Index | xarray/indexes/__init__.py |
| frozen_holdout_v1_posthoc | pydata__xarray-6400 | pydata/xarray | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/formatting.py<br>xarray/core/options.py |
| frozen_holdout_v1_posthoc | pydata__xarray-4442 | pydata/xarray | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/coordinates.py |
| frozen_holdout_v1_posthoc | pydata__xarray-7229 | pydata/xarray | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | xarray/core/computation.py |
| frozen_holdout_v1_posthoc | pydata__xarray-3302 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | doc/conf.py |
| frozen_holdout_v1_posthoc | pydata__xarray-5365 | pydata/xarray | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | xarray/__init__.py |
| frozen_holdout_v1_posthoc | pydata__xarray-4759 | pydata/xarray | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | xarray/core/merge.py<br>xarray/core/utils.py<br>xarray/core/variable.py |
| frozen_holdout_v1_posthoc | pydata__xarray-7105 | pydata/xarray | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | xarray/core/alignment.py<br>xarray/core/utils.py |
| frozen_holdout_v1_posthoc | pylint-dev__pylint-4330 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | pylint/testutils/decorator.py |
| frozen_holdout_v1_posthoc | pylint-dev__pylint-6937 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/lint/base_options.py<br>pylint/lint/message_state_handler.py |
| frozen_holdout_v1_posthoc | pylint-dev__pylint-4661 | pylint-dev/pylint | 只找回部分正確檔案 | 正確檔案未進入Code Index | setup.cfg |
| frozen_holdout_v1_posthoc | pylint-dev__pylint-5839 | pylint-dev/pylint | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | pylint/checkers/__init__.py<br>pylint/constants.py |
| frozen_holdout_v1_posthoc | pylint-dev__pylint-8169 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/checkers/variables.py |
| frozen_holdout_v1_posthoc | pylint-dev__pylint-4175 | pylint-dev/pylint | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | pylint/lint/parallel.py |
| frozen_holdout_v1_posthoc | pytest-dev__pytest-7535 | pytest-dev/pytest | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/_code/code.py |
| frozen_holdout_v1_posthoc | pytest-dev__pytest-5559 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | doc/en/example/nonpython/conftest.py<br>src/_pytest/_code/code.py |
| frozen_holdout_v1_posthoc | pytest-dev__pytest-7637 | pytest-dev/pytest | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | src/_pytest/hookspec.py<br>src/_pytest/mark/__init__.py<br>src/pytest/collect.py |
| frozen_holdout_v1_posthoc | pytest-dev__pytest-7122 | pytest-dev/pytest | 正確檔案未進入Code Index | 正確檔案未進入Code Index | src/_pytest/mark/expression.py<br>src/_pytest/mark/legacy.py |
| frozen_holdout_v1_posthoc | pytest-dev__pytest-7648 | pytest-dev/pytest | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | src/_pytest/deprecated.py<br>src/_pytest/main.py<br>src/_pytest/nodes.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-10382 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sklearn/exceptions.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-11585 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | examples/decomposition/plot_faces_decomposition.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-13915 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sklearn/__init__.py<br>sklearn/cross_decomposition/pls_.py<br>sklearn/experimental/enable_iterative_imputer.py<br>sklearn/metrics/classification.py<br>sklearn/preprocessing/_encoders.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-12784 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | build_tools/generate_authors_table.py<br>examples/applications/plot_stock_market.py<br>examples/compose/plot_transformed_target.py<br>examples/mixture/plot_gmm_covariances.py<br>examples/neighbors/plot_kde_1d.py<br>examples/plot_anomaly_comparison.py<br>examples/plot_johnson_lindenstrauss_bound.py<br>examples/text/plot_document_classification_20newsgroups.py<br>sklearn/compose/_column_transformer.py<br>sklearn/feature_extraction/text.py<br>sklearn/linear_model/logistic.py<br>sklearn/metrics/regression.py<br>sklearn/neural_network/multilayer_perceptron.py<br>sklearn/preprocessing/data.py<br>sklearn/svm/base.py<br>sklearn/utils/testing.py<br>sklearn/utils/validation.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-14464 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sklearn/gaussian_process/kernels.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-10427 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | sklearn/externals/_pilutil.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-10331 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sklearn/grid_search.py<br>sklearn/model_selection/_search.py<br>sklearn/svm/base.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-11596 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 正確檔案未進入Code Index | sklearn/utils/_show_versions.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-13436 | scikit-learn/scikit-learn | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sklearn/base.py |
| frozen_holdout_v1_posthoc | scikit-learn__scikit-learn-11206 | scikit-learn/scikit-learn | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sklearn/preprocessing/data.py<br>sklearn/utils/estimator_checks.py<br>sklearn/utils/extmath.py<br>sklearn/utils/sparsefuncs.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-8679 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/domains/std.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-9128 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/python.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-9982 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/util/logging.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-8264 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/util/typing.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-10673 | sphinx-doc/sphinx | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/environment/collectors/toctree.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-10067 | sphinx-doc/sphinx | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sphinx/builders/latex/__init__.py<br>sphinx/builders/latex/util.py<br>sphinx/config.py<br>sphinx/environment/__init__.py<br>sphinx/environment/collectors/asset.py<br>sphinx/util/i18n.py<br>sphinx/writers/latex.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-7615 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/transforms/__init__.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-9658 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/ext/autodoc/mock.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-9104 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/domains/python.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-9230 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/util/docfields.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-7593 | sphinx-doc/sphinx | 正確檔案未進入Code Index | 正確檔案未進入Code Index | sphinx/builders/html/__init__.py<br>sphinx/builders/html/transforms.py<br>sphinx/util/nodes.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-8633 | sphinx-doc/sphinx | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sphinx/ext/autodoc/__init__.py |
| frozen_holdout_v1_posthoc | sphinx-doc__sphinx-10449 | sphinx-doc/sphinx | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sphinx/ext/autodoc/typehints.py |
| frozen_holdout_v1_posthoc | sympy__sympy-13682 | sympy/sympy | 正確檔案未進入Code Index | 正確檔案未進入Code Index | sympy/printing/str.py<br>sympy/sets/__init__.py<br>sympy/sets/ordinals.py |
| frozen_holdout_v1_posthoc | sympy__sympy-16597 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/assumptions/ask.py<br>sympy/assumptions/ask_generated.py<br>sympy/printing/tree.py<br>sympy/tensor/indexed.py |
| frozen_holdout_v1_posthoc | sympy__sympy-13301 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/calculus/util.py |
| frozen_holdout_v1_posthoc | sympy__sympy-20139 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/symbol.py<br>sympy/printing/dot.py |
| frozen_holdout_v1_posthoc | sympy__sympy-18211 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/core/relational.py |
| frozen_holdout_v1_posthoc | sympy__sympy-11232 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/matrices/expressions/matmul.py |
| frozen_holdout_v1_posthoc | sympy__sympy-21586 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/abc.py<br>sympy/core/assumptions.py |
| frozen_holdout_v1_posthoc | sympy__sympy-12906 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/concrete/summations.py |
| frozen_holdout_v1_posthoc | sympy__sympy-17845 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/calculus/singularities.py<br>sympy/categories/baseclasses.py<br>sympy/combinatorics/partitions.py<br>sympy/combinatorics/polyhedron.py<br>sympy/core/function.py<br>sympy/logic/boolalg.py<br>sympy/printing/str.py<br>sympy/sets/conditionset.py<br>sympy/sets/powerset.py<br>sympy/solvers/inequalities.py<br>sympy/solvers/solveset.py<br>sympy/stats/stochastic_process_types.py |
| frozen_holdout_v1_posthoc | sympy__sympy-12286 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/core/symbol.py<br>sympy/printing/repr.py |
| frozen_holdout_v1_posthoc | sympy__sympy-20115 | sympy/sympy | 正確檔案未進入TF-IDF前50名 | 正確檔案未進入TF-IDF前50名 | sympy/printing/pycode.py |
| frozen_holdout_v1_posthoc | sympy__sympy-13309 | sympy/sympy | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/functions/elementary/miscellaneous.py |
| frozen_holdout_v1_posthoc | sympy__sympy-16858 | sympy/sympy | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/stats/crv_types.py<br>sympy/stats/joint_rv_types.py |
| frozen_holdout_v1_posthoc | sympy__sympy-21932 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/stats/stochastic_process_types.py |
| frozen_holdout_v1_posthoc | sympy__sympy-17251 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/physics/matrices.py |
| frozen_holdout_v1_posthoc | sympy__sympy-17271 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/printing/latex.py |
| frozen_holdout_v1_posthoc | sympy__sympy-15198 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/combinatorics/homomorphisms.py<br>sympy/printing/ccode.py<br>sympy/printing/codeprinter.py<br>sympy/printing/fcode.py<br>sympy/printing/glsl.py<br>sympy/printing/mathematica.py<br>sympy/utilities/lambdify.py<br>sympy/utilities/runtests.py |
| frozen_holdout_v1_posthoc | sympy__sympy-18116 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/codegen/array_utils.py<br>sympy/core/decorators.py<br>sympy/core/numbers.py<br>sympy/sets/sets.py<br>sympy/simplify/trigsimp.py<br>sympy/solvers/ode.py |
| frozen_holdout_v1_posthoc | sympy__sympy-18200 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/solvers/diophantine.py |
| frozen_holdout_v1_posthoc | sympy__sympy-12088 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/polys/fields.py<br>sympy/simplify/simplify.py |
| frozen_holdout_v1_posthoc | sympy__sympy-18667 | sympy/sympy | 正確檔案未進入Code Index | 正確檔案未進入Code Index | sympy/combinatorics/schur_number.py |
| frozen_holdout_v1_posthoc | sympy__sympy-14085 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/parsing/sympy_tokenize.py |
| frozen_holdout_v1_posthoc | sympy__sympy-18587 | sympy/sympy | 只找回部分正確檔案 | 正確檔案在TF-IDF前50名，但被SBERT排出前20名 | sympy/matrices/common.py |
| frozen_holdout_v1_posthoc | sympy__sympy-19093 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/assumptions/handlers/matrices.py<br>sympy/matrices/expressions/determinant.py<br>sympy/matrices/expressions/inverse.py<br>sympy/matrices/expressions/matadd.py<br>sympy/matrices/expressions/matmul.py<br>sympy/matrices/expressions/matpow.py<br>sympy/matrices/matrices.py<br>sympy/solvers/solvers.py<br>sympy/stats/stochastic_process_types.py |
| frozen_holdout_v1_posthoc | sympy__sympy-12472 | sympy/sympy | 只找回部分正確檔案 | 正確檔案未進入TF-IDF前50名 | sympy/core/power.py<br>sympy/simplify/hyperexpand.py |
| frozen_holdout_v1_posthoc | sympy__sympy-13236 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/core/assumptions.py<br>sympy/core/exprtools.py<br>sympy/ntheory/factor_.py |
| frozen_holdout_v1_posthoc | sympy__sympy-18033 | sympy/sympy | 只找回部分正確檔案 | 同一Ticket同時包含初步檢索與重新排序遺漏 | sympy/codegen/array_utils.py<br>sympy/combinatorics/generators.py<br>sympy/combinatorics/homomorphisms.py<br>sympy/combinatorics/named_groups.py<br>sympy/combinatorics/perm_groups.py<br>sympy/combinatorics/polyhedron.py<br>sympy/combinatorics/tensor_can.py<br>sympy/combinatorics/util.py<br>sympy/printing/latex.py<br>sympy/printing/repr.py |
