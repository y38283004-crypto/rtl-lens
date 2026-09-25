"""Installed package and analyzer compatibility information."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from rtl_lens import __version__ as source_version

PACKAGE_NAME = "rtl-lens"
PYSLANG_COMPATIBILITY = ">=11,<12"
VERILATOR_COMPATIBILITY = ">=5.040"


def package_version() -> str:
    """Return installed metadata, with a source-tree fallback for contributors."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return source_version
