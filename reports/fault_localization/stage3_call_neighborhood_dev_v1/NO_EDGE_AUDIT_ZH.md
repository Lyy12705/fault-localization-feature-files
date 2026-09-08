# WP3 無呼叫邊案例審核

- 審核案例：22
- Base source 載入失敗：0
- Base target 找不到：0
- 完整索引圖已有 incident edge：21
- 完整索引圖的相鄰 symbol 也在候選池：20

## 主因統計

| 主因 | 數量 |
|---|---:|
| `dynamic_dispatch` | 1 |
| `import_resolution` | 5 |
| `source_reconstruction` | 15 |
| `stage2_pool_scope` | 1 |

`source_reconstruction` 表示同檔完整索引邊在 symbol-only pool 重建時消失；`import_resolution` 表示跨檔完整索引邊在重建時消失。兩者都不代表 base source 或目標定義缺失。

## 逐筆分類

| Ticket | Symbol | 主因 | 信心 | 關鍵證據 |
|---|---|---|---|---|
| `astropy__astropy-14598` | `Card._split` | `source_reconstruction` | high | astropy/io/fits/card.py::Card._fix_value<br>astropy/io/fits/card.py::Card._itersubcards<br>astropy/io/fits/card.py::Card |
| `django__django-15139` | `RedisSerializer.loads` | `dynamic_dispatch` | medium | django/core/cache/backends/redis.py::self._serializer.loads<br>django/core/serializers/base.py::pickle.loads |
| `matplotlib__matplotlib-23057` | `_get_backend_mod` | `source_reconstruction` | high | lib/matplotlib/pyplot.py::_warn_if_gui_out_of_main_thread<br>lib/matplotlib/pyplot.py::draw_if_interactive<br>lib/matplo |
| `matplotlib__matplotlib-25404` | `SpanSelector.__init__` | `source_reconstruction` | high | lib/matplotlib/cbook.py::normalize_kwargs<br>lib/matplotlib/widgets.py::SpanSelector._setup_edge_handles<br>lib/matplotl |
| `matplotlib__matplotlib-25404` | `SpanSelector.new_axes` | `source_reconstruction` | high | lib/matplotlib/patches.py::Rectangle<br>lib/matplotlib/widgets.py::SpanSelector.__init__<br>lib/matplotlib/widgets.py::S |
| `matplotlib__matplotlib-25404` | `RectangleSelector.__init__` | `import_resolution` | high | lib/matplotlib/_api/__init__.py::check_in_list<br>lib/matplotlib/cbook.py::normalize_kwargs<br>lib/matplotlib/widgets.py |
| `matplotlib__matplotlib-25404` | `PolygonSelector.__init__` | `source_reconstruction` | high | lib/matplotlib/lines.py::Line2D<br>lib/matplotlib/widgets.py::ToolHandles |
| `mwaskom__seaborn-2389` | `_HeatMapper` | `source_reconstruction` | high | seaborn/matrix.py::heatmap |
| `mwaskom__seaborn-2389` | `_HeatMapper.__init__` | `source_reconstruction` | high | seaborn/matrix.py::_HeatMapper._determine_cmap_params<br>seaborn/matrix.py::_HeatMapper._skip_ticks<br>seaborn/matrix.py |
| `mwaskom__seaborn-2813` | `Histogram._define_bin_edges` | `source_reconstruction` | high | seaborn/_statistics.py::Histogram.define_bin_params |
| `mwaskom__seaborn-2979` | `Subplots._determine_axis_sharing` | `source_reconstruction` | high | seaborn/_core/subplots.py::Subplots.__init__ |
| `mwaskom__seaborn-3187` | `locator_to_legend_entries` | `source_reconstruction` | high | seaborn/relational.py::_RelationalPlotter.add_legend_data<br>seaborn/utils.py::dummy_axis |
| `pallets__flask-4642` | `show_server_banner` | `import_resolution` | high | src/flask/app.py::Flask.run<br>src/flask/cli.py::run_command |
| `psf__requests-1776` | `PreparedRequest.__init__` | `stage2_pool_scope` | high | requests/hooks.py::default_hooks |
| `pydata__xarray-4940` | `Dataset.reduce` | `source_reconstruction` | high | xarray/core/dataset.py::Dataset._replace_with_new_dims<br>xarray/core/dataset.py::Dataset.argmax<br>xarray/core/dataset. |
| `pydata__xarray-4940` | `Dataset.argmin` | `source_reconstruction` | high | xarray/core/dataset.py::Dataset.reduce |
| `pydata__xarray-4940` | `Dataset.argmax` | `source_reconstruction` | high | xarray/core/dataset.py::Dataset.reduce |
| `scikit-learn__scikit-learn-11042` | `_transform_selected` | `source_reconstruction` | high | sklearn/preprocessing/data.py::OneHotEncoder.fit_transform<br>sklearn/preprocessing/data.py::OneHotEncoder.transform |
| `sphinx-doc__sphinx-7748` | `FunctionDocumenter.format_signature` | `import_resolution` | high | sphinx/ext/autodoc/__init__.py::FunctionDocumenter<br>sphinx/ext/autodoc/__init__.py::FunctionDocumenter.annotate_to_fir |
| `sphinx-doc__sphinx-8056` | `GoogleDocstring._consume_fields` | `source_reconstruction` | high | sphinx/ext/napoleon/docstring.py::GoogleDocstring._consume_empty<br>sphinx/ext/napoleon/docstring.py::GoogleDocstring._c |
| `sphinx-doc__sphinx-8611` | `NonDataDescriptorMixin.should_suppress_value_header` | `import_resolution` | high | sphinx/util/inspect.py::isattributedescriptor |
| `sphinx-doc__sphinx-8611` | `NonDataDescriptorMixin.get_doc` | `import_resolution` | high | sphinx/util/inspect.py::isattributedescriptor |

分類以 candidate reconstruction、完整 index call graph 與 base-commit AST 交叉檢查。medium／low 表示有結構證據但不能證明執行時派送目標。
