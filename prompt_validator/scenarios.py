"""Deterministic market scenario generator.

Generates synthetic price data for backtesting trading models across
multiple market regimes. All data is reproducible via fixed seeds.

Scenarios:
  1. STRONG_UPTREND   — Steady climb with pullbacks
  2. STRONG_DOWNTREND  — Steady decline with bounces
  3. RANGE_BOUND       — Oscillating between support/resistance
  4. HIGH_VOLATILITY   — Wide swings, no clear direction
  5. LOW_VOLATILITY    — Tight compression, small moves
  6. TREND_REVERSAL    — Uptrend that reverses into downtrend
  7. V_RECOVERY        — Sharp drop followed by sharp recovery
  8. BREAKOUT          — Compression then explosive move
  9. CHOPPY            — Random noise, no structure
  10. FLASH_CRASH      — Sudden 10%+ drop, partial recovery
"""

import math
import random
from dataclasses import dataclass, field


@dataclass
class Bar:
    """Single OHLCV bar."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def tr(self) -> float:
        """True Range (standalone, no prior close needed)."""
        return self.high - self.low

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2.0

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open


@dataclass
class Scenario:
    """A named market scenario with generated bar data."""
    name: str
    description: str
    bars: list[Bar] = field(default_factory=list)
    expected_bias: str = "neutral"  # "bullish", "bearish", "neutral"
    volatility_regime: str = "normal"  # "low", "normal", "high", "extreme"


def _generate_bars(
    n: int,
    start_price: float,
    drift: float,
    volatility: float,
    seed: int,
    volume_base: int = 10000,
) -> list[Bar]:
    """Generate n OHLCV bars with given drift and volatility."""
    rng = random.Random(seed)
    bars = []
    price = start_price

    for i in range(n):
        # Price movement
        noise = rng.gauss(0, volatility)
        change = drift + noise
        new_price = price * (1 + change)

        # Build OHLC from price movement
        intra_vol = abs(change) + volatility * 0.5
        o = price
        c = new_price
        if c > o:
            h = c + abs(rng.gauss(0, price * intra_vol * 0.3))
            l = o - abs(rng.gauss(0, price * intra_vol * 0.2))
        else:
            h = o + abs(rng.gauss(0, price * intra_vol * 0.2))
            l = c - abs(rng.gauss(0, price * intra_vol * 0.3))

        # Ensure OHLC consistency
        h = max(h, o, c)
        l = min(l, o, c)
        l = max(l, 0.01)  # price floor

        vol = int(volume_base * (1 + abs(change) / volatility) * rng.uniform(0.5, 1.5))

        bars.append(Bar(timestamp=i, open=round(o, 2), high=round(h, 2),
                        low=round(l, 2), close=round(c, 2), volume=vol))
        price = new_price

    return bars


def generate_strong_uptrend(n: int = 200, seed: int = 1001) -> Scenario:
    bars = _generate_bars(n, 100.0, drift=0.003, volatility=0.008, seed=seed)
    return Scenario("STRONG_UPTREND", "Steady climb with pullbacks", bars, "bullish", "normal")


def generate_strong_downtrend(n: int = 200, seed: int = 2001) -> Scenario:
    bars = _generate_bars(n, 100.0, drift=-0.003, volatility=0.008, seed=seed)
    return Scenario("STRONG_DOWNTREND", "Steady decline with bounces", bars, "bearish", "normal")


def generate_range_bound(n: int = 200, seed: int = 3001) -> Scenario:
    """Oscillating between support and resistance."""
    rng = random.Random(seed)
    bars = []
    price = 100.0
    support, resistance = 95.0, 105.0

    for i in range(n):
        # Mean-revert within range
        mid = (support + resistance) / 2
        revert_force = -0.002 * (price - mid) / (resistance - support)
        noise = rng.gauss(0, 0.006)
        change = revert_force + noise
        new_price = price * (1 + change)
        new_price = max(support * 0.98, min(resistance * 1.02, new_price))

        o = price
        c = new_price
        h = max(o, c) + abs(rng.gauss(0, 0.3))
        l = min(o, c) - abs(rng.gauss(0, 0.3))
        l = max(l, 0.01)
        vol = int(10000 * rng.uniform(0.5, 1.5))
        bars.append(Bar(i, round(o, 2), round(h, 2), round(l, 2), round(c, 2), vol))
        price = new_price

    return Scenario("RANGE_BOUND", "Oscillating between support/resistance", bars, "neutral", "normal")


def generate_high_volatility(n: int = 200, seed: int = 4001) -> Scenario:
    bars = _generate_bars(n, 100.0, drift=0.0005, volatility=0.025, seed=seed)
    return Scenario("HIGH_VOLATILITY", "Wide swings, no clear direction", bars, "neutral", "high")


def generate_low_volatility(n: int = 200, seed: int = 5001) -> Scenario:
    bars = _generate_bars(n, 100.0, drift=0.0002, volatility=0.002, seed=seed)
    return Scenario("LOW_VOLATILITY", "Tight compression, small moves", bars, "neutral", "low")


def generate_trend_reversal(n: int = 200, seed: int = 6001) -> Scenario:
    """Uptrend first half, reversal second half."""
    half = n // 2
    bars1 = _generate_bars(half, 100.0, drift=0.004, volatility=0.008, seed=seed)
    last_price = bars1[-1].close
    bars2 = _generate_bars(n - half, last_price, drift=-0.005, volatility=0.010, seed=seed + 100)
    for i, b in enumerate(bars2):
        bars2[i] = Bar(half + b.timestamp, b.open, b.high, b.low, b.close, b.volume)
    return Scenario("TREND_REVERSAL", "Uptrend reverses into downtrend", bars1 + bars2, "neutral", "normal")


def generate_v_recovery(n: int = 200, seed: int = 7001) -> Scenario:
    """Sharp drop then sharp recovery."""
    third = n // 3
    bars1 = _generate_bars(third, 100.0, drift=-0.008, volatility=0.012, seed=seed)
    bottom = bars1[-1].close
    bars2 = _generate_bars(third, bottom, drift=-0.002, volatility=0.015, seed=seed + 50)
    bottom2 = bars2[-1].close
    bars3 = _generate_bars(n - 2 * third, bottom2, drift=0.010, volatility=0.012, seed=seed + 100)
    all_bars = bars1 + bars2 + bars3
    for i, b in enumerate(all_bars):
        all_bars[i] = Bar(i, b.open, b.high, b.low, b.close, b.volume)
    return Scenario("V_RECOVERY", "Sharp drop then sharp recovery", all_bars, "neutral", "extreme")


def generate_breakout(n: int = 200, seed: int = 8001) -> Scenario:
    """Tight range then explosive breakout."""
    compress = int(n * 0.6)
    bars1 = _generate_bars(compress, 100.0, drift=0.0001, volatility=0.002, seed=seed)
    last = bars1[-1].close
    bars2 = _generate_bars(n - compress, last, drift=0.006, volatility=0.015, seed=seed + 100)
    for i, b in enumerate(bars2):
        bars2[i] = Bar(compress + b.timestamp, b.open, b.high, b.low, b.close, b.volume)
    return Scenario("BREAKOUT", "Compression then explosive move", bars1 + bars2, "bullish", "normal")


def generate_choppy(n: int = 200, seed: int = 9001) -> Scenario:
    bars = _generate_bars(n, 100.0, drift=0.0, volatility=0.012, seed=seed)
    return Scenario("CHOPPY", "Random noise, no structure", bars, "neutral", "normal")


def generate_flash_crash(n: int = 200, seed: int = 10001) -> Scenario:
    """Normal then sudden 12% drop, partial recovery."""
    pre = int(n * 0.5)
    bars1 = _generate_bars(pre, 100.0, drift=0.001, volatility=0.005, seed=seed)
    last = bars1[-1].close
    # Crash: 15 bars of severe decline
    crash_bars = _generate_bars(15, last, drift=-0.015, volatility=0.020, seed=seed + 50)
    crash_bottom = crash_bars[-1].close
    # Partial recovery
    remain = n - pre - 15
    bars3 = _generate_bars(remain, crash_bottom, drift=0.004, volatility=0.012, seed=seed + 100)
    all_bars = bars1 + crash_bars + bars3
    for i, b in enumerate(all_bars):
        all_bars[i] = Bar(i, b.open, b.high, b.low, b.close, b.volume)
    return Scenario("FLASH_CRASH", "Sudden drop, partial recovery", all_bars, "bearish", "extreme")


ALL_SCENARIOS = [
    generate_strong_uptrend,
    generate_strong_downtrend,
    generate_range_bound,
    generate_high_volatility,
    generate_low_volatility,
    generate_trend_reversal,
    generate_v_recovery,
    generate_breakout,
    generate_choppy,
    generate_flash_crash,
]


def generate_all_scenarios(n: int = 200) -> list[Scenario]:
    """Generate all 10 market scenarios."""
    return [gen(n) for gen in ALL_SCENARIOS]
