# Stage 3 Symbol Gold audit evidence

## Sample 1: `pallets__flask-4642`

- Status: **exact**

- File: `src/flask/app.py` — True

- Expected: `Flask.run` / `method`

- Independent AST: `Flask.run` / `method`

- Evidence lines: `911 912 914 916`; source range: `846-966`


### Patch hunk

```diff

@@ -908,12 +910,18 @@ def run(
             The default port is now picked from the ``SERVER_NAME``
             variable.
         """
-        # Change this into a no-op if the server is invoked from the
-        # command line. Have a look at cli.py for more information.
+        # Ignore this call so that it doesn't start another server if
+        # the 'flask run' command is used.
         if os.environ.get("FLASK_RUN_FROM_CLI") == "true":
-            from .debughelpers import explain_ignored_app_run
+            if not is_running_from_reloader():
+                click.secho(
+                    " * Ignoring a call to 'app.run()', the server is"
+                    " already being run with the 'flask run' command.\n"
+                    "   Only call 'app.run()' in an 'if __name__ =="
+                    ' "__main__"\' guard.',
+                    fg="red",
+                )
 
-            explain_ignored_app_run()
             return
 
         if get_load_dotenv(load_dotenv):

```

### Base source

```python

909:             variable.
910:         """
911:         # Change this into a no-op if the server is invoked from the
912:         # command line. Have a look at cli.py for more information.
913:         if os.environ.get("FLASK_RUN_FROM_CLI") == "true":
914:             from .debughelpers import explain_ignored_app_run
915: 
916:             explain_ignored_app_run()
917:             return
918: 

```

## Sample 2: `pallets__flask-4642`

- Status: **exact**

- File: `src/flask/cli.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `965`; source range: `module`


### Patch hunk

```diff

@@ -963,6 +967,7 @@ def routes_command(sort: str, all_methods: bool) -> None:
 
 
 cli = FlaskGroup(
+    name="flask",
     help="""\
 A general utility script for Flask applications.
 

```

### Base source

```python

963: 
964: 
965: cli = FlaskGroup(
966:     help="""\
967: A general utility script for Flask applications.

```

## Sample 3: `pydata__xarray-4184`

- Status: **exact**

- File: `xarray/core/dataset.py` — True

- Expected: `Dataset._set_sparse_data_from_dataframe` / `method`

- Independent AST: `Dataset._set_sparse_data_from_dataframe` / `method`

- Evidence lines: `4560 4561 4562 4563 4564`; source range: `4545-4580`


### Patch hunk

```diff

@@ -4557,11 +4556,7 @@ def _set_sparse_data_from_dataframe(
             is_sorted = True
             shape = (idx.size,)
 
-        for name, series in dataframe.items():
-            # Cast to a NumPy array first, in case the Series is a pandas
-            # Extension array (which doesn't have a valid NumPy dtype)
-            values = np.asarray(series)
-
+        for name, values in arrays:
             # In virtually all real use cases, the sparse array will now have
             # missing values and needs a fill_value. For consistency, don't
             # special case the rare exceptions (e.g., dtype=int without a

```

### Base source

```python

4558:             shape = (idx.size,)
4559: 
4560:         for name, series in dataframe.items():
4561:             # Cast to a NumPy array first, in case the Series is a pandas
4562:             # Extension array (which doesn't have a valid NumPy dtype)
4563:             values = np.asarray(series)
4564: 
4565:             # In virtually all real use cases, the sparse array will now have
4566:             # missing values and needs a fill_value. For consistency, don't

```

## Sample 4: `pallets__flask-5063`

- Status: **exact**

- File: `src/flask/cli.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `12`; source range: `module`


### Patch hunk

```diff

@@ -9,7 +9,7 @@
 import traceback
 import typing as t
 from functools import update_wrapper
-from operator import attrgetter
+from operator import itemgetter
 
 import click
 from click.core import ParameterSource

```

### Base source

```python

10: import typing as t
11: from functools import update_wrapper
12: from operator import attrgetter
13: 
14: import click

```

## Sample 5: `sympy__sympy-13903`

- Status: **exact**

- File: `sympy/printing/fcode.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `53`; source range: `module`


### Patch hunk

```diff

@@ -50,7 +50,9 @@
     "exp": "exp",
     "erf": "erf",
     "Abs": "abs",
-    "conjugate": "conjg"
+    "conjugate": "conjg",
+    "Max": "max",
+    "Min": "min"
 }
 
 

```

### Base source

```python

51:     "erf": "erf",
52:     "Abs": "abs",
53:     "conjugate": "conjg"
54: }
55: 

```

## Sample 6: `scikit-learn__scikit-learn-13087`

- Status: **exact**

- File: `sklearn/calibration.py` — True

- Expected: `calibration_curve` / `function`

- Independent AST: `calibration_curve` / `function`

- Evidence lines: `575`; source range: `522-586`


### Patch hunk

```diff

@@ -572,7 +581,16 @@ def calibration_curve(y_true, y_prob, normalize=False, n_bins=5):
 
     y_true = _check_binary_probabilistic_predictions(y_true, y_prob)
 
-    bins = np.linspace(0., 1. + 1e-8, n_bins + 1)
+    if strategy == 'quantile':  # Determine bin edges by distribution of data
+        quantiles = np.linspace(0, 1, n_bins + 1)
+        bins = np.percentile(y_prob, quantiles * 100)
+        bins[-1] = bins[-1] + 1e-8
+    elif strategy == 'uniform':
+        bins = np.linspace(0., 1. + 1e-8, n_bins + 1)
+    else:
+        raise ValueError("Invalid entry to 'strategy' input. Strategy "
+                         "must be either 'quantile' or 'uniform'.")
+
     binids = np.digitize(y_prob, bins) - 1
 
     bin_sums = np.bincount(binids, weights=y_prob, minlength=len(bins))

```

### Base source

```python

573:     y_true = _check_binary_probabilistic_predictions(y_true, y_prob)
574: 
575:     bins = np.linspace(0., 1. + 1e-8, n_bins + 1)
576:     binids = np.digitize(y_prob, bins) - 1
577: 

```

## Sample 7: `mwaskom__seaborn-2389`

- Status: **exact**

- File: `seaborn/matrix.py` — True

- Expected: `_HeatMapper.__init__` / `method`

- Independent AST: `_HeatMapper.__init__` / `method`

- Evidence lines: `135 136 137`; source range: `99-192`


### Patch hunk

```diff

@@ -132,9 +125,6 @@ def __init__(self, data, vmin, vmax, cmap, center, robust, annot, fmt,
         elif yticklabels is False:
             yticklabels = []
 
-        # Get the positions and used label for the ticks
-        nx, ny = data.T.shape
-
         if not len(xticklabels):
             self.xticks = []
             self.xticklabels = []

```

### Base source

```python

133:             yticklabels = []
134: 
135:         # Get the positions and used label for the ticks
136:         nx, ny = data.T.shape
137: 
138:         if not len(xticklabels):
139:             self.xticks = []

```

## Sample 8: `pydata__xarray-4184`

- Status: **exact**

- File: `xarray/core/dataset.py` — True

- Expected: `Dataset._set_sparse_data_from_dataframe` / `method`

- Independent AST: `Dataset._set_sparse_data_from_dataframe` / `method`

- Evidence lines: `4546 4550`; source range: `4545-4580`


### Patch hunk

```diff

@@ -4543,11 +4543,10 @@ def to_dataframe(self):
         return self._to_dataframe(self.dims)
 
     def _set_sparse_data_from_dataframe(
-        self, dataframe: pd.DataFrame, dims: tuple
+        self, idx: pd.Index, arrays: List[Tuple[Hashable, np.ndarray]], dims: tuple
     ) -> None:
         from sparse import COO
 
-        idx = dataframe.index
         if isinstance(idx, pd.MultiIndex):
             coords = np.stack([np.asarray(code) for code in idx.codes], axis=0)
             is_sorted = idx.is_lexsorted()

```

### Base source

```python

4544: 
4545:     def _set_sparse_data_from_dataframe(
4546:         self, dataframe: pd.DataFrame, dims: tuple
4547:     ) -> None:
4548:         from sparse import COO
4549: 
4550:         idx = dataframe.index
4551:         if isinstance(idx, pd.MultiIndex):
4552:             coords = np.stack([np.asarray(code) for code in idx.codes], axis=0)

```

## Sample 9: `django__django-15139`

- Status: **exact**

- File: `django/contrib/sessions/serializers.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `1`; source range: `module`


### Patch hunk

```diff

@@ -1,3 +1,4 @@
+# RemovedInDjango50Warning.
 from django.core.serializers.base import (
     PickleSerializer as BasePickleSerializer,
 )

```

### Base source

```python

1: from django.core.serializers.base import (
2:     PickleSerializer as BasePickleSerializer,
3: )

```

## Sample 10: `psf__requests-1768`

- Status: **exact**

- File: `requests/utils.py` — True

- Expected: `get_auth_from_url` / `function`

- Independent AST: `get_auth_from_url` / `function`

- Evidence lines: `560`; source range: `557-564`


### Patch hunk

```diff

@@ -558,6 +558,7 @@ def get_auth_from_url(url):
     """Given a url with authentication components, extract them into a tuple of
     username,password."""
     if url:
+        url = unquote(url)
         parsed = urlparse(url)
         return (parsed.username, parsed.password)
     else:

```

### Base source

```python

558:     """Given a url with authentication components, extract them into a tuple of
559:     username,password."""
560:     if url:
561:         parsed = urlparse(url)
562:         return (parsed.username, parsed.password)

```

## Sample 11: `pallets__flask-4169`

- Status: **exact**

- File: `src/flask/cli.py` — True

- Expected: `DispatchingApp.__init__` / `method`

- Independent AST: `DispatchingApp.__init__` / `method`

- Evidence lines: `315`; source range: `311-323`


### Patch hunk

```diff

@@ -312,7 +312,7 @@ def __init__(self, loader, use_eager_loading=None):
         self.loader = loader
         self._app = None
         self._lock = Lock()
-        self._bg_loading_exc_info = None
+        self._bg_loading_exc = None
 
         if use_eager_loading is None:
             use_eager_loading = os.environ.get("WERKZEUG_RUN_MAIN") != "true"

```

### Base source

```python

313:         self._app = None
314:         self._lock = Lock()
315:         self._bg_loading_exc_info = None
316: 
317:         if use_eager_loading is None:

```

## Sample 12: `matplotlib__matplotlib-26341`

- Status: **exact**

- File: `lib/matplotlib/axes/_base.py` — True

- Expected: `_process_plot_var_args.__getstate__` / `method`

- Independent AST: `_process_plot_var_args.__getstate__` / `method`

- Evidence lines: `227 228 229`; source range: `227-229`


### Patch hunk

```diff

@@ -224,18 +223,11 @@ def __init__(self, command='plot'):
         self.command = command
         self.set_prop_cycle(None)
 
-    def __getstate__(self):
-        # note: it is not possible to pickle a generator (and thus a cycler).
-        return {'command': self.command}
-
-    def __setstate__(self, state):
-        self.__dict__ = state.copy()
-        self.set_prop_cycle(None)
-
     def set_prop_cycle(self, cycler):
         if cycler is None:
             cycler = mpl.rcParams['axes.prop_cycle']
-        self.prop_cycler = itertools.cycle(cycler)
+        self._idx = 0
+        self._cycler_items = [*cycler]
         self._prop_keys = cycler.keys  # This should make a copy
 
     def __call__(self, axes, *args, data=None, **kwargs):

```

### Base source

```python

225:         self.set_prop_cycle(None)
226: 
227:     def __getstate__(self):
228:         # note: it is not possible to pickle a generator (and thus a cycler).
229:         return {'command': self.command}
230: 
231:     def __setstate__(self, state):

```

## Sample 13: `django__django-16517`

- Status: **exact**

- File: `django/contrib/admindocs/utils.py` — True

- Expected: `create_reference_role` / `function`

- Independent AST: `create_reference_role` / `function`

- Evidence lines: `103`; source range: `103-121`


### Patch hunk

```diff

@@ -101,6 +101,9 @@ def parse_rst(text, default_reference_context, thing_being_parsed=None):
 
 
 def create_reference_role(rolename, urlbase):
+    # Views and template names are case-sensitive.
+    is_case_sensitive = rolename in ["template", "view"]
+
     def _role(name, rawtext, text, lineno, inliner, options=None, content=None):
         if options is None:
             options = {}

```

### Base source

```python

101: 
102: 
103: def create_reference_role(rolename, urlbase):
104:     def _role(name, rawtext, text, lineno, inliner, options=None, content=None):
105:         if options is None:

```

## Sample 14: `django__django-14399`

- Status: **exact**

- File: `django/conf/__init__.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `11`; source range: `module`


### Patch hunk

```diff

@@ -9,10 +9,12 @@
 import importlib
 import os
 import time
+import warnings
 from pathlib import Path
 
 from django.conf import global_settings
 from django.core.exceptions import ImproperlyConfigured
+from django.utils.deprecation import RemovedInDjango50Warning
 from django.utils.functional import LazyObject, empty
 
 ENVIRONMENT_VARIABLE = "DJANGO_SETTINGS_MODULE"

```

### Base source

```python

9: import importlib
10: import os
11: import time
12: from pathlib import Path
13: 

```

## Sample 15: `pydata__xarray-4940`

- Status: **exact**

- File: `xarray/core/dataset.py` — True

- Expected: `Dataset.argmax` / `method`

- Independent AST: `Dataset.argmax` / `method`

- Evidence lines: `6956 6958 6959 6960 6961 6962 6968 6975`; source range: `6920-6981`


### Patch hunk

```diff

@@ -6953,26 +6950,24 @@ def argmax(self, dim=None, axis=None, **kwargs):
         DataArray.argmax
 
         """
-        if dim is None and axis is None:
+        if dim is None:
             warnings.warn(
-                "Once the behaviour of DataArray.argmax() and Variable.argmax() with "
-                "neither dim nor axis argument changes to return a dict of indices of "
-                "each dimension, for consistency it will be an error to call "
-                "Dataset.argmax() with no argument, since we don't return a dict of "
-                "Datasets.",
+                "Once the behaviour of DataArray.argmin() and Variable.argmin() without "
+                "dim changes to return a dict of indices of each dimension, for "
+                "consistency it will be an error to call Dataset.argmin() with no argument,"
+                "since we don't return a dict of Datasets.",
                 DeprecationWarning,
                 stacklevel=2,
             )
         if (
             dim is None
-            or axis is not None
             or (not isinstance(dim, Sequence) and dim is not ...)
             or isinstance(dim, str)
         ):
             # Return int index if single dimension is passed, and is not part of a
             # sequence
             argmax_func = getattr(duck_array_ops, "argmax")
-            return self.reduce(argmax_func, dim=dim, axis=axis, **kwargs)
+            return self.reduce(argmax_func, dim=dim, **kwargs)
         else:
             raise ValueError(
                 "When dim is a sequence or ..., DataArray.argmin() returns a dict. "

```

### Base source

```python

6954: 
6955:         """
6956:         if dim is None and axis is None:
6957:             warnings.warn(
6958:                 "Once the behaviour of DataArray.argmax() and Variable.argmax() with "
6959:                 "neither dim nor axis argument changes to return a dict of indices of "
6960:                 "each dimension, for consistency it will be an error to call "
6961:                 "Dataset.argmax() with no argument, since we don't return a dict of "
6962:                 "Datasets.",
6963:                 DeprecationWarning,
6964:                 stacklevel=2,
6965:             )
6966:         if (
6967:             dim is None
6968:             or axis is not None
6969:             or (not isinstance(dim, Sequence) and dim is not ...)
6970:             or isinstance(dim, str)
6971:         ):
6972:             # Return int index if single dimension is passed, and is not part of a
6973:             # sequence
6974:             argmax_func = getattr(duck_array_ops, "argmax")
6975:             return self.reduce(argmax_func, dim=dim, axis=axis, **kwargs)
6976:         else:
6977:             raise ValueError(

```

## Sample 16: `django__django-14785`

- Status: **exact**

- File: `django/db/models/fields/__init__.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `4`; source range: `module`


### Patch hunk

```diff

@@ -2,6 +2,7 @@
 import copy
 import datetime
 import decimal
+import math
 import operator
 import uuid
 import warnings

```

### Base source

```python

2: import copy
3: import datetime
4: import decimal
5: import operator
6: import uuid

```

## Sample 17: `psf__requests-1776`

- Status: **exact**

- File: `requests/auth.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `18`; source range: `module`


### Patch hunk

```diff

@@ -16,6 +16,7 @@
 from base64 import b64encode
 
 from .compat import urlparse, str
+from .cookies import extract_cookies_to_jar
 from .utils import parse_dict_header
 
 log = logging.getLogger(__name__)

```

### Base source

```python

16: from base64 import b64encode
17: 
18: from .compat import urlparse, str
19: from .utils import parse_dict_header
20: 

```

## Sample 18: `pylint-dev__pylint-6357`

- Status: **exact**

- File: `pylint/checkers/similar.py` — True

- Expected: `stripped_lines` / `function`

- Independent AST: `stripped_lines` / `function`

- Evidence lines: `624`; source range: `560-652`


### Patch hunk

```diff

@@ -622,6 +621,10 @@ def _get_functions(
     strippedlines = []
     docstring = None
     for lineno, line in enumerate(lines, start=1):
+        if line_enabled_callback is not None and not line_enabled_callback(
+            "R0801", lineno
+        ):
+            continue
         line = line.strip()
         if ignore_docstrings:
             if not docstring:

```

### Base source

```python

622:     strippedlines = []
623:     docstring = None
624:     for lineno, line in enumerate(lines, start=1):
625:         line = line.strip()
626:         if ignore_docstrings:

```

## Sample 19: `astropy__astropy-13073`

- Status: **exact**

- File: `astropy/io/ascii/core.py` — True

- Expected: `BaseOutputter` / `class`

- Independent AST: `BaseOutputter` / `class`

- Evidence lines: `1018`; source range: `1015-1084`


### Patch hunk

```diff

@@ -1016,7 +1016,10 @@ class BaseOutputter:
     """Output table as a dict of column objects keyed on column name.  The
     table data are stored as plain python lists within the column objects.
     """
+    # User-defined converters which gets set in ascii.ui if a `converter` kwarg
+    # is supplied.
     converters = {}
+
     # Derived classes must define default_converters and __call__
 
     @staticmethod

```

### Base source

```python

1016:     """Output table as a dict of column objects keyed on column name.  The
1017:     table data are stored as plain python lists within the column objects.
1018:     """
1019:     converters = {}
1020:     # Derived classes must define default_converters and __call__

```

## Sample 20: `django__django-14785`

- Status: **exact**

- File: `django/db/models/fields/__init__.py` — True

- Expected: `DecimalField.to_python` / `method`

- Independent AST: `DecimalField.to_python` / `method`

- Evidence lines: `1541`; source range: `1538-1550`


### Patch hunk

```diff

@@ -1539,6 +1540,12 @@ def to_python(self, value):
         if value is None:
             return value
         if isinstance(value, float):
+            if math.isnan(value):
+                raise exceptions.ValidationError(
+                    self.error_messages['invalid'],
+                    code='invalid',
+                    params={'value': value},
+                )
             return self.context.create_decimal_from_float(value)
         try:
             return decimal.Decimal(value)

```

### Base source

```python

1539:         if value is None:
1540:             return value
1541:         if isinstance(value, float):
1542:             return self.context.create_decimal_from_float(value)
1543:         try:

```

## Sample 21: `django__django-15139`

- Status: **exact**

- File: `django/core/cache/backends/redis.py` — True

- Expected: `RedisSerializer` / `class`

- Independent AST: `RedisSerializer` / `class`

- Evidence lines: `12 13 14 15 16`; source range: `12-28`


### Patch hunk

```diff

@@ -1,31 +1,30 @@
 """Redis cache backend."""
 
+import pickle
 import random
 import re
 
 from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
-from django.core.serializers.base import PickleSerializer
 from django.utils.functional import cached_property
 from django.utils.module_loading import import_string
 
 
-class RedisSerializer(PickleSerializer):
-    """
-    Similar to PickSerializer, except integers are serialized as native Redis
-    integers for better incr() and decr() atomicity.
-    """
+class RedisSerializer:
+    def __init__(self, protocol=None):
+        self.protocol = pickle.HIGHEST_PROTOCOL if protocol is None else protocol
+
     def dumps(self, obj):
         # Only skip pickling for integers, a int subclasses as bool should be
         # pickled.
         if type(obj) is int:
             return obj
-        return super().dumps(obj)
+        return pickle.dumps(obj, self.protocol)
 
     def loads(self, data):
         try:
             return int(data)
         except ValueError:
-            return super().loads(data)
+            return pickle.loads(data)
 
 
 class RedisCacheClient:

```

### Base source

```python

10: 
11: 
12: class RedisSerializer(PickleSerializer):
13:     """
14:     Similar to PickSerializer, except integers are serialized as native Redis
15:     integers for better incr() and decr() atomicity.
16:     """
17:     def dumps(self, obj):
18:         # Only skip pickling for integers, a int subclasses as bool should be

```

## Sample 22: `pydata__xarray-4940`

- Status: **exact**

- File: `xarray/core/dataset.py` — True

- Expected: `Dataset.argmin` / `method`

- Independent AST: `Dataset.argmin` / `method`

- Evidence lines: `6857`; source range: `6857-6918`


### Patch hunk

```diff

@@ -6854,7 +6860,7 @@ def idxmax(
             )
         )
 
-    def argmin(self, dim=None, axis=None, **kwargs):
+    def argmin(self, dim=None, **kwargs):
         """Indices of the minima of the member variables.
 
         If there are multiple minima, the indices of the first one found will be

```

### Base source

```python

6855:         )
6856: 
6857:     def argmin(self, dim=None, axis=None, **kwargs):
6858:         """Indices of the minima of the member variables.
6859: 

```

## Sample 23: `pydata__xarray-5580`

- Status: **exact**

- File: `xarray/core/formatting.py` — True

- Expected: `_mapping_repr` / `function`

- Independent AST: `_mapping_repr` / `function`

- Evidence lines: `380 381 387`; source range: `375-402`


### Patch hunk

```diff

@@ -377,14 +377,12 @@ def _mapping_repr(
 ):
     if col_width is None:
         col_width = _calculate_col_width(mapping)
-    if max_rows is None:
-        max_rows = OPTIONS["display_max_rows"]
     summary = [f"{title}:"]
     if mapping:
         len_mapping = len(mapping)
         if not _get_boolean_with_default(expand_option_name, default=True):
             summary = [f"{summary[0]} ({len_mapping})"]
-        elif len_mapping > max_rows:
+        elif max_rows is not None and len_mapping > max_rows:
             summary = [f"{summary[0]} ({max_rows}/{len_mapping})"]
             first_rows = max_rows // 2 + max_rows % 2
             keys = list(mapping.keys())

```

### Base source

```python

378:     if col_width is None:
379:         col_width = _calculate_col_width(mapping)
380:     if max_rows is None:
381:         max_rows = OPTIONS["display_max_rows"]
382:     summary = [f"{title}:"]
383:     if mapping:
384:         len_mapping = len(mapping)
385:         if not _get_boolean_with_default(expand_option_name, default=True):
386:             summary = [f"{summary[0]} ({len_mapping})"]
387:         elif len_mapping > max_rows:
388:             summary = [f"{summary[0]} ({max_rows}/{len_mapping})"]
389:             first_rows = max_rows // 2 + max_rows % 2

```

## Sample 24: `matplotlib__matplotlib-25404`

- Status: **exact**

- File: `lib/matplotlib/widgets.py` — True

- Expected: `_SelectorWidget.set_props` / `method`

- Independent AST: `_SelectorWidget.set_props` / `method`

- Evidence lines: `2460 2461 2468`; source range: `2458-2468`


### Patch hunk

```diff

@@ -2457,15 +2457,16 @@ def artists(self):
 
     def set_props(self, **props):
         """
-        Set the properties of the selector artist. See the `props` argument
-        in the selector docstring to know which properties are supported.
+        Set the properties of the selector artist.
+
+        See the *props* argument in the selector docstring to know which properties are
+        supported.
         """
         artist = self._selection_artist
         props = cbook.normalize_kwargs(props, artist)
         artist.set(**props)
         if self.useblit:
             self.update()
-        self._props.update(props)
 
     def set_handle_props(self, **handle_props):
         """

```

### Base source

```python

2458:     def set_props(self, **props):
2459:         """
2460:         Set the properties of the selector artist. See the `props` argument
2461:         in the selector docstring to know which properties are supported.
2462:         """
2463:         artist = self._selection_artist
2464:         props = cbook.normalize_kwargs(props, artist)
2465:         artist.set(**props)
2466:         if self.useblit:
2467:             self.update()
2468:         self._props.update(props)
2469: 
2470:     def set_handle_props(self, **handle_props):

```

## Sample 25: `pytest-dev__pytest-10893`

- Status: **exact**

- File: `src/_pytest/unittest.py` — True

- Expected: `TestCaseFunction` / `class`

- Independent AST: `TestCaseFunction` / `class`

- Evidence lines: `300`; source range: `183-342`


### Patch hunk

```diff

@@ -298,6 +298,9 @@ def addSuccess(self, testcase: "unittest.TestCase") -> None:
     def stopTest(self, testcase: "unittest.TestCase") -> None:
         pass
 
+    def addDuration(self, testcase: "unittest.TestCase", elapsed: float) -> None:
+        pass
+
     def runtest(self) -> None:
         from _pytest.debugging import maybe_wrap_pytest_function_for_tracing
 

```

### Base source

```python

298:     def stopTest(self, testcase: "unittest.TestCase") -> None:
299:         pass
300: 
301:     def runtest(self) -> None:
302:         from _pytest.debugging import maybe_wrap_pytest_function_for_tracing

```

## Sample 26: `pallets__flask-4642`

- Status: **exact**

- File: `src/flask/cli.py` — True

- Expected: `FlaskGroup.__init__` / `method`

- Independent AST: `FlaskGroup.__init__` / `method`

- Evidence lines: `480`; source range: `466-490`


### Patch hunk

```diff

@@ -477,7 +479,13 @@ def __init__(
         if add_version_option:
             params.append(version_option)
 
-        AppGroup.__init__(self, params=params, **extra)
+        if "context_settings" not in extra:
+            extra["context_settings"] = {}
+
+        extra["context_settings"].setdefault("auto_envvar_prefix", "FLASK")
+
+        super().__init__(params=params, **extra)
+
         self.create_app = create_app
         self.load_dotenv = load_dotenv
         self.set_debug_flag = set_debug_flag

```

### Base source

```python

478:             params.append(version_option)
479: 
480:         AppGroup.__init__(self, params=params, **extra)
481:         self.create_app = create_app
482:         self.load_dotenv = load_dotenv

```

## Sample 27: `pydata__xarray-4940`

- Status: **exact**

- File: `xarray/core/dataset.py` — True

- Expected: `Dataset.argmax` / `method`

- Independent AST: `Dataset.argmax` / `method`

- Evidence lines: `6920`; source range: `6920-6981`


### Patch hunk

```diff

@@ -6917,7 +6917,7 @@ def argmin(self, dim=None, axis=None, **kwargs):
                 "Dataset.argmin() with a sequence or ... for dim"
             )
 
-    def argmax(self, dim=None, axis=None, **kwargs):
+    def argmax(self, dim=None, **kwargs):
         """Indices of the maxima of the member variables.
 
         If there are multiple maxima, the indices of the first one found will be

```

### Base source

```python

6918:             )
6919: 
6920:     def argmax(self, dim=None, axis=None, **kwargs):
6921:         """Indices of the maxima of the member variables.
6922: 

```

## Sample 28: `pydata__xarray-4684`

- Status: **exact**

- File: `xarray/coding/times.py` — True

- Expected: `_decode_datetime_with_pandas` / `function`

- Independent AST: `_decode_datetime_with_pandas` / `function`

- Evidence lines: `154 155 156 157 158 159 160 161 162 163 164 165 166 167`; source range: `138-169`


### Patch hunk

```diff

@@ -151,21 +161,22 @@ def _decode_datetime_with_pandas(flat_num_dates, units, calendar):
         # strings, in which case we fall back to using cftime
         raise OutOfBoundsDatetime
 
-    # fixes: https://github.com/pydata/pandas/issues/14068
-    # these lines check if the the lowest or the highest value in dates
-    # cause an OutOfBoundsDatetime (Overflow) error
-    with warnings.catch_warnings():
-        warnings.filterwarnings("ignore", "invalid value encountered", RuntimeWarning)
-        pd.to_timedelta(flat_num_dates.min(), delta) + ref_date
-        pd.to_timedelta(flat_num_dates.max(), delta) + ref_date
-
-    # Cast input dates to integers of nanoseconds because `pd.to_datetime`
-    # works much faster when dealing with integers
-    # make _NS_PER_TIME_DELTA an array to ensure type upcasting
-    flat_num_dates_ns_int = (
-        flat_num_dates.astype(np.float64) * _NS_PER_TIME_DELTA[delta]
-    ).astype(np.int64)
+    # To avoid integer overflow when converting to nanosecond units for integer
+    # dtypes smaller than np.int64 cast all integer-dtype arrays to np.int64
+    # (GH 2002).
+    if flat_num_dates.dtype.kind == "i":
+        flat_num_dates = flat_num_dates.astype(np.int64)
 
+    # Cast input ordinals to integers of nanoseconds because pd.to_timedelta
+    # works much faster when dealing with integers (GH 1399).
+    flat_num_dates_ns_int = (flat_num_dates * _NS_PER_TIME_DELTA[delta]).astype(
+        np.int64
+    )
+
+    # Use pd.to_timedelta to safely cast integer values to timedeltas,
+    # and add those to a Timestamp to safely produce a DatetimeIndex.  This
+    # ensures that we do not encounter integer overflow at any point in the
+    # process without raising OutOfBoundsDatetime.
     return (pd.to_timedelta(flat_num_dates_ns_int, "ns") + ref_date).values
 
 

```

### Base source

```python

152:         raise OutOfBoundsDatetime
153: 
154:     # fixes: https://github.com/pydata/pandas/issues/14068
155:     # these lines check if the the lowest or the highest value in dates
156:     # cause an OutOfBoundsDatetime (Overflow) error
157:     with warnings.catch_warnings():
158:         warnings.filterwarnings("ignore", "invalid value encountered", RuntimeWarning)
159:         pd.to_timedelta(flat_num_dates.min(), delta) + ref_date
160:         pd.to_timedelta(flat_num_dates.max(), delta) + ref_date
161: 
162:     # Cast input dates to integers of nanoseconds because `pd.to_datetime`
163:     # works much faster when dealing with integers
164:     # make _NS_PER_TIME_DELTA an array to ensure type upcasting
165:     flat_num_dates_ns_int = (
166:         flat_num_dates.astype(np.float64) * _NS_PER_TIME_DELTA[delta]
167:     ).astype(np.int64)
168: 
169:     return (pd.to_timedelta(flat_num_dates_ns_int, "ns") + ref_date).values

```

## Sample 29: `pylint-dev__pylint-6357`

- Status: **exact**

- File: `pylint/checkers/similar.py` — True

- Expected: `stripped_lines` / `function`

- Independent AST: `stripped_lines` / `function`

- Evidence lines: `565`; source range: `560-652`


### Patch hunk

```diff

@@ -563,6 +560,7 @@ def stripped_lines(
     ignore_docstrings: bool,
     ignore_imports: bool,
     ignore_signatures: bool,
+    line_enabled_callback: Callable[[str, int], bool] | None = None,
 ) -> list[LineSpecifs]:
     """Return tuples of line/line number/line type with leading/trailing whitespace and any ignored code features removed.
 

```

### Base source

```python

563:     ignore_docstrings: bool,
564:     ignore_imports: bool,
565:     ignore_signatures: bool,
566: ) -> list[LineSpecifs]:
567:     """Return tuples of line/line number/line type with leading/trailing whitespace and any ignored code features removed.

```

## Sample 30: `pydata__xarray-4684`

- Status: **exact**

- File: `xarray/coding/times.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `28`; source range: `module`


### Patch hunk

```diff

@@ -26,6 +26,7 @@
 _STANDARD_CALENDARS = {"standard", "gregorian", "proleptic_gregorian"}
 
 _NS_PER_TIME_DELTA = {
+    "ns": 1,
     "us": int(1e3),
     "ms": int(1e6),
     "s": int(1e9),

```

### Base source

```python

26: _STANDARD_CALENDARS = {"standard", "gregorian", "proleptic_gregorian"}
27: 
28: _NS_PER_TIME_DELTA = {
29:     "us": int(1e3),
30:     "ms": int(1e6),

```

## Sample 31: `psf__requests-2393`

- Status: **exact**

- File: `requests/utils.py` — True

- Expected: `requote_uri` / `function`

- Independent AST: `requote_uri` / `function`

- Evidence lines: `421 422 423 424`; source range: `415-424`


### Patch hunk

```diff

@@ -418,10 +418,18 @@ def requote_uri(uri):
     This function passes the given URI through an unquote/quote cycle to
     ensure that it is fully and consistently quoted.
     """
-    # Unquote only the unreserved characters
-    # Then quote only illegal characters (do not quote reserved, unreserved,
-    # or '%')
-    return quote(unquote_unreserved(uri), safe="!#$%&'()*+,/:;=?@[]~")
+    safe_with_percent = "!#$%&'()*+,/:;=?@[]~"
+    safe_without_percent = "!#$&'()*+,/:;=?@[]~"
+    try:
+        # Unquote only the unreserved characters
+        # Then quote only illegal characters (do not quote reserved,
+        # unreserved, or '%')
+        return quote(unquote_unreserved(uri), safe=safe_with_percent)
+    except InvalidURL:
+        # We couldn't unquote the given URI, so let's try quoting it, but
+        # there may be unquoted '%'s in the URI. We need to make sure they're
+        # properly quoted so they do not cause issues elsewhere.
+        return quote(uri, safe=safe_without_percent)
 
 
 def address_in_network(ip, net):

```

### Base source

```python

419:     ensure that it is fully and consistently quoted.
420:     """
421:     # Unquote only the unreserved characters
422:     # Then quote only illegal characters (do not quote reserved, unreserved,
423:     # or '%')
424:     return quote(unquote_unreserved(uri), safe="!#$%&'()*+,/:;=?@[]~")
425: 
426: 

```

## Sample 32: `pylint-dev__pylint-6820`

- Status: **exact**

- File: `pylint/config/utils.py` — True

- Expected: `_preprocess_options` / `function`

- Independent AST: `_preprocess_options` / `function`

- Evidence lines: `233 238`; source range: `216-251`


### Patch hunk

```diff

@@ -230,12 +244,21 @@ def _preprocess_options(run: Run, args: Sequence[str]) -> list[str]:
         except ValueError:
             option, value = argument, None
 
-        if option not in PREPROCESSABLE_OPTIONS:
+        matched_option = None
+        for option_name, data in PREPROCESSABLE_OPTIONS.items():
+            to_match = data[2]
+            if to_match == 0:
+                if option == option_name:
+                    matched_option = option_name
+            elif option.startswith(option_name[:to_match]):
+                matched_option = option_name
+
+        if matched_option is None:
             processed_args.append(argument)
             i += 1
             continue
 
-        takearg, cb = PREPROCESSABLE_OPTIONS[option]
+        takearg, cb, _ = PREPROCESSABLE_OPTIONS[matched_option]
 
         if takearg and value is None:
             i += 1

```

### Base source

```python

231:             option, value = argument, None
232: 
233:         if option not in PREPROCESSABLE_OPTIONS:
234:             processed_args.append(argument)
235:             i += 1
236:             continue
237: 
238:         takearg, cb = PREPROCESSABLE_OPTIONS[option]
239: 
240:         if takearg and value is None:

```

## Sample 33: `sphinx-doc__sphinx-9798`

- Status: **exact**

- File: `sphinx/domains/python.py` — True

- Expected: `PyXrefMixin.make_xrefs` / `method`

- Independent AST: `PyXrefMixin.make_xrefs` / `method`

- Evidence lines: `361`; source range: `346-367`


### Patch hunk

```diff

@@ -353,17 +353,21 @@ def make_xrefs(self, rolename: str, domain: str, target: str,
 
         split_contnode = bool(contnode and contnode.astext() == target)
 
+        in_literal = False
         results = []
         for sub_target in filter(None, sub_targets):
             if split_contnode:
                 contnode = nodes.Text(sub_target)
 
-            if delims_re.match(sub_target):
+            if in_literal or delims_re.match(sub_target):
                 results.append(contnode or innernode(sub_target, sub_target))
             else:
                 results.append(self.make_xref(rolename, domain, sub_target,
                                               innernode, contnode, env, inliner, location))
 
+            if sub_target in ('Literal', 'typing.Literal'):
+                in_literal = True
+
         return results
 
 

```

### Base source

```python

359:                 contnode = nodes.Text(sub_target)
360: 
361:             if delims_re.match(sub_target):
362:                 results.append(contnode or innernode(sub_target, sub_target))
363:             else:

```

## Sample 34: `mwaskom__seaborn-2813`

- Status: **exact**

- File: `seaborn/axisgrid.py` — True

- Expected: `pairplot` / `function`

- Independent AST: `pairplot` / `function`

- Evidence lines: `2101`; source range: `1975-2146`


### Patch hunk

```diff

@@ -2098,7 +2098,7 @@ def pairplot(
                 markers = [markers] * n_markers
             if len(markers) != n_markers:
                 raise ValueError("markers must be a singleton or a list of "
-                                  "markers for each level of the hue variable")
+                                 "markers for each level of the hue variable")
             grid.hue_kws = {"marker": markers}
         elif kind == "scatter":
             if isinstance(markers, str):

```

### Base source

```python

2099:             if len(markers) != n_markers:
2100:                 raise ValueError("markers must be a singleton or a list of "
2101:                                   "markers for each level of the hue variable")
2102:             grid.hue_kws = {"marker": markers}
2103:         elif kind == "scatter":

```

## Sample 35: `pallets__flask-4642`

- Status: **exact**

- File: `src/flask/cli.py` — True

- Expected: `show_server_banner` / `function`

- Independent AST: `show_server_banner` / `function`

- Evidence lines: `640`; source range: `636-662`


### Patch hunk

```diff

@@ -637,7 +641,7 @@ def show_server_banner(env, debug, app_import_path, eager_loading):
     """Show extra startup messages the first time the server is run,
     ignoring the reloader.
     """
-    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
+    if is_running_from_reloader():
         return
 
     if app_import_path is not None:

```

### Base source

```python

638:     ignoring the reloader.
639:     """
640:     if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
641:         return
642: 

```

## Sample 36: `matplotlib__matplotlib-25404`

- Status: **exact**

- File: `lib/matplotlib/widgets.py` — True

- Expected: `SpanSelector.__init__` / `method`

- Independent AST: `SpanSelector.__init__` / `method`

- Evidence lines: `2673`; source range: `2633-2687`


### Patch hunk

```diff

@@ -2670,7 +2670,7 @@ def __init__(self, ax, onselect, direction, minspan=0, useblit=False,
 
         # Reset canvas so that `new_axes` connects events.
         self.canvas = None
-        self.new_axes(ax)
+        self.new_axes(ax, _props=props)
 
         # Setup handles
         self._handle_props = {

```

### Base source

```python

2671:         # Reset canvas so that `new_axes` connects events.
2672:         self.canvas = None
2673:         self.new_axes(ax)
2674: 
2675:         # Setup handles

```

## Sample 37: `pydata__xarray-3649`

- Status: **exact**

- File: `xarray/core/combine.py` — True

- Expected: `combine_by_coords` / `function`

- Independent AST: `combine_by_coords` / `function`

- Evidence lines: `539`; source range: `472-698`


### Patch hunk

```diff

@@ -536,7 +542,8 @@ def combine_by_coords(
     coords : {'minimal', 'different', 'all' or list of str}, optional
         As per the 'data_vars' kwarg, but for coordinate variables.
     fill_value : scalar, optional
-        Value to use for newly missing values
+        Value to use for newly missing values. If None, raises a ValueError if
+        the passed Datasets do not create a complete hypercube.
     join : {'outer', 'inner', 'left', 'right', 'exact'}, optional
         String indicating how to combine differing indexes
         (excluding concat_dim) in objects

```

### Base source

```python

537:         As per the 'data_vars' kwarg, but for coordinate variables.
538:     fill_value : scalar, optional
539:         Value to use for newly missing values
540:     join : {'outer', 'inner', 'left', 'right', 'exact'}, optional
541:         String indicating how to combine differing indexes

```

## Sample 38: `pylint-dev__pylint-7097`

- Status: **exact**

- File: `pylint/checkers/imports.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `30`; source range: `module`


### Patch hunk

```diff

@@ -28,6 +28,7 @@
 )
 from pylint.exceptions import EmptyReportError
 from pylint.graph import DotBackend, get_cycles
+from pylint.interfaces import HIGH
 from pylint.reporters.ureports.nodes import Paragraph, Section, VerbatimText
 from pylint.typing import MessageDefinitionTuple
 from pylint.utils import IsortDriver

```

### Base source

```python

28: )
29: from pylint.exceptions import EmptyReportError
30: from pylint.graph import DotBackend, get_cycles
31: from pylint.reporters.ureports.nodes import Paragraph, Section, VerbatimText
32: from pylint.typing import MessageDefinitionTuple

```

## Sample 39: `pydata__xarray-3649`

- Status: **exact**

- File: `xarray/core/combine.py` — True

- Expected: `_check_shape_tile_ids` / `function`

- Independent AST: `_check_shape_tile_ids` / `function`

- Evidence lines: `118 120 121 122`; source range: `118-141`


### Patch hunk

```diff

@@ -115,11 +115,12 @@ def _infer_concat_order_from_coords(datasets):
     return combined_ids, concat_dims
 
 
-def _check_shape_tile_ids(combined_tile_ids):
+def _check_dimension_depth_tile_ids(combined_tile_ids):
+    """
+    Check all tuples are the same length, i.e. check that all lists are
+    nested to the same depth.
+    """
     tile_ids = combined_tile_ids.keys()
-
-    # Check all tuples are the same length
-    # i.e. check that all lists are nested to the same depth
     nesting_depths = [len(tile_id) for tile_id in tile_ids]
     if not nesting_depths:
         nesting_depths = [0]

```

### Base source

```python

116: 
117: 
118: def _check_shape_tile_ids(combined_tile_ids):
119:     tile_ids = combined_tile_ids.keys()
120: 
121:     # Check all tuples are the same length
122:     # i.e. check that all lists are nested to the same depth
123:     nesting_depths = [len(tile_id) for tile_id in tile_ids]
124:     if not nesting_depths:

```

## Sample 40: `astropy__astropy-14598`

- Status: **exact**

- File: `astropy/io/fits/card.py` — True

- Expected: `Card` / `class`

- Independent AST: `Card` / `class`

- Evidence lines: `69`; source range: `41-1243`


### Patch hunk

```diff

@@ -66,7 +66,7 @@ class Card(_Verify):
     # followed by an optional comment
     _strg = r"\'(?P<strg>([ -~]+?|\'\'|) *?)\'(?=$|/| )"
     _comm_field = r"(?P<comm_field>(?P<sepr>/ *)(?P<comm>(.|\n)*))"
-    _strg_comment_RE = re.compile(f"({_strg})? *{_comm_field}?")
+    _strg_comment_RE = re.compile(f"({_strg})? *{_comm_field}?$")
 
     # FSC commentary card string which must contain printable ASCII characters.
     # Note: \Z matches the end of the string without allowing newlines

```

### Base source

```python

67:     _strg = r"\'(?P<strg>([ -~]+?|\'\'|) *?)\'(?=$|/| )"
68:     _comm_field = r"(?P<comm_field>(?P<sepr>/ *)(?P<comm>(.|\n)*))"
69:     _strg_comment_RE = re.compile(f"({_strg})? *{_comm_field}?")
70: 
71:     # FSC commentary card string which must contain printable ASCII characters.

```

## Sample 41: `django__django-16517`

- Status: **exact**

- File: `django/contrib/admindocs/utils.py` — True

- Expected: `create_reference_role.<locals>._role` / `function`

- Independent AST: `create_reference_role.<locals>._role` / `function`

- Evidence lines: `114`; source range: `104-119`


### Patch hunk

```diff

@@ -111,7 +114,7 @@ def _role(name, rawtext, text, lineno, inliner, options=None, content=None):
                 urlbase
                 % (
                     inliner.document.settings.link_base,
-                    text.lower(),
+                    text if is_case_sensitive else text.lower(),
                 )
             ),
             **options,

```

### Base source

```python

112:                 % (
113:                     inliner.document.settings.link_base,
114:                     text.lower(),
115:                 )
116:             ),

```

## Sample 42: `pylint-dev__pylint-6357`

- Status: **exact**

- File: `pylint/checkers/similar.py` — True

- Expected: `Similar.append_stream` / `method`

- Independent AST: `Similar.append_stream` / `method`

- Evidence lines: `370 371 372 373 374 375 376 377 378 379 380 381 382 383 384 385 386 387 388 390`; source range: `359-390`


### Patch hunk

```diff

@@ -366,28 +366,25 @@ def append_stream(
             readlines = decoding_stream(stream, encoding).readlines
         else:
             readlines = stream.readlines  # type: ignore[assignment] # hint parameter is incorrectly typed as non-optional
+
         try:
-            active_lines: list[str] = []
-            if hasattr(self, "linter"):
-                # Remove those lines that should be ignored because of disables
-                for index, line in enumerate(readlines()):
-                    if self.linter._is_one_message_enabled("R0801", index + 1):  # type: ignore[attr-defined]
-                        active_lines.append(line)
-            else:
-                active_lines = readlines()
-
-            self.linesets.append(
-                LineSet(
-                    streamid,
-                    active_lines,
-                    self.namespace.ignore_comments,
-                    self.namespace.ignore_docstrings,
-                    self.namespace.ignore_imports,
-                    self.namespace.ignore_signatures,
-                )
-            )
+            lines = readlines()
         except UnicodeDecodeError:
-            pass
+            lines = []
+
+        self.linesets.append(
+            LineSet(
+                streamid,
+                lines,
+                self.namespace.ignore_comments,
+                self.namespace.ignore_docstrings,
+                self.namespace.ignore_imports,
+                self.namespace.ignore_signatures,
+                line_enabled_callback=self.linter._is_one_message_enabled  # type: ignore[attr-defined]
+                if hasattr(self, "linter")
+                else None,
+            )
+        )
 
     def run(self) -> None:
         """Start looking for similarities and display results on stdout."""

```

### Base source

```python

368:             readlines = stream.readlines  # type: ignore[assignment] # hint parameter is incorrectly typed as non-optional
369:         try:
370:             active_lines: list[str] = []
371:             if hasattr(self, "linter"):
372:                 # Remove those lines that should be ignored because of disables
373:                 for index, line in enumerate(readlines()):
374:                     if self.linter._is_one_message_enabled("R0801", index + 1):  # type: ignore[attr-defined]
375:                         active_lines.append(line)
376:             else:
377:                 active_lines = readlines()
378: 
379:             self.linesets.append(
380:                 LineSet(
381:                     streamid,
382:                     active_lines,
383:                     self.namespace.ignore_comments,
384:                     self.namespace.ignore_docstrings,
385:                     self.namespace.ignore_imports,
386:                     self.namespace.ignore_signatures,
387:                 )
388:             )
389:         except UnicodeDecodeError:
390:             pass
391: 
392:     def run(self) -> None:

```

## Sample 43: `pylint-dev__pylint-7097`

- Status: **exact**

- File: `pylint/checkers/imports.py` — True

- Expected: `ImportsChecker._get_imported_module` / `method`

- Independent AST: `ImportsChecker._get_imported_module` / `method`

- Evidence lines: `803 804 806`; source range: `793-823`


### Patch hunk

```diff

@@ -800,10 +801,10 @@ def _get_imported_module(
                 return None
             self.add_message("relative-beyond-top-level", node=importnode)
         except astroid.AstroidSyntaxError as exc:
-            message = (
-                f"Cannot import {modname!r} due to syntax error {str(exc.error)!r}"
+            message = f"Cannot import {modname!r} due to '{exc.error}'"
+            self.add_message(
+                "syntax-error", line=importnode.lineno, args=message, confidence=HIGH
             )
-            self.add_message("syntax-error", line=importnode.lineno, args=message)
 
         except astroid.AstroidBuildingError:
             if not self.linter.is_message_enabled("import-error"):

```

### Base source

```python

801:             self.add_message("relative-beyond-top-level", node=importnode)
802:         except astroid.AstroidSyntaxError as exc:
803:             message = (
804:                 f"Cannot import {modname!r} due to syntax error {str(exc.error)!r}"
805:             )
806:             self.add_message("syntax-error", line=importnode.lineno, args=message)
807: 
808:         except astroid.AstroidBuildingError:

```

## Sample 44: `astropy__astropy-13465`

- Status: **exact**

- File: `astropy/io/fits/diff.py` — True

- Expected: `TableDataDiff._report` / `method`

- Independent AST: `TableDataDiff._report` / `method`

- Evidence lines: `1436`; source range: `1398-1447`


### Patch hunk

```diff

@@ -1433,7 +1436,8 @@ def _report(self):
         for indx, values in self.diff_values:
             self._writeln(' Column {} data differs in row {}:'.format(*indx))
             report_diff_values(values[0], values[1], fileobj=self._fileobj,
-                               indent_width=self._indent + 1)
+                               indent_width=self._indent + 1, rtol=self.rtol,
+                               atol=self.atol)
 
         if self.diff_values and self.numdiffs < self.diff_total:
             self._writeln(' ...{} additional difference(s) found.'.format(

```

### Base source

```python

1434:             self._writeln(' Column {} data differs in row {}:'.format(*indx))
1435:             report_diff_values(values[0], values[1], fileobj=self._fileobj,
1436:                                indent_width=self._indent + 1)
1437: 
1438:         if self.diff_values and self.numdiffs < self.diff_total:

```

## Sample 45: `django__django-15139`

- Status: **exact**

- File: `django/contrib/sessions/backends/base.py` — True

- Expected: `SessionBase.get_expiry_date` / `method`

- Independent AST: `SessionBase.get_expiry_date` / `method`

- Evidence lines: `235`; source range: `218-237`


### Patch hunk

```diff

@@ -233,6 +235,8 @@ def get_expiry_date(self, **kwargs):
 
         if isinstance(expiry, datetime):
             return expiry
+        elif isinstance(expiry, str):
+            return datetime.fromisoformat(expiry)
         expiry = expiry or self.get_session_cookie_age()
         return modification + timedelta(seconds=expiry)
 

```

### Base source

```python

233: 
234:         if isinstance(expiry, datetime):
235:             return expiry
236:         expiry = expiry or self.get_session_cookie_age()
237:         return modification + timedelta(seconds=expiry)

```

## Sample 46: `pylint-dev__pylint-6528`

- Status: **exact**

- File: `pylint/lint/pylinter.py` — True

- Expected: `PyLinter._discover_files` / `method`

- Independent AST: `PyLinter._discover_files` / `method`

- Evidence lines: `581`; source range: `567-592`


### Patch hunk

```diff

@@ -579,6 +578,16 @@ def _discover_files(files_or_modules: Sequence[str]) -> Iterator[str]:
                     if any(root.startswith(s) for s in skip_subtrees):
                         # Skip subtree of already discovered package.
                         continue
+
+                    if _is_ignored_file(
+                        root,
+                        self.config.ignore,
+                        self.config.ignore_patterns,
+                        self.config.ignore_paths,
+                    ):
+                        skip_subtrees.append(root)
+                        continue
+
                     if "__init__.py" in files:
                         skip_subtrees.append(root)
                         yield root

```

### Base source

```python

579:                     if any(root.startswith(s) for s in skip_subtrees):
580:                         # Skip subtree of already discovered package.
581:                         continue
582:                     if "__init__.py" in files:
583:                         skip_subtrees.append(root)

```

## Sample 47: `psf__requests-1776`

- Status: **exact**

- File: `requests/models.py` — True

- Expected: `PreparedRequest.copy` / `method`

- Independent AST: `PreparedRequest.copy` / `method`

- Evidence lines: `301`; source range: `297-304`


### Patch hunk

```diff

@@ -299,6 +302,7 @@ def copy(self):
         p.method = self.method
         p.url = self.url
         p.headers = self.headers.copy()
+        p._cookies = self._cookies.copy()
         p.body = self.body
         p.hooks = self.hooks
         return p

```

### Base source

```python

299:         p.method = self.method
300:         p.url = self.url
301:         p.headers = self.headers.copy()
302:         p.body = self.body
303:         p.hooks = self.hooks

```

## Sample 48: `mwaskom__seaborn-3187`

- Status: **exact**

- File: `seaborn/_core/scales.py` — True

- Expected: `ContinuousBase._setup` / `method`

- Independent AST: `ContinuousBase._setup` / `method`

- Evidence lines: `380`; source range: `322-384`


### Patch hunk

```diff

@@ -378,6 +378,14 @@ def spacer(x):
             axis.set_view_interval(vmin, vmax)
             locs = axis.major.locator()
             locs = locs[(vmin <= locs) & (locs <= vmax)]
+            # Avoid having an offset / scientific notation in a legend
+            # as we don't represent that anywhere so it ends up incorrect.
+            # This could become an option (e.g. Continuous.label(offset=True))
+            # in which case we would need to figure out how to show it.
+            if hasattr(axis.major.formatter, "set_useOffset"):
+                axis.major.formatter.set_useOffset(False)
+            if hasattr(axis.major.formatter, "set_scientific"):
+                axis.major.formatter.set_scientific(False)
             labels = axis.major.formatter.format_ticks(locs)
             new._legend = list(locs), list(labels)
 

```

### Base source

```python

378:             axis.set_view_interval(vmin, vmax)
379:             locs = axis.major.locator()
380:             locs = locs[(vmin <= locs) & (locs <= vmax)]
381:             labels = axis.major.formatter.format_ticks(locs)
382:             new._legend = list(locs), list(labels)

```

## Sample 49: `pytest-dev__pytest-10893`

- Status: **exact**

- File: `src/_pytest/pathlib.py` — True

- Expected: `<module>` / `module`

- Independent AST: `<module>` / `module`

- Evidence lines: `30`; source range: `module`


### Patch hunk

```diff

@@ -28,6 +29,8 @@
 from typing import Iterator
 from typing import Optional
 from typing import Set
+from typing import Tuple
+from typing import Type
 from typing import TypeVar
 from typing import Union
 

```

### Base source

```python

28: from typing import Iterator
29: from typing import Optional
30: from typing import Set
31: from typing import TypeVar
32: from typing import Union

```

## Sample 50: `sympy__sympy-13279`

- Status: **exact**

- File: `sympy/core/mul.py` — True

- Expected: `Mul.flatten` / `method`

- Independent AST: `Mul.flatten` / `method`

- Evidence lines: `273`; source range: `97-616`


### Patch hunk

```diff

@@ -271,6 +272,10 @@ def flatten(cls, seq):
                 coeff = o.__mul__(coeff)
                 continue
 
+            elif isinstance(o, MatrixExpr):
+                coeff = o.__mul__(coeff)
+                continue
+
             elif o is S.ComplexInfinity:
                 if not coeff:
                     # 0 * zoo = NaN

```

### Base source

```python

271:                 coeff = o.__mul__(coeff)
272:                 continue
273: 
274:             elif o is S.ComplexInfinity:
275:                 if not coeff:

```
