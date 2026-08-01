"""Deprecated compatibility shim: the package is now `causal_data_juicer`.

Old imports (`from causeforge.x import Y`) keep working by aliasing the
module tree; new code should import `causal_data_juicer` directly.
"""
import sys as _sys
import warnings as _warnings

import causal_data_juicer as _pkg

_warnings.warn("`causeforge` is renamed to `causal_data_juicer`; "
               "update your imports.", DeprecationWarning, stacklevel=2)
_sys.modules[__name__] = _pkg
