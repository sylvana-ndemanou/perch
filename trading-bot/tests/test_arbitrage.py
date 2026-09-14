from src.arbitrage import Direction, Triangle, evaluate_triangle, scan
from src.market_data import MarketDataStore

TRIANGLE = Triangle(alt="ETH", quote_asset="USDT", bridge_asset="BTC")


def make_store(btc_usdt: tuple[float, float], eth_btc: tuple[float, float], eth_usdt: tuple[float, float]) -> MarketDataStore:
    store = MarketDataStore()
    store.update("BTCUSDT", bid=btc_usdt[0], bid_qty=1, ask=btc_usdt[1], ask_qty=1)
    store.update("ETHBTC", bid=eth_btc[0], bid_qty=1, ask=eth_btc[1], ask_qty=1)
    store.update("ETHUSDT", bid=eth_usdt[0], bid_qty=1, ask=eth_usdt[1], ask_qty=1)
    return store


def test_no_opportunity_when_prices_are_consistent():
    # ETH/USDT implied from BTC/USDT * ETH/BTC exactly matches the direct
    # ETH/USDT price, so after fees both directions should be losing trades.
    store = make_store(btc_usdt=(50000, 50010), eth_btc=(0.05, 0.0501), eth_usdt=(2500, 2505.5))
    opportunities = scan([TRIANGLE], store, fee_rate=0.001, start_amount=1000, min_profit_pct=0.0)
    assert all(o.profit_pct < 0 for o in opportunities)


def test_forward_opportunity_detected_when_alt_quote_price_is_too_high():
    # Direct ETH/USDT bid is far above what buying BTC then ETH would cost,
    # so USDT -> BTC -> ETH -> USDT should show a clear profit.
    store = make_store(btc_usdt=(50000, 50010), eth_btc=(0.05, 0.0501), eth_usdt=(2600, 2605))
    opportunities = evaluate_triangle(TRIANGLE, store, fee_rate=0.001, start_amount=1000)
    forward = next(o for o in opportunities if o.direction is Direction.FORWARD)
    assert forward.profit_pct > 0.01
    assert forward.end_amount > forward.start_amount


def test_reverse_opportunity_detected_when_alt_quote_price_is_too_low():
    # Direct ETH/USDT ask is far below the BTC-bridged rate, so
    # USDT -> ETH -> BTC -> USDT should show a clear profit.
    store = make_store(btc_usdt=(50000, 50010), eth_btc=(0.05, 0.0501), eth_usdt=(2380, 2385))
    opportunities = evaluate_triangle(TRIANGLE, store, fee_rate=0.001, start_amount=1000)
    reverse = next(o for o in opportunities if o.direction is Direction.REVERSE)
    assert reverse.profit_pct > 0.01


def test_scan_filters_below_min_profit_and_sorts_best_first():
    store = make_store(btc_usdt=(50000, 50010), eth_btc=(0.05, 0.0501), eth_usdt=(2600, 2605))
    hits = scan([TRIANGLE], store, fee_rate=0.001, start_amount=1000, min_profit_pct=0.5)
    assert hits == []

    hits = scan([TRIANGLE], store, fee_rate=0.001, start_amount=1000, min_profit_pct=0.001)
    assert len(hits) >= 1
    assert hits[0].profit_pct == max(o.profit_pct for o in hits)


def test_missing_market_data_yields_no_opportunities():
    store = MarketDataStore()  # empty
    opportunities = evaluate_triangle(TRIANGLE, store, fee_rate=0.001, start_amount=1000)
    assert opportunities == []
