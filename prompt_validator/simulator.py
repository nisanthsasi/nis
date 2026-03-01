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
    """TITAN — Swing/Multi-day with multi-timeframe and partial exits."""
    bars = scenario.bars
    closes = [b.close for b in bars]
    ema50 = _ema(closes, 50)
    ema200 = _ema(closes, 200) if len(closes) >= 200 else _ema(closes, min(len(closes), 50))
    atr = _atr(bars, 14)
    result = SimResult("TITAN", scenario.name)
    daily_pnl = 0.0
    cooldown = 0

    for i in range(55, len(bars)):
        if cooldown > 0:
            cooldown -= 1
            continue
        if daily_pnl <= -2.0:
            result.halted = True
            result.halt_reason = "Max daily loss 2%"
            break

        # Multi-timeframe: EMA50 > EMA200 (daily trend)
        bullish_trend = ema50[i] > ema200[i]
        bearish_trend = ema50[i] < ema200[i]

        # Swing structure: higher low / lower high
        recent_lows = [bars[k].low for k in range(max(0, i - 10), i + 1)]
        recent_highs = [bars[k].high for k in range(max(0, i - 10), i + 1)]
        higher_low = min(recent_lows[-5:]) > min(recent_lows[:5]) if len(recent_lows) >= 10 else False
        lower_high = max(recent_highs[-5:]) < max(recent_highs[:5]) if len(recent_highs) >= 10 else False

        # Pullback to support (within 0.5*ATR of EMA50)
        near_ema = abs(closes[i] - ema50[i]) < 0.5 * atr[i] if atr[i] > 0 else False

        direction = None
        if bullish_trend and higher_low and near_ema and bars[i].is_bullish:
            direction = "LONG"
        elif bearish_trend and lower_high and near_ema and not bars[i].is_bullish:
            direction = "SHORT"

        if direction:
            entry = bars[i].close
            atr_daily = atr[i] * 2  # Proxy for daily ATR (using 2x intraday)
            if direction == "LONG":
                stop = entry - 1.5 * atr_daily
                t1 = entry + 1.0 * atr_daily
                t2 = entry + 2.0 * atr_daily
                t3 = entry + 3.0 * atr_daily
            else:
                stop = entry + 1.5 * atr_daily
                t1 = entry - 1.0 * atr_daily
                t2 = entry - 2.0 * atr_daily
                t3 = entry - 3.0 * atr_daily

            risk = abs(entry - stop)
            if risk < 0.01:
                continue

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
                        stop = entry  # Move stop to breakeven
                    if not partial_taken[1] and partial_taken[0] and bars[j].high >= t2:
                        total_pnl += (t2 - entry) / entry * 100 * 0.33
                        partial_taken[1] = True
                        stop = t1  # Move stop to T1
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

            daily_pnl += result.trades[-1].pnl_pct
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
