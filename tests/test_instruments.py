import pytest

from optionsdesk.instruments import InstrumentRejected, parse_option_symbol, validate_option


@pytest.mark.parametrize(
    "sym,underlying,strike,kind,is_index",
    [
        ("NIFTY24SEP25000CE", "NIFTY", 25000.0, "CE", True),
        ("BANKNIFTY24O0952000PE", "BANKNIFTY", 52000.0, "PE", True),
        ("FINNIFTY24N1223500CE", "FINNIFTY", 23500.0, "CE", True),
        ("MIDCPNIFTY24D3112500PE", "MIDCPNIFTY", 12500.0, "PE", True),
        ("RELIANCE24SEP3000CE", "RELIANCE", 3000.0, "CE", False),
        ("M&M24OCT2900PE", "M&M", 2900.0, "PE", False),
        ("nifty24sep25000ce", "NIFTY", 25000.0, "CE", True),
    ],
)
def test_parses_nse_option_symbols(sym, underlying, strike, kind, is_index):
    inst = parse_option_symbol(sym)
    assert (inst.underlying, inst.strike, inst.option_type, inst.is_index) == (underlying, strike, kind, is_index)
    assert inst.exchange == "NFO"


@pytest.mark.parametrize(
    "sym",
    [
        "NIFTY24SEPFUT",  # futures
        "RELIANCE",  # equity
        "NIFTY 50",  # index
        "INFY-EQ",
        "NIFTY24SEP25000",  # no CE/PE
        "24SEP25000CE",
        "",
        "USDINR24SEP84CE",  # looks like an option but is not allowed on NFO... parses; see exchange test
    ],
)
def test_rejects_non_option_symbols(sym):
    if sym == "USDINR24SEP84CE":
        # Currency options live on CDS; they are rejected by the exchange check, not the regex.
        with pytest.raises(InstrumentRejected):
            validate_option(sym, "CDS")
        return
    with pytest.raises(InstrumentRejected):
        parse_option_symbol(sym)


@pytest.mark.parametrize("exchange", ["NSE", "BSE", "BFO", "MCX", "CDS", "", "nfo "])
def test_exchange_must_be_nfo(exchange):
    if exchange.strip().upper() == "NFO":
        assert validate_option("NIFTY24SEP25000CE", exchange).tradingsymbol == "NIFTY24SEP25000CE"
    else:
        with pytest.raises(InstrumentRejected, match="exchange"):
            validate_option("NIFTY24SEP25000CE", exchange)
