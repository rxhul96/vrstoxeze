from backend.analytics.option_chain import build_chain


def test_chain_depth_windows():
    chain = build_chain(25000, depth=12)
    assert chain["atm"] == 25000
    atm = next(r for r in chain["rows"] if r["atm"])
    assert atm["strike"] == 25000
    # Virtualization contract: UI only paints a depth window, not hundreds of strikes.
    window = [r for r in chain["rows"] if abs(r["strike"] - chain["atm"]) <= chain["step"] * 3]
    assert len(window) == 7
    assert len(chain["rows"]) < 40
