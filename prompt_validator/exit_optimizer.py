"""Exit Strategy Optimizer for SATVA v15 trading system.

Tests multiple exit strategy variations across all 10 market scenarios to find
the optimal exit configuration. Measures win rate, expectancy, profit factor,
giveback, and time-stop effectiveness per regime.

Run as: python -m prompt_validator.exit_optimizer
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import Optional

from prompt_validator.scenarios import Bar, Scenario, generate_all_scenarios


# ---------------------------------------------------------------------------
# Indicator helpers (replicated from simulator.py for self-containment)
# ---------------------------------------------------------------------------

def _ema(values: list[float], period: int) -> list[float]:
    result = [0.0] * len(values)
    if not values or period < 1:
        return result
    k = 2.0 / (period + 1)
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def _sma(values: list[float], period: int) -> list[float]:
    result = [0.0] * len(values)
    for i in range(len(values)):
        if i < period - 1:
            result[i] = sum(values[: i + 1]) / (i + 1)
        else:
            result[i] = sum(values[i - period + 1 : i + 1]) / period
    return result


def _atr(bars: list[Bar], period: int = 14) -> list[float]:
    trs: list[float] = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b.high - b.low)
        else:
            tr = max(
                b.high - b.low,
                abs(b.high - bars[i - 1].close),
                abs(b.low - bars[i - 1].close),
            )
            trs.append(tr)
    return _sma(trs, period)


def _rsi(closes: list[float], period: int = 14) -> list[float]:
    result = [50.0] * len(closes)
    if len(closes) < period + 1:
        return result
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = 100 - (100 / (1 + rs))
    return result


def _linreg_slope(values: list[float]) -> float:
    """Linear regression slope over a window of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PricePath:
    """Forward price path from an entry point."""
    entry_price: float
    entry_idx: int
    direction: str          # "LONG" or "SHORT"
    atr: float
    stop_dist: float        # |entry - stop| in price
    bars: list[Bar]         # the full scenario bars (referenced, not copied)
    max_forward: int = 60   # look-ahead bars

    @property
    def r_trade(self) -> float:
        return self.stop_dist

    def signed_pnl(self, exit_price: float) -> float:
        """P&L in price points, positive = profit."""
        if self.direction == "LONG":
            return exit_price - self.entry_price
        return self.entry_price - exit_price

    def r_multiple(self, exit_price: float) -> float:
        pnl = self.signed_pnl(exit_price)
        return pnl / self.r_trade if self.r_trade > 0 else 0.0

    @property
    def forward_bars(self) -> list[Bar]:
        start = self.entry_idx + 1
        end = min(start + self.max_forward, len(self.bars))
        return self.bars[start:end]

    def high_water(self, up_to_bar_offset: int) -> float:
        """Highest favorable excursion in price up to offset bars after entry."""
        best = self.entry_price
        for k, b in enumerate(self.forward_bars):
            if k >= up_to_bar_offset:
                break
            if self.direction == "LONG":
                best = max(best, b.high)
            else:
                best = min(best, b.low)
        return best


@dataclass
class ExitResult:
    """Result of applying an exit strategy to one trade."""
    strategy: str
    direction: str
    entry_price: float
    exit_price: float
    r_multiple: float
    bars_held: int
    exit_reason: str
    peak_r: float = 0.0      # max R reached before exit
    giveback_r: float = 0.0   # R given back from peak


@dataclass
class StrategyStats:
    """Aggregate statistics for one exit strategy."""
    name: str
    trades: list[ExitResult] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.trades)

    @property
    def winners(self) -> list[ExitResult]:
        return [t for t in self.trades if t.r_multiple > 0]

    @property
    def losers(self) -> list[ExitResult]:
        return [t for t in self.trades if t.r_multiple <= 0]

    @property
    def win_rate(self) -> float:
        return len(self.winners) / self.n * 100 if self.n else 0.0

    @property
    def avg_winner_r(self) -> float:
        w = self.winners
        return sum(t.r_multiple for t in w) / len(w) if w else 0.0

    @property
    def avg_loser_r(self) -> float:
        lo = self.losers
        return sum(t.r_multiple for t in lo) / len(lo) if lo else 0.0

    @property
    def expectancy(self) -> float:
        if not self.n:
            return 0.0
        return sum(t.r_multiple for t in self.trades) / self.n

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.r_multiple for t in self.winners)
        gross_loss = abs(sum(t.r_multiple for t in self.losers))
        if gross_loss == 0:
            return float("inf") if gross_win > 0 else 0.0
        return gross_win / gross_loss

    @property
    def total_r(self) -> float:
        return sum(t.r_multiple for t in self.trades)

    @property
    def avg_giveback_r(self) -> float:
        w = self.winners
        return sum(t.giveback_r for t in w) / len(w) if w else 0.0

    @property
    def avg_bars_held(self) -> float:
        return sum(t.bars_held for t in self.trades) / self.n if self.n else 0.0


# ---------------------------------------------------------------------------
# Regime classifier (simplified from v15 Section 17)
# ---------------------------------------------------------------------------

def classify_regime(scenario: Scenario) -> str:
    """Map scenario name to a SATVA regime for analysis grouping."""
    mapping = {
        "STRONG_UPTREND": "STRONG_TREND",
        "STRONG_DOWNTREND": "STRONG_TREND",
        "RANGE_BOUND": "RANGE",
        "HIGH_VOLATILITY": "SHOCK",
        "LOW_VOLATILITY": "RANGE",
        "TREND_REVERSAL": "TREND",
        "V_RECOVERY": "SHOCK",
        "BREAKOUT": "TREND",
        "CHOPPY": "UNCLEAR",
        "FLASH_CRASH": "SHOCK",
    }
    return mapping.get(scenario.name, "UNCLEAR")


# ---------------------------------------------------------------------------
# 1. Trade Simulator — simulate_trade()
# ---------------------------------------------------------------------------

def simulate_trade(
    bars: list[Bar],
    entry_idx: int,
    direction: str,
    atr: float,
    stop_dist: float,
    max_forward: int = 60,
) -> PricePath:
    """Create a PricePath for forward analysis from an entry point.

    Args:
        bars: Full scenario bar list.
        entry_idx: Index of the entry bar.
        direction: "LONG" or "SHORT".
        atr: ATR value at entry.
        stop_dist: Distance from entry to stop in price points.
        max_forward: Maximum bars to look ahead (default 60).

    Returns:
        PricePath object with full price path for analysis.
    """
    return PricePath(
        entry_price=bars[entry_idx].close,
        entry_idx=entry_idx,
        direction=direction,
        atr=atr,
        stop_dist=stop_dist,
        bars=bars,
        max_forward=max_forward,
    )


# ---------------------------------------------------------------------------
# 5. Entry Signal Generator
# ---------------------------------------------------------------------------

def generate_entries(scenario: Scenario, min_entries: int = 20, max_entries: int = 50) -> list[PricePath]:
    """Generate realistic entry signals across a scenario.

    Uses:
      LONG: EMA9 > EMA21 + RSI 40-70 + volume > avg
      SHORT: EMA9 < EMA21 + RSI 30-60 + volume > avg
      Stop at recent swing low/high +/- slippage.

    Returns list of PricePath objects, 20-50 per scenario.
    """
    bars = scenario.bars
    if len(bars) < 40:
        return []

    closes = [b.close for b in bars]
    volumes = [float(b.volume) for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    rsi = _rsi(closes, 14)
    atr = _atr(bars, 14)
    avg_vol = _sma(volumes, 20)

    entries: list[PricePath] = []
    cooldown = 0

    for i in range(30, len(bars) - 10):
        if cooldown > 0:
            cooldown -= 1
            continue
        if len(entries) >= max_entries:
            break
        if atr[i] <= 0:
            continue

        vol_ok = bars[i].volume > avg_vol[i] if avg_vol[i] > 0 else False

        # Find swing low/high for stop placement
        lookback = bars[max(0, i - 10) : i]
        if not lookback:
            continue
        swing_low = min(b.low for b in lookback)
        swing_high = max(b.high for b in lookback)

        slippage = max(0.01, 0.02 * atr[i])
        direction = None

        # LONG: EMA9 > EMA21, RSI 40-70, volume > avg
        if ema9[i] > ema21[i] and 40 <= rsi[i] <= 70 and vol_ok:
            stop = swing_low - slippage
            stop_dist = bars[i].close - stop
            if stop_dist > 0 and stop_dist <= 1.8 * atr[i]:
                direction = "LONG"

        # SHORT: EMA9 < EMA21, RSI 30-60, volume > avg
        elif ema9[i] < ema21[i] and 30 <= rsi[i] <= 60 and vol_ok:
            stop = swing_high + slippage
            stop_dist = stop - bars[i].close
            if stop_dist > 0 and stop_dist <= 1.8 * atr[i]:
                direction = "SHORT"

        if direction:
            path = simulate_trade(bars, i, direction, atr[i], stop_dist, max_forward=60)
            entries.append(path)
            # Adaptive cooldown: fewer entries available → less cooldown
            cooldown = max(2, (len(bars) - 40) // max_entries)

    return entries


# ---------------------------------------------------------------------------
# 2. Exit Strategy Tester
# ---------------------------------------------------------------------------

def _apply_exit_strategy(path: PricePath, strategy: str) -> ExitResult:
    """Apply a named exit strategy to a PricePath and return the result."""
    entry = path.entry_price
    atr = path.atr
    r_trade = path.r_trade
    d = path.direction
    fwd = path.forward_bars

    if not fwd or r_trade <= 0 or atr <= 0:
        return ExitResult(strategy, d, entry, entry, 0.0, 0, "no_bars")

    # Strategy parameters
    configs = _get_strategy_config(strategy, atr, entry, d, path)

    tiers = configs["tiers"]           # list of (pct, target_price)
    trail_atr_mult = configs["trail_atr_mult"]
    giveback_kill = configs["giveback_kill"]  # fraction of ATR
    max_hold = configs.get("max_hold", 60)
    be_threshold_r = configs.get("be_threshold_r", None)  # move to BE after this R
    dynamic_trail = configs.get("dynamic_trail", False)
    time_decay_trail = configs.get("time_decay_trail", False)
    vol_adaptive = configs.get("vol_adaptive", False)

    stop = entry - r_trade if d == "LONG" else entry + r_trade
    remaining_pct = 1.0
    realized_r = 0.0
    tier_idx = 0
    peak_price = entry
    trailing_active = False
    trail_stop = stop
    bars_held = 0
    be_moved = False
    peak_r = 0.0

    for k, bar in enumerate(fwd):
        if k >= max_hold:
            # Time stop
            exit_p = bar.close
            unrealized = path.signed_pnl(exit_p) / r_trade * remaining_pct
            realized_r += unrealized
            return ExitResult(
                strategy, d, entry, exit_p, realized_r, k,
                "time_stop", peak_r, max(0, peak_r - realized_r),
            )

        bars_held = k + 1

        # Check stop hit
        if d == "LONG":
            if bar.low <= stop:
                unrealized = (stop - entry) / r_trade * remaining_pct
                realized_r += unrealized
                return ExitResult(
                    strategy, d, entry, stop, realized_r, bars_held,
                    "stop_hit", peak_r, max(0, peak_r - realized_r),
                )
        else:
            if bar.high >= stop:
                unrealized = (entry - stop) / r_trade * remaining_pct
                realized_r += unrealized
                return ExitResult(
                    strategy, d, entry, stop, realized_r, bars_held,
                    "stop_hit", peak_r, max(0, peak_r - realized_r),
                )

        # Update peak
        if d == "LONG":
            peak_price = max(peak_price, bar.high)
        else:
            peak_price = min(peak_price, bar.low)

        current_r_at_peak = abs(peak_price - entry) / r_trade
        peak_r = max(peak_r, current_r_at_peak)

        # Breakeven move
        if be_threshold_r is not None and not be_moved:
            current_favorable = path.signed_pnl(bar.close) / r_trade
            if current_favorable >= be_threshold_r:
                be_pad = 0.10 * atr
                if d == "LONG":
                    stop = max(stop, entry + be_pad)
                else:
                    stop = min(stop, entry - be_pad)
                be_moved = True

        # Check tier targets
        while tier_idx < len(tiers) and remaining_pct > 0:
            pct, target = tiers[tier_idx]
            hit = False
            if d == "LONG" and bar.high >= target:
                hit = True
            elif d == "SHORT" and bar.low <= target:
                hit = True

            if hit:
                partial_r = path.signed_pnl(target) / r_trade * pct
                realized_r += partial_r
                remaining_pct -= pct
                tier_idx += 1

                # Adjust stop after partial
                if tier_idx == 1:
                    # After T1: move stop to breakeven + pad
                    be_pad = 0.10 * atr
                    if d == "LONG":
                        stop = max(stop, entry + be_pad)
                    else:
                        stop = min(stop, entry - be_pad)
                    be_moved = True
                elif tier_idx == 2 and len(tiers) >= 2:
                    # After T2: move stop to T1
                    t1_price = tiers[0][1]
                    if d == "LONG":
                        stop = max(stop, t1_price)
                    else:
                        stop = min(stop, t1_price)
                    trailing_active = True
                elif tier_idx >= 3:
                    trailing_active = True
            else:
                break

        if remaining_pct <= 0.001:
            return ExitResult(
                strategy, d, entry, tiers[-1][1] if tiers else entry,
                realized_r, bars_held, "all_targets",
                peak_r, max(0, peak_r - realized_r),
            )

        # Trailing stop for runner portion
        if trailing_active and remaining_pct > 0:
            # Compute effective trail multiplier
            eff_trail = trail_atr_mult

            if dynamic_trail:
                # TAS proxy: use EMA alignment strength
                closes_window = [path.bars[path.entry_idx + j].close
                                 for j in range(max(0, k - 10), k + 1)
                                 if path.entry_idx + j < len(path.bars)]
                if len(closes_window) >= 5:
                    ema_fast = _ema(closes_window, 3)
                    ema_slow = _ema(closes_window, 8)
                    strong_trend = (ema_fast[-1] > ema_slow[-1]) if d == "LONG" else (ema_fast[-1] < ema_slow[-1])
                    eff_trail = 0.8 if strong_trend else 1.2

            if time_decay_trail:
                # Trail tightens: starts at 1.5*ATR, reduces 0.05 per 5 bars
                eff_trail = max(0.5, 1.5 - 0.05 * (bars_held // 5))

            if vol_adaptive:
                # Use recent bar ranges as proxy for volatility change
                recent_ranges = [path.bars[path.entry_idx + j].high - path.bars[path.entry_idx + j].low
                                 for j in range(max(0, k - 5), k + 1)
                                 if path.entry_idx + j < len(path.bars)]
                if recent_ranges:
                    current_vol = sum(recent_ranges) / len(recent_ranges)
                    vol_ratio = current_vol / atr if atr > 0 else 1.0
                    if vol_ratio > 1.2:
                        eff_trail = trail_atr_mult * 1.3  # widen
                    elif vol_ratio < 0.8:
                        eff_trail = trail_atr_mult * 0.7  # tighten

            # Ratchet trail
            if d == "LONG":
                new_trail = bar.close - eff_trail * atr
                trail_stop = max(trail_stop if trailing_active else stop, new_trail)
                stop = max(stop, trail_stop)
            else:
                new_trail = bar.close + eff_trail * atr
                trail_stop = min(trail_stop if trailing_active else stop, new_trail)
                stop = min(stop, trail_stop)

            # Giveback kill
            if giveback_kill > 0:
                if d == "LONG":
                    giveback = peak_price - bar.close
                else:
                    giveback = bar.close - peak_price
                if giveback >= giveback_kill * atr:
                    exit_p = bar.close
                    unrealized = path.signed_pnl(exit_p) / r_trade * remaining_pct
                    realized_r += unrealized
                    return ExitResult(
                        strategy, d, entry, exit_p, realized_r, bars_held,
                        "giveback_kill", peak_r, max(0, peak_r - realized_r),
                    )

    # Exhausted forward bars
    if fwd:
        exit_p = fwd[-1].close
        unrealized = path.signed_pnl(exit_p) / r_trade * remaining_pct
        realized_r += unrealized
        return ExitResult(
            strategy, d, entry, exit_p, realized_r, len(fwd),
            "bars_exhausted", peak_r, max(0, peak_r - realized_r),
        )

    return ExitResult(strategy, d, entry, entry, 0.0, 0, "no_data")


def _get_strategy_config(
    strategy: str, atr: float, entry: float, direction: str, path: PricePath
) -> dict:
    """Return exit configuration dict for a given strategy name."""
    d = direction
    r = path.r_trade

    # Helper to compute target price from entry
    def _target(mult: float) -> float:
        if d == "LONG":
            return entry + mult * atr
        return entry - mult * atr

    # T1 per v15: max(0.9*ATR, distance_to_nearest_level) — we use 0.9*ATR
    # as we don't have real level data in synthetic scenarios.
    t1_v15 = _target(0.9)
    t2_v15 = _target(1.6)
    t3_v15 = _target(2.4)

    defaults = {
        "trail_atr_mult": 1.0,
        "giveback_kill": 0.35,
        "max_hold": 60,
        "be_threshold_r": None,
        "dynamic_trail": False,
        "time_decay_trail": False,
        "vol_adaptive": False,
    }

    if strategy == "v15_baseline":
        # (a) Current v15: 40/30/30 at T1/T2/T3
        defaults["tiers"] = [(0.40, t1_v15), (0.30, t2_v15), (0.30, t3_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "aggressive_runner":
        # (b) 50/25/25
        defaults["tiers"] = [(0.50, t1_v15), (0.25, t2_v15), (0.25, t3_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "conservative_runner":
        # (c) 33/33/34
        defaults["tiers"] = [(0.33, t1_v15), (0.33, t2_v15), (0.34, t3_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "heavy_runner":
        # (d) 30/30/40
        defaults["tiers"] = [(0.30, t1_v15), (0.30, t2_v15), (0.40, t3_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "two_tier":
        # (e) 60/40 at T1/T2 — no runner
        defaults["tiers"] = [(0.60, t1_v15), (0.40, t2_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.0  # no runner → no giveback

    elif strategy == "four_tier":
        # (f) 30/25/25/20 at T1/T2/T3/T4
        t4 = _target(3.0)
        defaults["tiers"] = [(0.30, t1_v15), (0.25, t2_v15), (0.25, t3_v15), (0.20, t4)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "atr_scaled_wide":
        # (g) Wider targets: T1=1.2, T2=2.0, T3=3.0
        defaults["tiers"] = [(0.40, _target(1.2)), (0.30, _target(2.0)), (0.30, _target(3.0))]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "tight_targets":
        # (h) Tight: T1=0.7, T2=1.2, T3=1.8
        defaults["tiers"] = [(0.40, _target(0.7)), (0.30, _target(1.2)), (0.30, _target(1.8))]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35

    elif strategy == "dynamic_trail":
        # (i) Trail adapts to trend strength
        defaults["tiers"] = [(0.40, t1_v15), (0.30, t2_v15), (0.30, t3_v15)]
        defaults["trail_atr_mult"] = 1.0  # overridden dynamically
        defaults["giveback_kill"] = 0.35
        defaults["dynamic_trail"] = True

    elif strategy == "time_decay_trail":
        # (j) Trail tightens over time
        defaults["tiers"] = [(0.40, t1_v15), (0.30, t2_v15), (0.30, t3_v15)]
        defaults["trail_atr_mult"] = 1.5  # starting value
        defaults["giveback_kill"] = 0.35
        defaults["time_decay_trail"] = True

    elif strategy == "vol_adaptive":
        # (k) Trail adapts to ATR expansion/contraction
        defaults["tiers"] = [(0.40, t1_v15), (0.30, t2_v15), (0.30, t3_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35
        defaults["vol_adaptive"] = True

    elif strategy.startswith("be_speed_"):
        # (l) Breakeven speed test: be_speed_0.5, be_speed_0.8, etc.
        be_r = float(strategy.split("_")[-1])
        defaults["tiers"] = [(0.40, t1_v15), (0.30, t2_v15), (0.30, t3_v15)]
        defaults["trail_atr_mult"] = 1.0
        defaults["giveback_kill"] = 0.35
        defaults["be_threshold_r"] = be_r

    else:
        # Fallback: v15 baseline
        defaults["tiers"] = [(0.40, t1_v15), (0.30, t2_v15), (0.30, t3_v15)]

    return defaults


ALL_EXIT_STRATEGIES = [
    "v15_baseline",
    "aggressive_runner",
    "conservative_runner",
    "heavy_runner",
    "two_tier",
    "four_tier",
    "atr_scaled_wide",
    "tight_targets",
    "dynamic_trail",
    "time_decay_trail",
    "vol_adaptive",
    "be_speed_0.5",
    "be_speed_0.8",
    "be_speed_1.0",
    "be_speed_1.2",
]


def test_all_strategies(
    paths: list[PricePath],
) -> dict[str, StrategyStats]:
    """Test all exit strategies against a list of PricePaths.

    Returns dict mapping strategy name to StrategyStats.
    """
    results: dict[str, StrategyStats] = {}
    for strat in ALL_EXIT_STRATEGIES:
        stats = StrategyStats(name=strat)
        for p in paths:
            result = _apply_exit_strategy(p, strat)
            stats.trades.append(result)
        results[strat] = stats
    return results


# ---------------------------------------------------------------------------
# 3. Giveback Analysis
# ---------------------------------------------------------------------------

GIVEBACK_THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


def analyze_giveback(
    paths: list[PricePath],
    regime_map: Optional[dict[int, str]] = None,
) -> dict[float, StrategyStats]:
    """Test different giveback kill thresholds.

    For each threshold, simulate the v15 baseline exit but with that
    giveback kill value. Returns dict mapping threshold -> StrategyStats.
    """
    results: dict[float, StrategyStats] = {}

    for threshold in GIVEBACK_THRESHOLDS:
        stats = StrategyStats(name=f"giveback_{threshold:.2f}")
        for p in paths:
            # Build a custom v15-like config but with the specific giveback
            atr = p.atr
            entry = p.entry_price
            d = p.direction

            def _target(mult: float) -> float:
                return (entry + mult * atr) if d == "LONG" else (entry - mult * atr)

            # Temporarily monkey-patch the strategy config
            original_fn = _get_strategy_config

            custom_config = {
                "tiers": [(0.40, _target(0.9)), (0.30, _target(1.6)), (0.30, _target(2.4))],
                "trail_atr_mult": 1.0,
                "giveback_kill": threshold,
                "max_hold": 60,
                "be_threshold_r": None,
                "dynamic_trail": False,
                "time_decay_trail": False,
                "vol_adaptive": False,
            }

            # Direct simulation with custom giveback
            result = _apply_exit_with_config(p, f"giveback_{threshold:.2f}", custom_config)
            stats.trades.append(result)

        results[threshold] = stats

    return results


def _apply_exit_with_config(path: PricePath, name: str, config: dict) -> ExitResult:
    """Apply exit logic with an explicit config dict (bypasses strategy lookup)."""
    entry = path.entry_price
    atr = path.atr
    r_trade = path.r_trade
    d = path.direction
    fwd = path.forward_bars

    if not fwd or r_trade <= 0 or atr <= 0:
        return ExitResult(name, d, entry, entry, 0.0, 0, "no_bars")

    tiers = config["tiers"]
    trail_atr_mult = config["trail_atr_mult"]
    giveback_kill = config["giveback_kill"]
    max_hold = config.get("max_hold", 60)

    stop = entry - r_trade if d == "LONG" else entry + r_trade
    remaining_pct = 1.0
    realized_r = 0.0
    tier_idx = 0
    peak_price = entry
    trailing_active = False
    trail_stop = stop
    bars_held = 0
    peak_r = 0.0

    for k, bar in enumerate(fwd):
        if k >= max_hold:
            exit_p = bar.close
            unrealized = path.signed_pnl(exit_p) / r_trade * remaining_pct
            realized_r += unrealized
            return ExitResult(name, d, entry, exit_p, realized_r, k, "time_stop",
                              peak_r, max(0, peak_r - realized_r))

        bars_held = k + 1

        # Stop check
        if d == "LONG" and bar.low <= stop:
            unrealized = (stop - entry) / r_trade * remaining_pct
            realized_r += unrealized
            return ExitResult(name, d, entry, stop, realized_r, bars_held, "stop_hit",
                              peak_r, max(0, peak_r - realized_r))
        if d == "SHORT" and bar.high >= stop:
            unrealized = (entry - stop) / r_trade * remaining_pct
            realized_r += unrealized
            return ExitResult(name, d, entry, stop, realized_r, bars_held, "stop_hit",
                              peak_r, max(0, peak_r - realized_r))

        # Peak tracking
        if d == "LONG":
            peak_price = max(peak_price, bar.high)
        else:
            peak_price = min(peak_price, bar.low)
        current_peak_r = abs(peak_price - entry) / r_trade
        peak_r = max(peak_r, current_peak_r)

        # Tier exits
        while tier_idx < len(tiers) and remaining_pct > 0:
            pct, target = tiers[tier_idx]
            hit = (d == "LONG" and bar.high >= target) or (d == "SHORT" and bar.low <= target)
            if hit:
                partial_r = path.signed_pnl(target) / r_trade * pct
                realized_r += partial_r
                remaining_pct -= pct
                tier_idx += 1
                if tier_idx == 1:
                    be_pad = 0.10 * atr
                    if d == "LONG":
                        stop = max(stop, entry + be_pad)
                    else:
                        stop = min(stop, entry - be_pad)
                elif tier_idx == 2 and len(tiers) >= 2:
                    t1_price = tiers[0][1]
                    if d == "LONG":
                        stop = max(stop, t1_price)
                    else:
                        stop = min(stop, t1_price)
                    trailing_active = True
                elif tier_idx >= 3:
                    trailing_active = True
            else:
                break

        if remaining_pct <= 0.001:
            return ExitResult(name, d, entry, tiers[-1][1] if tiers else entry,
                              realized_r, bars_held, "all_targets",
                              peak_r, max(0, peak_r - realized_r))

        # Trailing stop
        if trailing_active and remaining_pct > 0:
            if d == "LONG":
                new_trail = bar.close - trail_atr_mult * atr
                trail_stop = max(trail_stop, new_trail)
                stop = max(stop, trail_stop)
            else:
                new_trail = bar.close + trail_atr_mult * atr
                trail_stop = min(trail_stop, new_trail)
                stop = min(stop, trail_stop)

            # Giveback kill
            if giveback_kill > 0:
                gb = (peak_price - bar.close) if d == "LONG" else (bar.close - peak_price)
                if gb >= giveback_kill * atr:
                    exit_p = bar.close
                    unrealized = path.signed_pnl(exit_p) / r_trade * remaining_pct
                    realized_r += unrealized
                    return ExitResult(name, d, entry, exit_p, realized_r, bars_held,
                                      "giveback_kill", peak_r, max(0, peak_r - realized_r))

    if fwd:
        exit_p = fwd[-1].close
        unrealized = path.signed_pnl(exit_p) / r_trade * remaining_pct
        realized_r += unrealized
        return ExitResult(name, d, entry, exit_p, realized_r, len(fwd), "bars_exhausted",
                          peak_r, max(0, peak_r - realized_r))

    return ExitResult(name, d, entry, entry, 0.0, 0, "no_data")


# ---------------------------------------------------------------------------
# 3b. Giveback per regime
# ---------------------------------------------------------------------------

def analyze_giveback_by_regime(
    paths: list[PricePath],
    regime_labels: list[str],
) -> dict[str, dict[float, StrategyStats]]:
    """Giveback analysis broken out by regime."""
    regimes = sorted(set(regime_labels))
    result: dict[str, dict[float, StrategyStats]] = {}
    for regime in regimes:
        regime_paths = [p for p, r in zip(paths, regime_labels) if r == regime]
        if regime_paths:
            result[regime] = analyze_giveback(regime_paths)
    return result


# ---------------------------------------------------------------------------
# 4. Time Stop Analysis
# ---------------------------------------------------------------------------

TIME_STOP_PERIODS = [15, 20, 30, 40, 60, 90, 120]


def analyze_time_stops(
    paths: list[PricePath],
) -> dict[int, StrategyStats]:
    """Test different max hold periods.

    For each period, run the v15 baseline with that max hold.
    Also tracks what % of trades would have been winners if held longer.
    """
    results: dict[int, StrategyStats] = {}

    for period in TIME_STOP_PERIODS:
        stats = StrategyStats(name=f"time_stop_{period}")
        for p in paths:
            atr = p.atr
            entry = p.entry_price
            d = p.direction

            def _target(mult: float) -> float:
                return (entry + mult * atr) if d == "LONG" else (entry - mult * atr)

            config = {
                "tiers": [(0.40, _target(0.9)), (0.30, _target(1.6)), (0.30, _target(2.4))],
                "trail_atr_mult": 1.0,
                "giveback_kill": 0.35,
                "max_hold": period,
                "be_threshold_r": None,
                "dynamic_trail": False,
                "time_decay_trail": False,
                "vol_adaptive": False,
            }
            result = _apply_exit_with_config(p, f"time_stop_{period}", config)
            stats.trades.append(result)

        results[period] = stats

    return results


def compute_missed_opportunity(
    paths: list[PricePath], period: int,
) -> float:
    """Fraction of losers at `period` bars that would have become winners with 120 bars."""
    losers_at_period = 0
    would_win = 0

    for p in paths:
        atr = p.atr
        entry = p.entry_price
        d = p.direction

        def _target(mult: float) -> float:
            return (entry + mult * atr) if d == "LONG" else (entry - mult * atr)

        short_config = {
            "tiers": [(0.40, _target(0.9)), (0.30, _target(1.6)), (0.30, _target(2.4))],
            "trail_atr_mult": 1.0, "giveback_kill": 0.35, "max_hold": period,
            "be_threshold_r": None, "dynamic_trail": False,
            "time_decay_trail": False, "vol_adaptive": False,
        }
        long_config = dict(short_config)
        long_config["max_hold"] = 120

        r_short = _apply_exit_with_config(p, "short", short_config)
        r_long = _apply_exit_with_config(p, "long", long_config)

        if r_short.r_multiple <= 0:
            losers_at_period += 1
            if r_long.r_multiple > 0:
                would_win += 1

    return would_win / losers_at_period if losers_at_period > 0 else 0.0


# ---------------------------------------------------------------------------
# 6. Comprehensive Report
# ---------------------------------------------------------------------------

def print_exit_report(
    all_stats: dict[str, StrategyStats],
    giveback_stats: dict[float, StrategyStats],
    giveback_by_regime: dict[str, dict[float, StrategyStats]],
    time_stats: dict[int, StrategyStats],
    paths: list[PricePath],
    regime_labels: list[str],
) -> None:
    """Print the full exit strategy optimization report."""
    sep = "=" * 100
    thin = "-" * 100

    print()
    print(sep)
    print("  SATVA v15 EXIT STRATEGY OPTIMIZER — COMPREHENSIVE REPORT")
    print(sep)
    print()

    # ------------------------------------------------------------------
    # Side-by-side comparison
    # ------------------------------------------------------------------
    print("SECTION 1: EXIT STRATEGY COMPARISON (ALL SCENARIOS)")
    print(thin)
    header = f"{'Strategy':<22} {'Trades':>6} {'Win%':>7} {'AvgW_R':>8} {'AvgL_R':>8} {'Expect':>8} {'PF':>8} {'TotalR':>9} {'AvgBars':>8} {'Giveback':>9}"
    print(header)
    print(thin)

    ranked: list[tuple[str, StrategyStats]] = sorted(
        all_stats.items(), key=lambda x: x[1].expectancy, reverse=True,
    )
    for name, st in ranked:
        pf_str = f"{st.profit_factor:.2f}" if st.profit_factor < 1000 else "INF"
        print(
            f"{name:<22} {st.n:>6} {st.win_rate:>6.1f}% {st.avg_winner_r:>8.3f} "
            f"{st.avg_loser_r:>8.3f} {st.expectancy:>8.3f} {pf_str:>8} "
            f"{st.total_r:>9.2f} {st.avg_bars_held:>8.1f} {st.avg_giveback_r:>9.3f}"
        )

    best_name = ranked[0][0] if ranked else "N/A"
    best_exp = ranked[0][1].expectancy if ranked else 0.0
    print(thin)
    print(f"  >>> BEST OVERALL: {best_name} (expectancy = {best_exp:.4f}R)")
    print()

    # ------------------------------------------------------------------
    # Best strategy per regime
    # ------------------------------------------------------------------
    print("SECTION 2: BEST EXIT STRATEGY PER REGIME")
    print(thin)

    regimes = sorted(set(regime_labels))
    regime_path_map: dict[str, list[int]] = {r: [] for r in regimes}
    for idx, r in enumerate(regime_labels):
        regime_path_map[r].append(idx)

    for regime in regimes:
        indices = regime_path_map[regime]
        if not indices:
            continue
        print(f"\n  REGIME: {regime}  ({len(indices)} trades)")
        print(f"  {'Strategy':<22} {'Win%':>7} {'Expect':>8} {'PF':>8} {'TotalR':>9}")
        print(f"  {'-' * 60}")

        regime_rankings: list[tuple[str, float, float, float, float]] = []
        for strat_name, strat_stats in all_stats.items():
            regime_trades = [strat_stats.trades[i] for i in indices if i < len(strat_stats.trades)]
            if not regime_trades:
                continue
            n = len(regime_trades)
            wins = sum(1 for t in regime_trades if t.r_multiple > 0)
            wr = wins / n * 100 if n else 0
            exp = sum(t.r_multiple for t in regime_trades) / n if n else 0
            gw = sum(t.r_multiple for t in regime_trades if t.r_multiple > 0)
            gl = abs(sum(t.r_multiple for t in regime_trades if t.r_multiple <= 0))
            pf = gw / gl if gl > 0 else (float("inf") if gw > 0 else 0)
            total = sum(t.r_multiple for t in regime_trades)
            regime_rankings.append((strat_name, wr, exp, pf, total))

        regime_rankings.sort(key=lambda x: x[2], reverse=True)
        for rr in regime_rankings[:5]:
            pf_str = f"{rr[3]:.2f}" if rr[3] < 1000 else "INF"
            print(f"  {rr[0]:<22} {rr[1]:>6.1f}% {rr[2]:>8.3f} {pf_str:>8} {rr[4]:>9.2f}")

        if regime_rankings:
            print(f"  >>> BEST for {regime}: {regime_rankings[0][0]}")

    print()

    # ------------------------------------------------------------------
    # Giveback analysis
    # ------------------------------------------------------------------
    print("SECTION 3: GIVEBACK THRESHOLD ANALYSIS")
    print(thin)
    print(f"{'Threshold':>10} {'Win%':>7} {'Expect':>8} {'PF':>8} {'TotalR':>9} {'AvgGB_R':>9}")
    print(thin)

    best_gb = 0.35
    best_gb_exp = -999.0
    for threshold in GIVEBACK_THRESHOLDS:
        st = giveback_stats[threshold]
        pf_str = f"{st.profit_factor:.2f}" if st.profit_factor < 1000 else "INF"
        print(
            f"{threshold:>10.2f} {st.win_rate:>6.1f}% {st.expectancy:>8.3f} "
            f"{pf_str:>8} {st.total_r:>9.2f} {st.avg_giveback_r:>9.3f}"
        )
        if st.expectancy > best_gb_exp:
            best_gb_exp = st.expectancy
            best_gb = threshold

    print(thin)
    print(f"  >>> OPTIMAL GIVEBACK (all regimes): {best_gb:.2f}*ATR (expectancy = {best_gb_exp:.4f}R)")
    print()

    # Giveback per regime
    print("  OPTIMAL GIVEBACK PER REGIME:")
    for regime in sorted(giveback_by_regime.keys()):
        gb_data = giveback_by_regime[regime]
        best_t = 0.35
        best_e = -999.0
        for t, st in gb_data.items():
            if st.expectancy > best_e:
                best_e = st.expectancy
                best_t = t
        print(f"    {regime:<15} -> {best_t:.2f}*ATR  (expectancy = {best_e:.4f}R)")

    print()

    # ------------------------------------------------------------------
    # Time stop analysis
    # ------------------------------------------------------------------
    print("SECTION 4: TIME STOP ANALYSIS")
    print(thin)
    print(f"{'MaxHold':>8} {'Win%':>7} {'Expect':>8} {'PF':>8} {'TotalR':>9} {'AvgBars':>8} {'MissedOpp%':>11}")
    print(thin)

    best_ts = 60
    best_ts_exp = -999.0
    for period in TIME_STOP_PERIODS:
        st = time_stats[period]
        missed = compute_missed_opportunity(paths, period)
        pf_str = f"{st.profit_factor:.2f}" if st.profit_factor < 1000 else "INF"
        print(
            f"{period:>8} {st.win_rate:>6.1f}% {st.expectancy:>8.3f} "
            f"{pf_str:>8} {st.total_r:>9.2f} {st.avg_bars_held:>8.1f} {missed * 100:>10.1f}%"
        )
        if st.expectancy > best_ts_exp:
            best_ts_exp = st.expectancy
            best_ts = period

    print(thin)
    print(f"  >>> OPTIMAL MAX HOLD: {best_ts} bars (expectancy = {best_ts_exp:.4f}R)")
    print()

    # ------------------------------------------------------------------
    # Breakeven speed comparison
    # ------------------------------------------------------------------
    print("SECTION 5: BREAKEVEN SPEED ANALYSIS")
    print(thin)
    be_strategies = [s for s in ALL_EXIT_STRATEGIES if s.startswith("be_speed_")]
    print(f"{'BE at R':>10} {'Win%':>7} {'Expect':>8} {'PF':>8} {'TotalR':>9}")
    print(thin)
    best_be = "N/A"
    best_be_exp = -999.0
    for s in be_strategies:
        st = all_stats[s]
        pf_str = f"{st.profit_factor:.2f}" if st.profit_factor < 1000 else "INF"
        print(f"{s.replace('be_speed_', ''):>10}R {st.win_rate:>6.1f}% {st.expectancy:>8.3f} {pf_str:>8} {st.total_r:>9.2f}")
        if st.expectancy > best_be_exp:
            best_be_exp = st.expectancy
            best_be = s.replace("be_speed_", "")
    print(thin)
    print(f"  >>> OPTIMAL BE MOVE: {best_be}R profit (expectancy = {best_be_exp:.4f}R)")
    print()

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    print(sep)
    print("  RECOMMENDATIONS FOR SATVA v15 EXIT ENGINE")
    print(sep)
    print()

    # Find best overall strategy
    baseline_exp = all_stats["v15_baseline"].expectancy if "v15_baseline" in all_stats else 0
    improvements = []
    for name, st in ranked:
        if name == "v15_baseline":
            continue
        delta = st.expectancy - baseline_exp
        if delta > 0.001:
            improvements.append((name, delta, st.expectancy))

    if improvements:
        print("  STRATEGIES THAT OUTPERFORM v15 BASELINE:")
        for name, delta, exp in improvements[:5]:
            print(f"    {name:<22}  +{delta:.4f}R per trade (expectancy = {exp:.4f}R)")
    else:
        print("  v15 baseline is already optimal or near-optimal across all strategies tested.")

    print()
    print(f"  1. Overall best exit strategy: {best_name}")
    print(f"     vs baseline delta: {best_exp - baseline_exp:+.4f}R per trade")
    print()
    print(f"  2. Optimal giveback threshold: {best_gb:.2f}*ATR")
    print(f"     Current v15: 0.35*ATR (trend), 0.20*ATR (range)")
    print()
    print(f"  3. Optimal max hold period: {best_ts} bars")
    print(f"     Current v15: 120 bars (10 hours)")
    print()
    print(f"  4. Optimal breakeven move: at {best_be}R profit")
    print(f"     Current v15: at T1 hit (implicit via partial exit)")
    print()

    # Per-regime recommendations
    print("  5. PER-REGIME RECOMMENDATIONS:")
    for regime in regimes:
        indices = regime_path_map[regime]
        if not indices:
            continue
        best_r_strat = None
        best_r_exp = -999.0
        for strat_name, strat_stats in all_stats.items():
            regime_trades = [strat_stats.trades[i] for i in indices if i < len(strat_stats.trades)]
            if not regime_trades:
                continue
            exp = sum(t.r_multiple for t in regime_trades) / len(regime_trades)
            if exp > best_r_exp:
                best_r_exp = exp
                best_r_strat = strat_name
        gb_best = 0.35
        gb_best_exp = -999.0
        if regime in giveback_by_regime:
            gb_data = giveback_by_regime[regime]
            for t, st in gb_data.items():
                if st.expectancy > gb_best_exp:
                    gb_best_exp = st.expectancy
                    gb_best = t
        print(f"    {regime:<15} -> strategy={best_r_strat}, giveback={gb_best:.2f}*ATR")

    print()
    print(sep)
    print("  END OF REPORT")
    print(sep)
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_optimizer(n_bars: int = 200) -> None:
    """Run the full exit strategy optimization pipeline."""
    print("=" * 100)
    print("  SATVA v15 EXIT STRATEGY OPTIMIZER")
    print("  Generating scenarios and entry signals...")
    print("=" * 100)

    scenarios = generate_all_scenarios(n_bars)
    all_paths: list[PricePath] = []
    all_regime_labels: list[str] = []

    for sc in scenarios:
        regime = classify_regime(sc)
        entries = generate_entries(sc, min_entries=20, max_entries=50)
        print(f"  {sc.name:<22} regime={regime:<14} entries={len(entries)}")
        for e in entries:
            all_paths.append(e)
            all_regime_labels.append(regime)

    total_entries = len(all_paths)
    print(f"\n  Total entries generated: {total_entries}")
    if total_entries == 0:
        print("  ERROR: No entries generated. Cannot proceed.")
        return

    print(f"\n  Testing {len(ALL_EXIT_STRATEGIES)} exit strategies...")
    all_stats = test_all_strategies(all_paths)

    print("  Running giveback analysis...")
    giveback_stats = analyze_giveback(all_paths)
    giveback_by_regime = analyze_giveback_by_regime(all_paths, all_regime_labels)

    print("  Running time stop analysis...")
    time_stats = analyze_time_stops(all_paths)

    print("  Generating report...\n")
    print_exit_report(
        all_stats,
        giveback_stats,
        giveback_by_regime,
        time_stats,
        all_paths,
        all_regime_labels,
    )


if __name__ == "__main__":
    run_optimizer()
