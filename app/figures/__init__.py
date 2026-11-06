"""The canonical figure registry (owner's Handoff 1, 2026-11-03): one definition and one value for each financial
figure, shared by the Dossier, Compare and Milo. `registry` says what each figure is; `compute` works out each one's value."""

from .registry import IDS, REGISTRY, VERSION, definition, public
from .compute import compact, for_ticker, forward_pe, load, load_via, net_debt_value, resolve, unavailable

__all__ = ["IDS", "REGISTRY", "VERSION", "definition", "public", "compact", "for_ticker", "forward_pe", "load",
           "load_via", "net_debt_value", "resolve", "unavailable"]
