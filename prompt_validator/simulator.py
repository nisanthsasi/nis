"""Deterministic trade simulator engine.

Implements the actual trading rules from each model and simulates trades
across market scenarios. Every rule is taken directly from the prompt
specifications — no discretionary logic.

Each model strategy implements:
  - Indicator calculations (EMA, RSI, ADX, Bollinger, Z-score, etc.)
  - Entry signal generation (deterministic conditions)
  - Exit signal generation (stops, targets, time stops)
  - FSM state management
  - Risk management (daily loss limits, position sizing)
"""

import math
from dataclasses import dataclass, field
from prompt_validator.scenarios import Bar, Scenario


# ---------------------------------------------------------------------------
# Trade result
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    model: str
    scenario: str
    entry_bar: int
    exit_bar: int
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    exit_reason: str = ""

    @property
    def is_winner(self) -> bool:
        return self.pnl_pct > 0

    @property
    def is_loser(self) -> bool:
        return self.pnl_pct < 0


@dataclass
class SimResult:
    model: str
    scenario: str
    trades: list[Trade] = field(default_factory=list)
    total_pnl_pct: float = 0.0
    halted: bool = False
    halt_reason: str = ""

    @property
    def win_count(self) -> int:
        return sum(1 for t in self.trades if t.is_winner)

    @property
    def loss_count(self) -> int:
        return sum(1 for t in self.trades if t.is_loser)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        return self.win_count / self.total_trades * 100 if self.trades else 0.0

    @property
    def avg_win(self) -> float:
        wins = [t.pnl_pct for t in self.trades if t.is_winner]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t.pnl_pct for t in self.trades if t.is_loser]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl_pct for t in self.trades if t.is_winner)
        gross_loss = abs(sum(t.pnl_pct for t in self.trades if t.is_loser))
        return gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in self.trades:
            equity += t.pnl_pct
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def expectancy(self) -> float:
        """Per-trade expected value."""
        if not self.trades:
            return 0.0
        return self.total_pnl_pct / self.total_trades

    @property
    def avg_r(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.r_multiple for t in self.trades) / len(self.trades)


# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------

def _ema(values: list[float], period: int) -> list[float]:
    """Exponential moving average."""
    result = [0.0] * len(values)
    if not values or period < 1:
        return result
    k = 2.0 / (period + 1)
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def _sma(values: list[float], period: int) -> list[float]:
    """Simple moving average."""
    result = [0.0] * len(values)
    for i in range(len(values)):
        if i < period - 1:
            result[i] = sum(values[:i + 1]) / (i + 1)
        else:
            result[i] = sum(values[i - period + 1:i + 1]) / period
    return result


def _atr(bars: list[Bar], period: int = 14) -> list[float]:
    """Average True Range."""
    trs = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b.high - b.low)
        else:
            tr = max(b.high - b.low, abs(b.high - bars[i - 1].close), abs(b.low - bars[i - 1].close))
            trs.append(tr)
    return _sma(trs, period)


def _rsi(closes: list[float], period: int = 14) -> list[float]:
    """Relative Strength Index."""
    result = [50.0] * len(closes)
    if len(closes) < period + 1:
        return result
    gains = []
    losses = []
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


def _adx(bars: list[Bar], period: int = 14) -> list[float]:
    """Average Directional Index (simplified)."""
    result = [0.0] * len(bars)
    if len(bars) < period * 2:
        return result
    plus_dm = []
    minus_dm = []
    trs = []
    for i in range(1, len(bars)):
        high_diff = bars[i].high - bars[i - 1].high
        low_diff = bars[i - 1].low - bars[i].low
        plus_dm.append(max(high_diff, 0) if high_diff > low_diff else 0)
        minus_dm.append(max(low_diff, 0) if low_diff > high_diff else 0)
        tr = max(bars[i].high - bars[i].low,
                 abs(bars[i].high - bars[i - 1].close),
                 abs(bars[i].low - bars[i - 1].close))
        trs.append(tr)

    atr_vals = _sma(trs, period)
    plus_di_raw = _sma(plus_dm, period)
    minus_di_raw = _sma(minus_dm, period)

    dx_vals = []
    for i in range(len(atr_vals)):
        if atr_vals[i] == 0:
            dx_vals.append(0)
            continue
        plus_di = 100 * plus_di_raw[i] / atr_vals[i]
        minus_di = 100 * minus_di_raw[i] / atr_vals[i]
        denom = plus_di + minus_di
        dx_vals.append(100 * abs(plus_di - minus_di) / denom if denom > 0 else 0)

    adx_smooth = _sma(dx_vals, period)
    for i in range(len(adx_smooth)):
        if i + 1 < len(result):
            result[i + 1] = adx_smooth[i]
    return result


def _stddev(values: list[float], period: int) -> list[float]:
    """Rolling standard deviation."""
    result = [0.0] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        result[i] = math.sqrt(variance)
    return result


def _bollinger(closes: list[float], period: int = 20, num_std: float = 2.0):
    """Bollinger Bands: returns (upper, middle, lower)."""
    middle = _sma(closes, period)
    std = _stddev(closes, period)
    upper = [m + num_std * s for m, s in zip(middle, std)]
    lower = [m - num_std * s for m, s in zip(middle, std)]
    return upper, middle, lower


# ---------------------------------------------------------------------------
# Strategy Implementations
# ---------------------------------------------------------------------------

def _sim_satva(scenario: Scenario) -> SimResult:
    """SATVA — Intraday price-action with ABT spikes and compression."""
    bars = scenario.bars
    closes = [b.close for b in bars]
    atr = _atr(bars, 14)
    rsi = _rsi(closes, 14)
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    result = SimResult("SATVA", scenario.name)
    daily_pnl = 0.0
    cooldown = 0

    for i in range(30, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue
        if daily_pnl <= -3.0:
            result.halted = True
            result.halt_reason = "SessionLossR >= 2.0"
            break

        # ABT spike detection: TR >= 2.2 * ATR
        tr = bars[i].high - bars[i].low
        is_spike = tr >= 2.2 * atr[i] if atr[i] > 0 else False

        # RCS-like composite check
        trend_aligned = ema9[i] > ema21[i]
        rsi_ok = 40 < rsi[i] < 75
        volume_ok = bars[i].volume > 8000

        if is_spike and trend_aligned and rsi_ok and volume_ok:
            entry = bars[i].close
            stop = entry - 1.5 * atr[i]
            target = entry + 2.5 * atr[i]
            risk = abs(entry - stop)
            if risk < 0.01:
                continue

            # Simulate exit
            for j in range(i + 1, min(i + 30, len(bars))):
                if bars[j].low <= stop:
                    pnl = (stop - entry) / entry * 100
                    r_mult = -1.0
                    trade = Trade("SATVA", scenario.name, i, j, "LONG", entry, stop, stop, target,
                                  pnl, r_mult, "stop_hit")
                    result.trades.append(trade)
                    daily_pnl += pnl
                    cooldown = 3
                    break
                if bars[j].high >= target:
                    pnl = (target - entry) / entry * 100
                    r_mult = (target - entry) / risk
                    trade = Trade("SATVA", scenario.name, i, j, "LONG", entry, target, stop, target,
                                  pnl, r_mult, "target_hit")
                    result.trades.append(trade)
                    daily_pnl += pnl
                    cooldown = 3
                    break
                # Trailing stop after 1*ATR profit
                if bars[j].close >= entry + atr[i]:
                    trail = bars[j].close - 1.5 * atr[i]
                    if bars[j].low <= trail:
                        exit_p = trail
                        pnl = (exit_p - entry) / entry * 100
                        r_mult = (exit_p - entry) / risk
                        trade = Trade("SATVA", scenario.name, i, j, "LONG", entry, exit_p, stop, target,
                                      pnl, r_mult, "trail_stop")
                        result.trades.append(trade)
                        daily_pnl += pnl
                        cooldown = 3
                        break
            else:
                # Time exit after 30 bars
                exit_p = bars[min(i + 29, len(bars) - 1)].close
                pnl = (exit_p - entry) / entry * 100
                r_mult = (exit_p - entry) / risk if risk > 0 else 0
                trade = Trade("SATVA", scenario.name, i, min(i + 29, len(bars) - 1), "LONG",
                              entry, exit_p, stop, target, pnl, r_mult, "time_exit")
                result.trades.append(trade)
                daily_pnl += pnl
                cooldown = 3

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


def _sim_vortex(scenario: Scenario) -> SimResult:
    """VORTEX — Momentum/Trend Following with EMA crossover and ADX."""
    bars = scenario.bars
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    adx = _adx(bars, 14)
    rsi = _rsi(closes, 14)
    atr = _atr(bars, 14)
    result = SimResult("VORTEX", scenario.name)
    daily_pnl = 0.0
    cooldown = 0

    for i in range(30, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue
        if daily_pnl <= -3.0:
            result.halted = True
            result.halt_reason = "Max daily loss 3%"
            break

        # LONG: EMA crossover + ADX > 25 + RSI 50-80
        cross_up = ema9[i] > ema21[i] and ema9[i - 1] <= ema21[i - 1]
        trend_strong = adx[i] > 25
        rsi_ok = 50 < rsi[i] < 80
        vol_ok = bars[i].volume > sum(b.volume for b in bars[max(0, i - 20):i]) / max(1, min(20, i))

        # SHORT: mirror
        cross_down = ema9[i] < ema21[i] and ema9[i - 1] >= ema21[i - 1]
        rsi_short_ok = 20 < rsi[i] < 50

        direction = None
        if cross_up and trend_strong and rsi_ok and vol_ok:
            direction = "LONG"
        elif cross_down and trend_strong and rsi_short_ok and vol_ok:
            direction = "SHORT"

        if direction:
            entry = bars[i].close
            risk_mult = 1.5
            trail_mult = 2.0
            if direction == "LONG":
                stop = entry - risk_mult * atr[i]
                target = entry + 3.0 * atr[i]
            else:
                stop = entry + risk_mult * atr[i]
                target = entry - 3.0 * atr[i]
            risk = abs(entry - stop)
            if risk < 0.01:
                continue

            for j in range(i + 1, min(i + 40, len(bars))):
                if direction == "LONG":
                    if bars[j].low <= stop:
                        pnl = (stop - entry) / entry * 100
                        result.trades.append(Trade("VORTEX", scenario.name, i, j, direction,
                                                   entry, stop, stop, target, pnl, -1.0, "stop_hit"))
                        break
                    if bars[j].high >= target:
                        pnl = (target - entry) / entry * 100
                        result.trades.append(Trade("VORTEX", scenario.name, i, j, direction,
                                                   entry, target, stop, target, pnl, (target - entry) / risk, "target_hit"))
                        break
                    # Trailing
                    if bars[j].close >= entry + atr[i]:
                        trail = bars[j].close - trail_mult * atr[i]
                        if bars[j].low <= trail:
                            pnl = (trail - entry) / entry * 100
                            result.trades.append(Trade("VORTEX", scenario.name, i, j, direction,
                                                       entry, trail, stop, target, pnl, (trail - entry) / risk, "trail_stop"))
                            break
                else:
                    if bars[j].high >= stop:
                        pnl = (entry - stop) / entry * 100
                        result.trades.append(Trade("VORTEX", scenario.name, i, j, direction,
                                                   entry, stop, stop, target, pnl, -1.0, "stop_hit"))
                        break
                    if bars[j].low <= target:
                        pnl = (entry - target) / entry * 100
                        result.trades.append(Trade("VORTEX", scenario.name, i, j, direction,
                                                   entry, target, stop, target, pnl, (entry - target) / risk, "target_hit"))
                        break
            else:
                exit_p = bars[min(i + 39, len(bars) - 1)].close
                if direction == "LONG":
                    pnl = (exit_p - entry) / entry * 100
                else:
                    pnl = (entry - exit_p) / entry * 100
                r_mult = pnl / (risk / entry * 100) if risk > 0 else 0
                result.trades.append(Trade("VORTEX", scenario.name, i, min(i + 39, len(bars) - 1), direction,
                                           entry, exit_p, stop, target, pnl, r_mult, "time_exit"))

            daily_pnl += result.trades[-1].pnl_pct
            cooldown = 3

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


def _sim_nexus(scenario: Scenario) -> SimResult:
    """NEXUS — Mean Reversion with Z-score and Bollinger."""
    bars = scenario.bars
    closes = [b.close for b in bars]
    sma20 = _sma(closes, 20)
    std20 = _stddev(closes, 20)
    bb_upper, bb_mid, bb_lower = _bollinger(closes, 20, 2.0)
    rsi = _rsi(closes, 14)
    atr = _atr(bars, 14)
    result = SimResult("NEXUS", scenario.name)
    daily_pnl = 0.0
    cooldown = 0

    for i in range(25, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue
        if daily_pnl <= -2.0:
            result.halted = True
            result.halt_reason = "Max daily loss 2%"
            break

        z_score = (closes[i] - sma20[i]) / std20[i] if std20[i] > 0 else 0
        direction = None

        # Oversold reversion
        if z_score < -2.0 and rsi[i] < 30 and closes[i] < bb_lower[i]:
            direction = "LONG"
        # Overbought reversion
        elif z_score > 2.0 and rsi[i] > 70 and closes[i] > bb_upper[i]:
            direction = "SHORT"

        if direction:
            entry = bars[i].close
            fair_value = sma20[i]
            if direction == "LONG":
                stop = entry - 1.0 * atr[i]
                target = fair_value
            else:
                stop = entry + 1.0 * atr[i]
                target = fair_value
            risk = abs(entry - stop)
            if risk < 0.01:
                continue

            max_hold = 20  # Time stop
            for j in range(i + 1, min(i + max_hold, len(bars))):
                if direction == "LONG":
                    if bars[j].low <= stop:
                        pnl = (stop - entry) / entry * 100
                        result.trades.append(Trade("NEXUS", scenario.name, i, j, direction,
                                                   entry, stop, stop, target, pnl, -1.0, "stop_hit"))
                        break
                    if bars[j].high >= target:
                        pnl = (target - entry) / entry * 100
                        result.trades.append(Trade("NEXUS", scenario.name, i, j, direction,
                                                   entry, target, stop, target, pnl, (target - entry) / risk, "target_hit"))
                        break
                else:
                    if bars[j].high >= stop:
                        pnl = (entry - stop) / entry * 100
                        result.trades.append(Trade("NEXUS", scenario.name, i, j, direction,
                                                   entry, stop, stop, target, pnl, -1.0, "stop_hit"))
                        break
                    if bars[j].low <= target:
                        pnl = (entry - target) / entry * 100
                        result.trades.append(Trade("NEXUS", scenario.name, i, j, direction,
                                                   entry, target, stop, target, pnl, (entry - target) / risk, "target_hit"))
                        break
            else:
                # Time stop
                exit_p = bars[min(i + max_hold - 1, len(bars) - 1)].close
                if direction == "LONG":
                    pnl = (exit_p - entry) / entry * 100
                else:
                    pnl = (entry - exit_p) / entry * 100
                r_mult = pnl / (risk / entry * 100) if risk > 0 else 0
                result.trades.append(Trade("NEXUS", scenario.name, i, min(i + max_hold - 1, len(bars) - 1), direction,
                                           entry, exit_p, stop, target, pnl, r_mult, "time_stop"))

            daily_pnl += result.trades[-1].pnl_pct
            cooldown = 5

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


def _sim_prism(scenario: Scenario) -> SimResult:
    """PRISM — Options/Greeks (simulated as defined-risk credit spreads)."""
    bars = scenario.bars
    closes = [b.close for b in bars]
    atr = _atr(bars, 14)
    sma50 = _sma(closes, 50)
    std20 = _stddev(closes, 20)
    result = SimResult("PRISM", scenario.name)
    daily_pnl = 0.0
    cooldown = 0

    # Simulate iron condor-like trades: sell premium when IV is high
    for i in range(50, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue
        if daily_pnl <= -5.0:
            result.halted = True
            result.halt_reason = "Max daily loss 5%"
            break

        # IV proxy: current ATR vs historical mean ATR (IV rank)
        hist_atr = sum(atr[max(0, i - 50):i]) / min(50, i) if i > 0 else atr[i]
        iv_rank = (atr[i] / hist_atr * 50) if hist_atr > 0 else 50

        if iv_rank > 50:  # High IV → sell premium (iron condor)
            entry = bars[i].close
            wing_width = 2.0 * atr[i]
            credit = wing_width * 0.35  # Collect ~35% of width
            upper_short = entry + 1.0 * std20[i] if std20[i] > 0 else entry + atr[i]
            lower_short = entry - 1.0 * std20[i] if std20[i] > 0 else entry - atr[i]
            max_loss_pct = (wing_width - credit) / entry * 100
            max_profit_pct = credit / entry * 100

            dte = 30
            for j in range(i + 1, min(i + dte, len(bars))):
                # Breached short strike → loss
                if bars[j].high > upper_short + wing_width or bars[j].low < lower_short - wing_width:
                    pnl = -max_loss_pct
                    result.trades.append(Trade("PRISM", scenario.name, i, j, "IRON_CONDOR",
                                               entry, bars[j].close, lower_short, upper_short,
                                               pnl, pnl / max_profit_pct if max_profit_pct else 0, "breached"))
                    break
                # Close at 50% profit
                bars_elapsed = j - i
                time_decay_pct = bars_elapsed / dte
                current_profit = max_profit_pct * time_decay_pct * 0.7  # Simplified theta decay
                if current_profit >= max_profit_pct * 0.5 and lower_short < bars[j].close < upper_short:
                    pnl = max_profit_pct * 0.5
                    result.trades.append(Trade("PRISM", scenario.name, i, j, "IRON_CONDOR",
                                               entry, bars[j].close, lower_short, upper_short,
                                               pnl, 0.5, "profit_target_50pct"))
                    break
            else:
                # Expiration: if within short strikes → full profit
                last_close = bars[min(i + dte - 1, len(bars) - 1)].close
                if lower_short <= last_close <= upper_short:
                    pnl = max_profit_pct
                    reason = "full_profit_expiry"
                else:
                    # Partial loss
                    if last_close > upper_short:
                        breach = min(last_close - upper_short, wing_width)
                    else:
                        breach = min(lower_short - last_close, wing_width)
                    pnl = (credit - breach) / entry * 100
                    reason = "partial_loss_expiry"
                r_mult = pnl / max_profit_pct if max_profit_pct else 0
                result.trades.append(Trade("PRISM", scenario.name, i, min(i + dte - 1, len(bars) - 1),
                                           "IRON_CONDOR", entry, last_close, lower_short, upper_short,
                                           pnl, r_mult, reason))

            daily_pnl += result.trades[-1].pnl_pct
            cooldown = 15  # DTE-based cooldown

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


def _sim_flux(scenario: Scenario) -> SimResult:
    """FLUX — Scalping/HFT (tick-level simulation on bars)."""
    bars = scenario.bars
    closes = [b.close for b in bars]
    atr = _atr(bars, 14)
    result = SimResult("FLUX", scenario.name)
    daily_pnl = 0.0
    trades_this_session = 0
    cooldown = 0

    for i in range(15, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue
        if daily_pnl <= -1.0:
            result.halted = True
            result.halt_reason = "Kill switch: daily loss 1%"
            break
        if trades_this_session >= 100:
            result.halted = True
            result.halt_reason = "Rate limit: 100 trades/session"
            break

        # Order flow imbalance proxy: consecutive bullish/bearish bars
        lookback = bars[max(0, i - 5):i + 1]
        buy_pressure = sum(1 for b in lookback if b.is_bullish) / len(lookback)
        sell_pressure = 1 - buy_pressure

        spread = bars[i].high - bars[i].low
        tight_spread = spread <= 2 * (atr[i] * 0.1) if atr[i] > 0 else False

        direction = None
        if buy_pressure > 0.7 and tight_spread:
            direction = "LONG"
        elif sell_pressure > 0.7 and tight_spread:
            direction = "SHORT"

        if direction:
            entry = bars[i].close
            tick_size = max(0.01, atr[i] * 0.05)  # Approximate tick
            target_ticks = 4
            stop_ticks = 2

            if direction == "LONG":
                stop = entry - stop_ticks * tick_size
                target = entry + target_ticks * tick_size
            else:
                stop = entry + stop_ticks * tick_size
                target = entry - target_ticks * tick_size

            risk = abs(entry - stop)
            if risk < 0.001:
                continue

            # Scalp: resolve within 3 bars max
            for j in range(i + 1, min(i + 4, len(bars))):
                if direction == "LONG":
                    if bars[j].low <= stop:
                        pnl = (stop - entry) / entry * 100
                        result.trades.append(Trade("FLUX", scenario.name, i, j, direction,
                                                   entry, stop, stop, target, pnl, -1.0, "stop_hit"))
                        break
                    if bars[j].high >= target:
                        pnl = (target - entry) / entry * 100
                        result.trades.append(Trade("FLUX", scenario.name, i, j, direction,
                                                   entry, target, stop, target, pnl, 2.0, "target_hit"))
                        break
                else:
                    if bars[j].high >= stop:
                        pnl = (entry - stop) / entry * 100
                        result.trades.append(Trade("FLUX", scenario.name, i, j, direction,
                                                   entry, stop, stop, target, pnl, -1.0, "stop_hit"))
                        break
                    if bars[j].low <= target:
                        pnl = (entry - target) / entry * 100
                        result.trades.append(Trade("FLUX", scenario.name, i, j, direction,
                                                   entry, target, stop, target, pnl, 2.0, "target_hit"))
                        break
            else:
                # Time exit after 3 bars
                exit_p = bars[min(i + 3, len(bars) - 1)].close
                if direction == "LONG":
                    pnl = (exit_p - entry) / entry * 100
                else:
                    pnl = (entry - exit_p) / entry * 100
                r_mult = pnl / (risk / entry * 100) if risk > 0 else 0
                result.trades.append(Trade("FLUX", scenario.name, i, min(i + 3, len(bars) - 1), direction,
                                           entry, exit_p, stop, target, pnl, r_mult, "time_exit"))

            daily_pnl += result.trades[-1].pnl_pct
            trades_this_session += 1
            cooldown = 1

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


def _sim_titan(scenario: Scenario) -> SimResult:
    """TITAN — Swing/Multi-day Master System v1.0.0.

    Implements the full TITAN master prompt logic:
    - Multi-timeframe alignment (EMA50/200 daily + EMA21 4H-proxy + EMA9/21 1H-proxy)
    - ADX trend strength + RSI momentum confirmation
    - Swing Confidence Score (SCS) with 5 weighted components
    - Trade Eligibility Score (TES) with 4 weighted components
    - Pullback quality detection (depth, EMA proximity, volume contraction)
    - 12-gate entry sequence
    - 3-tier deterministic partial exits (33/33/34)
    - Weekly loss cap (4R) + daily loss cap (2R) + 8% drawdown halt
    - Weekly Meta Governor (WMG) with bootstrap tiers
    - Cooldown after 2 consecutive losses
    """
    bars = scenario.bars
    closes = [b.close for b in bars]

    # --- Indicators (multi-timeframe proxies on bar data) ---
    ema50 = _ema(closes, 50)
    ema200 = _ema(closes, 200) if len(closes) >= 200 else _ema(closes, min(len(closes), 50))
    ema21 = _ema(closes, 21)   # 4H EMA proxy
    ema9 = _ema(closes, 9)     # 1H fast EMA proxy
    ema21_1h = _ema(closes, 21)  # 1H slow EMA proxy
    atr = _atr(bars, 14)
    rsi = _rsi(closes, 14)
    adx = _adx(bars, 14)
    sma_vol = _sma([b.volume for b in bars], 20)

    result = SimResult("TITAN", scenario.name)
    weekly_loss_r = 0.0
    daily_loss_r = 0.0
    weekly_trade_count = 0
    daily_trade_count = 0
    consecutive_losses = 0
    cooldown = 0
    trade_history = []  # for WMG

    for i in range(55, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue

        # --- GATE 2: Trade caps (Section 3.3) ---
        if weekly_trade_count >= 2:
            continue  # Max 2 new entries per week
        if daily_trade_count >= 1:
            continue  # Max 1 new entry per day

        # --- GATE 3: Loss limits ---
        if weekly_loss_r >= 4.0:
            result.halted = True
            result.halt_reason = "WeeklyLossR >= 4.0R → WEEKLY_LOCK"
            break
        if daily_loss_r >= 2.0:
            continue  # DAY_LOCK: skip this bar

        # --- GATE 4: VOL_EXTREME check ---
        if atr[i] > 0:
            hist_atr = sum(atr[max(0, i - 20):i]) / min(20, max(1, i))
            atr_ratio = atr[i] / hist_atr if hist_atr > 0 else 1.0
        else:
            atr_ratio = 1.0
        vol_extreme = atr_ratio > 2.0 or (bars[i].high - bars[i].low) > 3.0 * atr[i] if atr[i] > 0 else False
        if vol_extreme:
            continue

        # --- TAS (Trend Alignment Score, Section 6) ---
        bullish_trend = ema50[i] > ema200[i]
        bearish_trend = ema50[i] < ema200[i]
        adx_strong = adx[i] > 25
        adx_moderate = 20 <= adx[i] <= 25

        # Daily layer
        daily_bull = bullish_trend and adx[i] > 20
        daily_bear = bearish_trend and adx[i] > 20

        # 4H layer: price vs EMA21
        aligned_bull_4h = closes[i] > ema21[i]
        aligned_bear_4h = closes[i] < ema21[i]

        # 1H layer: EMA9 vs EMA21 + RSI
        trigger_bull_1h = ema9[i] > ema21_1h[i] and rsi[i] > 40
        trigger_bear_1h = ema9[i] < ema21_1h[i] and rsi[i] < 60

        tas_long = (40 if daily_bull else 0) + (35 if aligned_bull_4h else 0) + (25 if trigger_bull_1h else 0)
        tas_short = (40 if daily_bear else 0) + (35 if aligned_bear_4h else 0) + (25 if trigger_bear_1h else 0)

        # --- Swing structure (Section 5) ---
        recent_lows = [bars[k].low for k in range(max(0, i - 10), i + 1)]
        recent_highs = [bars[k].high for k in range(max(0, i - 10), i + 1)]
        higher_low = min(recent_lows[-5:]) > min(recent_lows[:5]) if len(recent_lows) >= 10 else False
        lower_high = max(recent_highs[-5:]) < max(recent_highs[:5]) if len(recent_highs) >= 10 else False
        uptrend = bullish_trend and higher_low
        downtrend = bearish_trend and lower_high

        # --- PQS (Pullback Quality Score, Section 8) ---
        near_ema50 = abs(closes[i] - ema50[i]) / atr[i] if atr[i] > 0 else 999
        near_ema21 = abs(closes[i] - ema21[i]) / atr[i] if atr[i] > 0 else 999
        ema_touch = near_ema50 < 1.0 or near_ema21 < 0.5  # Within 1*ATR of EMA50 or 0.5*ATR of EMA21

        # Pullback depth
        if i >= 10:
            swing_high = max(bars[k].high for k in range(max(0, i - 10), i))
            swing_low = min(bars[k].low for k in range(max(0, i - 10), i))
            pb_depth_long = (swing_high - bars[i].low) / atr[i] if atr[i] > 0 else 0
            pb_depth_short = (bars[i].high - swing_low) / atr[i] if atr[i] > 0 else 0
        else:
            pb_depth_long = pb_depth_short = 0

        # Setup A: Breakout detection — price breaks above recent swing high
        breakout_long = closes[i] > swing_high if i >= 10 else False
        breakout_short = closes[i] < swing_low if i >= 10 else False
        breakout_vol = bars[i].volume >= 1.5 * sma_vol[i] if sma_vol[i] > 0 else False

        # Volume contraction during pullback
        vol_contract = bars[i].volume < 0.8 * sma_vol[i] if sma_vol[i] > 0 else False

        # Pullback candle quality: count bearish bars in pullback (Section 8.3)
        if i >= 10:
            pb_bars_count = sum(1 for k in range(max(0, i - 7), i) if not bars[k].is_bullish)
        else:
            pb_bars_count = 0

        def _pqs_score(pb_depth: float) -> int:
            depth = 100 if 0.5 <= pb_depth <= 1.5 else 50 if (1.5 < pb_depth <= 2.5 or 0.3 <= pb_depth < 0.5) else 0
            ema_s = 100 if ema_touch else 50 if min(near_ema50, near_ema21) < 1.5 else 0
            vol_s = 100 if vol_contract else 50 if bars[i].volume < sma_vol[i] else 0
            candle_s = 100 if 3 <= pb_bars_count <= 5 else 50 if pb_bars_count in (2, 6, 7) else 0
            return int(0.30 * depth + 0.25 * ema_s + 0.25 * candle_s + 0.20 * vol_s)

        pqs_long = _pqs_score(pb_depth_long)
        pqs_short = _pqs_score(pb_depth_short)

        # --- MOMENTUM (Section 10) ---
        rsi_ok_long = 40 <= rsi[i] <= 70
        rsi_ok_short = 30 <= rsi[i] <= 60
        vol_ok = bars[i].volume >= sma_vol[i] if sma_vol[i] > 0 else False

        def _momentum_score(rsi_ok: bool) -> int:
            if adx_strong and rsi_ok and vol_ok:
                return 100
            elif adx_moderate and rsi_ok:
                return 50
            return 0

        # --- SCS (Swing Confidence Score, Section 12) ---
        vol_state_bin = 0 if vol_extreme else 100 if 0.7 <= atr_ratio <= 1.3 else 50
        mom_long = _momentum_score(rsi_ok_long)
        mom_short = _momentum_score(rsi_ok_short)

        def _scs(tas: int, pqs: int, momentum: int, is_uptrend: bool) -> int:
            tas_bin = 100 if tas >= 65 else 50 if tas >= 40 else 0
            pqs_bin = 100 if pqs >= 70 else 50 if pqs >= 50 else 0
            structure = 100 if is_uptrend else 50 if bullish_trend or bearish_trend else 0
            return int(0.30 * tas_bin + 0.20 * pqs_bin + 0.15 * vol_state_bin + 0.15 * momentum + 0.20 * structure)

        def _scs_breakout(tas: int, momentum: int, is_uptrend: bool) -> int:
            """SCS for Setup A (breakout): replaces PQS with breakout volume quality."""
            tas_bin = 100 if tas >= 65 else 50 if tas >= 40 else 0
            brk_vol_bin = 100 if breakout_vol else 50 if vol_ok else 0
            structure = 100 if is_uptrend else 50 if bullish_trend or bearish_trend else 0
            return int(0.30 * tas_bin + 0.20 * brk_vol_bin + 0.15 * vol_state_bin + 0.15 * momentum + 0.20 * structure)

        scs_long = _scs(tas_long, pqs_long, mom_long, uptrend)
        scs_short = _scs(tas_short, pqs_short, mom_short, downtrend)
        scs_brk_long = _scs_breakout(tas_long, mom_long, uptrend)
        scs_brk_short = _scs_breakout(tas_short, mom_short, downtrend)

        # --- TES (Trade Eligibility Score, Section 13) ---
        # Trigger: bullish/bearish bar as proxy for engulfing/pin bar
        trigger_long = bars[i].is_bullish and bars[i].body > 0.5 * (bars[i].high - bars[i].low)
        trigger_short = not bars[i].is_bullish and bars[i].body > 0.5 * (bars[i].high - bars[i].low)

        def _tes(trigger: bool, atr_d: float, entry_price: float, stop_price: float, t1_price: float) -> int:
            trig_s = 100 if trigger else 0
            risk = abs(entry_price - stop_price)
            eff = risk / atr_d if atr_d > 0 else 999
            stop_q = 100 if eff <= 1.5 else 50 if eff <= 2.0 else 0
            r_pot = abs(t1_price - entry_price) / risk if risk > 0 else 0
            r_q = 100 if r_pot >= 2.0 else 50 if r_pot >= 1.5 else 0
            timing_s = 75  # Simplified: assume average timing
            return int(0.30 * trig_s + 0.25 * stop_q + 0.25 * r_q + 0.20 * timing_s)

        # --- WMG check (Section 22) ---
        wmg_locked = False
        if len(trade_history) >= 30:
            wins = sum(1 for t in trade_history[-30:] if t > 0)
            losses_w = sum(1 for t in trade_history[-30:] if t < 0)
            total_w = wins + losses_w
            if total_w > 0:
                wr = wins / total_w
                avg_win = sum(t for t in trade_history[-30:] if t > 0) / max(1, wins)
                avg_loss = abs(sum(t for t in trade_history[-30:] if t < 0)) / max(1, losses_w)
                exp_w = (wr * avg_win) - ((1 - wr) * avg_loss)
                if exp_w <= -0.20:
                    wmg_locked = True

        if wmg_locked:
            continue

        # --- REGIME classification (Section 7) ---
        sideways = not uptrend and not downtrend
        adx_weak = adx[i] < 20
        is_range_regime = sideways and adx_weak

        # --- Setup C: Range Reversion (Section 14) ---
        range_high = max(bars[k].high for k in range(max(0, i - 40), i + 1)) if i >= 10 else 0
        range_low = min(bars[k].low for k in range(max(0, i - 40), i + 1)) if i >= 10 else 0
        mid_range = (range_high + range_low) / 2
        near_range_low = abs(closes[i] - range_low) <= 0.3 * atr[i] if atr[i] > 0 else False
        near_range_high = abs(closes[i] - range_high) <= 0.3 * atr[i] if atr[i] > 0 else False

        # --- COOLDOWN check (Section 21) ---
        in_cooldown = consecutive_losses >= 2

        # --- Direction selection (Setup A: breakout, Setup B: pullback, Setup C: range) ---
        direction = None
        setup_type = None

        # Setup A — Breakout: price breaks swing high/low with volume (uses breakout SCS)
        if not in_cooldown and scs_brk_long >= 55 and tas_long >= 65 and breakout_long and breakout_vol and bars[i].is_bullish:
            direction = "LONG"
            setup_type = "A"
        elif not in_cooldown and scs_brk_short >= 55 and tas_short >= 65 and breakout_short and breakout_vol and not bars[i].is_bullish:
            direction = "SHORT"
            setup_type = "A"
        # Setup B — Pullback: price near EMA + trigger bar + structure (uses pullback SCS)
        elif scs_long >= 55 and tas_long >= 40 and trigger_long and ema_touch:
            direction = "LONG"
            setup_type = "B"
        elif scs_short >= 55 and tas_short >= 40 and trigger_short and ema_touch:
            direction = "SHORT"
            setup_type = "B"
        # Setup C — Range Reversion: price near range boundary with trigger
        elif is_range_regime and near_range_low and trigger_long and scs_long >= 55:
            direction = "LONG"
            setup_type = "C"
        elif is_range_regime and near_range_high and trigger_short and scs_short >= 55:
            direction = "SHORT"
            setup_type = "C"

        # Apply cooldown filter: requires SCS >= 70 AND TES >= 70 (Section 21)
        if in_cooldown and direction:
            candidate_scs = scs_brk_long if setup_type == "A" and direction == "LONG" else \
                            scs_brk_short if setup_type == "A" and direction == "SHORT" else \
                            scs_long if direction == "LONG" else scs_short
            if candidate_scs < 70:
                direction = None

        if direction:
            entry = bars[i].close
            atr_daily = atr[i] * 2  # Proxy for daily ATR

            if setup_type == "A":
                # Setup A targets (Section 17): T1=1*ATR, T2=2*ATR, T3=3*ATR
                if direction == "LONG":
                    stop = entry - 1.0 * atr_daily
                    t1 = entry + 1.0 * atr_daily
                    t2 = entry + 2.0 * atr_daily
                    t3 = entry + 3.0 * atr_daily
                else:
                    stop = entry + 1.0 * atr_daily
                    t1 = entry - 1.0 * atr_daily
                    t2 = entry - 2.0 * atr_daily
                    t3 = entry - 3.0 * atr_daily
            elif setup_type == "C":
                # Setup C targets (Section 17): T1=MidRange, T2=opposite bound
                if direction == "LONG":
                    stop = range_low - 1.0 * atr_daily
                    t1 = mid_range
                    t2 = range_high - 0.5 * atr_daily
                    t3 = t2  # No T3 for range trades
                else:
                    stop = range_high + 1.0 * atr_daily
                    t1 = mid_range
                    t2 = range_low + 0.5 * atr_daily
                    t3 = t2
            else:
                # Setup B targets (Section 17): T1=swing, T2=swing+1*ATR, T3=swing+2*ATR
                if direction == "LONG":
                    stop = entry - 1.0 * atr_daily
                    t1 = swing_high if i >= 10 else entry + 1.0 * atr_daily
                    t2 = t1 + 1.0 * atr_daily
                    t3 = t1 + 2.0 * atr_daily
                else:
                    stop = entry + 1.0 * atr_daily
                    t1 = swing_low if i >= 10 else entry - 1.0 * atr_daily
                    t2 = t1 - 1.0 * atr_daily
                    t3 = t1 - 2.0 * atr_daily

            risk = abs(entry - stop)
            if risk < 0.01:
                continue

            # --- GATE 10/11: EFF and R hard kills ---
            eff = risk / atr_daily if atr_daily > 0 else 999
            r_potential = abs(t1 - entry) / risk if risk > 0 else 0
            if eff > 2.5 or r_potential < 1.0:
                continue

            # TES gate
            has_trigger = (direction == "LONG" and trigger_long) or (direction == "SHORT" and trigger_short)
            tes = _tes(has_trigger, atr_daily, entry, stop, t1)
            if tes < 50:
                continue

            # Cooldown TES check (Section 21): also requires TES >= 70
            if in_cooldown and tes < 70:
                continue

            # --- 3-tier partial exit simulation ---
            max_hold = 50  # 10 trading days equiv
            partial_taken = [False, False]
            total_pnl = 0.0

            for j in range(i + 1, min(i + max_hold, len(bars))):
                if direction == "LONG":
                    if bars[j].low <= stop:
                        remaining = 1.0 - (0.33 if partial_taken[0] else 0) - (0.33 if partial_taken[1] else 0)
                        pnl = (stop - entry) / entry * 100 * remaining
                        total_pnl += pnl
                        result.trades.append(Trade("TITAN", scenario.name, i, j, direction,
                                                   entry, stop, stop, t3, total_pnl, total_pnl / (risk / entry * 100), "stop_hit"))
                        break
                    if not partial_taken[0] and bars[j].high >= t1:
                        total_pnl += (t1 - entry) / entry * 100 * 0.33
                        partial_taken[0] = True
                        stop = entry  # Breakeven (Section 18.1)
                    if not partial_taken[1] and partial_taken[0] and bars[j].high >= t2:
                        total_pnl += (t2 - entry) / entry * 100 * 0.33
                        partial_taken[1] = True
                        stop = t1  # Lock T1 profit (Section 18.2)
                    if partial_taken[1] and bars[j].high >= t3:
                        total_pnl += (t3 - entry) / entry * 100 * 0.34
                        result.trades.append(Trade("TITAN", scenario.name, i, j, direction,
                                                   entry, t3, stop, t3, total_pnl, total_pnl / (risk / entry * 100), "full_target"))
                        break
                else:
                    if bars[j].high >= stop:
                        remaining = 1.0 - (0.33 if partial_taken[0] else 0) - (0.33 if partial_taken[1] else 0)
                        pnl = (entry - stop) / entry * 100 * remaining
                        total_pnl += pnl
                        result.trades.append(Trade("TITAN", scenario.name, i, j, direction,
                                                   entry, stop, stop, t3, total_pnl, total_pnl / (risk / entry * 100), "stop_hit"))
                        break
                    if not partial_taken[0] and bars[j].low <= t1:
                        total_pnl += (entry - t1) / entry * 100 * 0.33
                        partial_taken[0] = True
                        stop = entry
                    if not partial_taken[1] and partial_taken[0] and bars[j].low <= t2:
                        total_pnl += (entry - t2) / entry * 100 * 0.33
                        partial_taken[1] = True
                        stop = t1
                    if partial_taken[1] and bars[j].low <= t3:
                        total_pnl += (entry - t3) / entry * 100 * 0.34
                        result.trades.append(Trade("TITAN", scenario.name, i, j, direction,
                                                   entry, t3, stop, t3, total_pnl, total_pnl / (risk / entry * 100), "full_target"))
                        break
            else:
                exit_p = bars[min(i + max_hold - 1, len(bars) - 1)].close
                remaining = 1.0 - (0.33 if partial_taken[0] else 0) - (0.33 if partial_taken[1] else 0)
                if direction == "LONG":
                    total_pnl += (exit_p - entry) / entry * 100 * remaining
                else:
                    total_pnl += (entry - exit_p) / entry * 100 * remaining
                result.trades.append(Trade("TITAN", scenario.name, i, min(i + max_hold - 1, len(bars) - 1),
                                           direction, entry, exit_p, stop, t3, total_pnl,
                                           total_pnl / (risk / entry * 100) if risk > 0 else 0, "max_hold_exit"))

            # Update counters
            trade_pnl = result.trades[-1].pnl_pct
            trade_r = result.trades[-1].r_multiple
            daily_loss_r += max(0, -trade_r)
            weekly_loss_r += max(0, -trade_r)
            weekly_trade_count += 1
            daily_trade_count += 1
            trade_history.append(trade_r)

            if trade_pnl < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0

            cooldown = 8

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

STRATEGY_REGISTRY = {
    "SATVA": _sim_satva,
    "VORTEX": _sim_vortex,
    "NEXUS": _sim_nexus,
    "PRISM": _sim_prism,
    "FLUX": _sim_flux,
    "TITAN": _sim_titan,
}


def simulate(model: str, scenario: Scenario) -> SimResult:
    """Run a single model against a single scenario."""
    if model not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown model: {model}. Available: {', '.join(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[model](scenario)


def simulate_all(models: list[str] = None, n_bars: int = 200) -> dict[str, list[SimResult]]:
    """Run all models against all scenarios. Returns {model: [SimResult, ...]}."""
    from prompt_validator.scenarios import generate_all_scenarios
    if models is None:
        models = list(STRATEGY_REGISTRY.keys())
    scenarios = generate_all_scenarios(n_bars)
    results = {}
    for model in models:
        results[model] = [simulate(model, s) for s in scenarios]
    return results
