"""NSE option instrument validation.

The desk trades **only** NFO options. Every order path calls :func:`validate_option` and
anything that is not an NSE option tradingsymbol is rejected before it can reach a broker.

Kite tradingsymbol formats for NFO options:

* monthly:  ``NIFTY24SEP25000CE``      -> underlying YY MON strike CE/PE
* weekly:   ``NIFTY24O0125000CE``      -> underlying YY M DD strike CE/PE (M = 1-9, O, N, D)
* stock:    ``RELIANCE24SEP3000CE``
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_EXCHANGE = "NFO"
INDEX_UNDERLYINGS = frozenset({"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"})

_MONTHLY = re.compile(
    r"^(?P<underlying>[A-Z][A-Z0-9&-]{1,20}?)(?P<yy>\d{2})"
    r"(?P<mon>JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
    r"(?P<strike>\d+(?:\.\d+)?)(?P<kind>CE|PE)$"
)
_WEEKLY = re.compile(
    r"^(?P<underlying>[A-Z][A-Z0-9&-]{1,20}?)(?P<yy>\d{2})"
    r"(?P<m>[1-9OND])(?P<dd>0[1-9]|[12]\d|3[01])"
    r"(?P<strike>\d+(?:\.\d+)?)(?P<kind>CE|PE)$"
)


class InstrumentRejected(ValueError):
    """Raised when an instrument is not an NSE option (or the exchange is not NFO)."""


@dataclass(frozen=True)
class OptionInstrument:
    tradingsymbol: str
    underlying: str
    strike: float
    option_type: str  # CE | PE
    expiry_code: str  # raw expiry token from the symbol (e.g. 24SEP or 24O01)
    is_index: bool

    @property
    def exchange(self) -> str:
        return ALLOWED_EXCHANGE


def parse_option_symbol(tradingsymbol: str) -> OptionInstrument:
    sym = (tradingsymbol or "").strip().upper()
    m = _MONTHLY.match(sym) or _WEEKLY.match(sym)
    if not m:
        raise InstrumentRejected(
            f"{tradingsymbol!r} is not an NSE option tradingsymbol (expected e.g. NIFTY24SEP25000CE)"
        )
    g = m.groupdict()
    expiry_code = g["yy"] + (g.get("mon") or (g["m"] + g["dd"]))
    underlying = g["underlying"]
    return OptionInstrument(
        tradingsymbol=sym,
        underlying=underlying,
        strike=float(g["strike"]),
        option_type=g["kind"],
        expiry_code=expiry_code,
        is_index=underlying in INDEX_UNDERLYINGS,
    )


def validate_option(tradingsymbol: str, exchange: str = ALLOWED_EXCHANGE) -> OptionInstrument:
    """Return the parsed option or raise :class:`InstrumentRejected`."""
    if (exchange or "").strip().upper() != ALLOWED_EXCHANGE:
        raise InstrumentRejected(f"exchange {exchange!r} is not allowed; only {ALLOWED_EXCHANGE} options are tradable")
    return parse_option_symbol(tradingsymbol)
