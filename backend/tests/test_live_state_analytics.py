from app.services.live_state import CanonicalQuote, LiveStateStore

def test_live_state_preserves_null_fields_and_replaces_changed_quote():
    store = LiveStateStore()
    assert store.update_quote(CanonicalQuote(symbol="NIFRA", ltp=100, change_percent=1.5))
    snap = store.snapshot()
    assert snap.quotes["NIFRA"].high is None
    assert store.update_quote(CanonicalQuote(symbol="NIFRA", ltp=101, change_percent=2.5))
    assert store.snapshot().quotes["NIFRA"].ltp == 101

def test_identical_live_quote_is_suppressed():
    store = LiveStateStore(); quote = CanonicalQuote(symbol="NABIL", ltp=500, change_percent=0)
    assert store.update_quote(quote)
    assert not store.update_quote(CanonicalQuote(symbol="NABIL", ltp=500, change_percent=0))
