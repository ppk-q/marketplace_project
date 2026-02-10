"""Compatibility facade for constants.

Deprecated for new code:
- `app.constants_auth`
- `app.constants_blog`
- `app.constants_media`
- `app.constants_api`
- `app.constants_system`

Старые импорты через `app.constants` оставлены для обратной совместимости.
"""

from __future__ import annotations

from app import constants_api as _api_constants
from app import constants_auth as _auth_constants
from app import constants_blog as _blog_constants
from app import constants_media as _media_constants
from app import constants_system as _system_constants

# Re-export UPPER_CASE constants from domain modules for legacy imports.
_CONSTANT_MODULES = (
    _api_constants,
    _auth_constants,
    _blog_constants,
    _media_constants,
    _system_constants,
)

for _module in _CONSTANT_MODULES:
    globals().update(
        {name: value for name, value in vars(_module).items() if name.isupper()}
    )

__all__ = sorted(name for name in globals() if name.isupper())

del _module
del _CONSTANT_MODULES
del _api_constants
del _auth_constants
del _blog_constants
del _media_constants
del _system_constants
