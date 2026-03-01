"""Tests for the trade simulation engine."""

import pytest
from prompt_validator.scenarios import (
    generate_strong_uptrend, generate_strong_downtrend, generate_range_bound,
    generate_high_volatility, generate_low_volatility, generate_trend_reversal,
    generate_v_recovery, generate_breakout, generate_choppy, generate_flash_crash,
    generate_all_scenarios, Bar, Scenario,
)
from prompt_validator.simulator import (
    simulate, simulate_all, SimResult, Trade,
    _ema, _sma, _atr, _rsi, _adx, _stddev, _bollinger,
    STRATEGY_REGISTRY,
)


# =====================================================================
# Scenario Generation Tests
# =====================================================================

class TestScenarios:
    def test_all_scenarios_generated(self):
        scenarios = generate_all_scenarios(100)
        assert len(scenarios) == 10

    def test_scenario_has_bars(self):
        s = generate_strong_uptrend(200)
        assert len(s.bars) == 200
        assert s.name == "STRONG_UPTREND"

    def test_bar_consistency(self):
        """OHLC must satisfy H >= O,C and L <= O,C."""
        for gen in [generate_strong_uptrend, generate_range_bound, generate_flash_crash]:
            s = gen(100)
            for b in s.bars:
                assert b.high >= b.open, f"High < Open at bar {b.timestamp}"
                assert b.high >= b.close, f"High < Close at bar {b.timestamp}"
                assert b.low <= b.open, f"Low > Open at bar {b.timestamp}"
                assert b.low <= b.close, f"Low > Close at bar {b.timestamp}"
                assert b.low > 0, "Price must be positive"
                assert b.volume > 0, "Volume must be positive"

    def test_uptrend_ends_higher(self):
        s = generate_strong_uptrend(200)
        assert s.bars[-1].close > s.bars[0].close

    def test_downtrend_ends_lower(self):
        s = generate_strong_downtrend(200)
        assert s.bars[-1].close < s.bars[0].close

    def test_deterministic_reproducibility(self):
        """Same seed produces same bars."""
        s1 = generate_strong_uptrend(100)
        s2 = generate_strong_uptrend(100)
        for b1, b2 in zip(s1.bars, s2.bars):
            assert b1.close == b2.close
            assert b1.high == b2.high

    def test_different_seeds_differ(self):
        s1 = generate_strong_uptrend(100)
        s2 = generate_strong_downtrend(100)
        # Different drift/seed should give different data
        assert s1.bars[-1].close != s2.bars[-1].close


# =====================================================================
# Indicator Tests
# =====================================================================

class TestIndicators:
    def test_ema_length(self):
        vals = [float(i) for i in range(100)]
        result = _ema(vals, 10)
        assert len(result) == 100

    def test_sma_correctness(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _sma(vals, 3)
        assert abs(result[2] - 2.0) < 0.01  # (1+2+3)/3
        assert abs(result[4] - 4.0) < 0.01  # (3+4+5)/3

    def test_rsi_range(self):
        """RSI must be between 0 and 100."""
        s = generate_high_volatility(200)
        closes = [b.close for b in s.bars]
        rsi = _rsi(closes, 14)
        for v in rsi:
            assert 0 <= v <= 100, f"RSI out of range: {v}"

    def test_atr_positive(self):
        s = generate_strong_uptrend(200)
        atr = _atr(s.bars, 14)
        for v in atr:
            assert v >= 0

    def test_adx_non_negative(self):
        s = generate_strong_uptrend(200)
        adx = _adx(s.bars, 14)
        for v in adx:
            assert v >= 0

    def test_bollinger_bands_order(self):
        closes = [float(100 + i * 0.1) for i in range(100)]
        upper, mid, lower = _bollinger(closes, 20, 2.0)
        for i in range(20, 100):
            assert upper[i] >= mid[i] >= lower[i]


# =====================================================================
# Simulator Tests
# =====================================================================

class TestSimulator:
    def test_all_models_registered(self):
        expected = {"SATVA", "VORTEX", "NEXUS", "PRISM", "FLUX", "TITAN"}
        assert set(STRATEGY_REGISTRY.keys()) == expected

    def test_invalid_model_raises(self):
        s = generate_strong_uptrend(100)
        with pytest.raises(ValueError):
            simulate("INVALID", s)

    def test_simulate_returns_result(self):
        s = generate_strong_uptrend(200)
        result = simulate("SATVA", s)
        assert isinstance(result, SimResult)
        assert result.model == "SATVA"
        assert result.scenario == "STRONG_UPTREND"

    def test_trade_pnl_direction(self):
        """Winning trades should have positive PnL, losing negative."""
        s = generate_strong_uptrend(500)
        result = simulate("VORTEX", s)
        for t in result.trades:
            if t.is_winner:
                assert t.pnl_pct > 0
            if t.is_loser:
                assert t.pnl_pct < 0

    def test_halt_on_daily_loss(self):
        """Models should halt when daily loss limit is hit."""
        s = generate_flash_crash(500)
        for model in STRATEGY_REGISTRY:
            result = simulate(model, s)
            # If halted, check reason exists
            if result.halted:
                assert result.halt_reason != ""

    def test_all_models_all_scenarios(self):
        """Every model should run against every scenario without error."""
        all_results = simulate_all(n_bars=100)
        assert len(all_results) == 6
        for model, results in all_results.items():
            assert len(results) == 10  # 10 scenarios
            for r in results:
                assert isinstance(r, SimResult)

    def test_deterministic_results(self):
        """Same inputs should always produce same results."""
        r1 = simulate_all(n_bars=100)
        r2 = simulate_all(n_bars=100)
        for model in STRATEGY_REGISTRY:
            for s1, s2 in zip(r1[model], r2[model]):
                assert s1.total_trades == s2.total_trades
                assert abs(s1.total_pnl_pct - s2.total_pnl_pct) < 0.0001

    def test_sim_result_properties(self):
        s = generate_strong_uptrend(500)
        result = simulate("SATVA", s)
        assert result.win_count + result.loss_count <= result.total_trades
        assert result.win_rate >= 0
        if result.trades:
            assert result.expectancy != 0 or all(t.pnl_pct == 0 for t in result.trades)


class TestTradeObject:
    def test_winner(self):
        t = Trade("TEST", "SCENARIO", 0, 5, "LONG", 100.0, 105.0, 95.0, 110.0, 5.0, 2.0, "target")
        assert t.is_winner is True
        assert t.is_loser is False

    def test_loser(self):
        t = Trade("TEST", "SCENARIO", 0, 3, "LONG", 100.0, 95.0, 95.0, 110.0, -5.0, -1.0, "stop")
        assert t.is_winner is False
        assert t.is_loser is True

    def test_breakeven(self):
        t = Trade("TEST", "SCENARIO", 0, 5, "LONG", 100.0, 100.0, 95.0, 110.0, 0.0, 0.0, "time")
        assert t.is_winner is False
        assert t.is_loser is False


class TestSimResultMetrics:
    def test_profit_factor(self):
        r = SimResult("TEST", "TEST")
        r.trades = [
            Trade("T", "S", 0, 1, "L", 100, 110, 95, 110, 10.0, 2.0, "t"),
            Trade("T", "S", 2, 3, "L", 100, 95, 95, 110, -5.0, -1.0, "s"),
        ]
        assert r.profit_factor == 2.0  # 10/5

    def test_max_drawdown(self):
        r = SimResult("TEST", "TEST")
        r.trades = [
            Trade("T", "S", 0, 1, "L", 100, 110, 95, 110, 5.0, 1.0, "t"),
            Trade("T", "S", 2, 3, "L", 100, 95, 95, 110, -3.0, -1.0, "s"),
            Trade("T", "S", 4, 5, "L", 100, 92, 95, 110, -4.0, -1.0, "s"),
        ]
        # Equity: 5, 2, -2 → peak=5, max dd = 5-(-2) = 7
        assert r.max_drawdown == 7.0

    def test_empty_result(self):
        r = SimResult("TEST", "TEST")
        assert r.win_rate == 0
        assert r.profit_factor == 0
        assert r.max_drawdown == 0
        assert r.expectancy == 0
