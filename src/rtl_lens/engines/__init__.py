"""Analysis-engine adapters exposed by RTL Lens."""

from typing import TYPE_CHECKING

from rtl_lens.engines.base import AnalysisEngine

if TYPE_CHECKING:
    from rtl_lens.engines.pyslang_engine import PySlangEngine

__all__ = ["AnalysisEngine", "PySlangEngine"]


def __getattr__(name: str) -> object:
    """Load native analyzer bindings only when their adapter is requested."""
    if name == "PySlangEngine":
        from rtl_lens.engines.pyslang_engine import PySlangEngine

        return PySlangEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
