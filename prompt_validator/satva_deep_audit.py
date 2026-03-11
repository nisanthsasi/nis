"""SATVA Deep Audit — v14.4.2 vs v15.0.0 Comparative Simulator.

Implements both SATVA versions with proper rules and compares metrics
side-by-side across all 10 market scenarios.

Usage:
    python -m prompt_validator.satva_deep_audit
    python -m prompt_validator.satva_deep_audit --bars 500
"""

import argparse
import math
from dataclasses import dataclass, field
from prompt_validator.scenarios import Bar, Scenario, generate_all_scenarios
from prompt_validator.simulator import _ema, _sma, _atr, _rsi


# ---------------------------------------------------------------------------
# Extended Trade dataclass
# ---------------------------------------------------------------------------

@dataclass
class AuditTrade:
    version: str  # "v14" or "v15"
    scenario: str
    direction: str  # "LONG" or "SHORT"
    setup_type: str  # "A", "B", "C", "D"
    regime: str
    entry_bar: int
    exit_bar: int
    entry_price: float
    exit_price: float
    stop_price: float
    r_trade: float
    r_multiple: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""
    rcs_score: float = 0.0
    ses_score: float = 0.0
    tas_score: float = 0.0
    mom_score: float = 0.0
    tier_reached: int = 0  # 0/1/2/3 for v15

    @property
    def is_winner(self) -> bool:
        return self.pnl_pct > 0

    @property
    def is_loser(self) -> bool:
        return self.pnl_pct < 0


@dataclass
class AuditResult:
    version: str
    scenario: str
    trades: list[AuditTrade] = field(default_factory=list)
    total_pnl_pct: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    regime_counts: dict = field(default_factory=dict)
    setup_counts: dict = field(default_factory=dict)

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
    def avg_win_r(self) -> float:
        wins = [t.r_multiple for t in self.trades if t.is_winner]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss_r(self) -> float:
        losses = [abs(t.r_multiple) for t in self.trades if t.is_loser]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl_pct for t in self.trades if t.is_winner)
        gross_loss = abs(sum(t.pnl_pct for t in self.trades if t.is_loser))
        if gross_loss == 0:
            return float('inf') if gross_win > 0 else 0.0
        return gross_win / gross_loss

    @property
    def expectancy_r(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.r_multiple for t in self.trades) / len(self.trades)

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
            max_dd = max(max_dd, peak - equity)
        return max_dd


# ---------------------------------------------------------------------------
# Shared indicator / structure helpers
# ---------------------------------------------------------------------------

def _compute_atr_prev(atr_values: list[float], idx: int, lookback: int = 24) -> float:
    start = max(0, idx - lookback)
    window = atr_values[start:idx]
    return sum(window) / len(window) if window else atr_values[idx]


def _compute_vwap(bars: list[Bar], start: int, end: int) -> float:
    cum_pv = 0.0
    cum_v = 0
    for i in range(start, end + 1):
        tp = (bars[i].high + bars[i].low + bars[i].close) / 3
        cum_pv += tp * bars[i].volume
        cum_v += bars[i].volume
    return cum_pv / cum_v if cum_v > 0 else bars[end].close


def _compute_pd_levels(bars: list[Bar], pd_end: int = 23):
    n = min(pd_end + 1, len(bars))
    pdo = bars[0].open
    pdh = max(b.high for b in bars[:n])
    pdl = min(b.low for b in bars[:n])
    pdc = bars[n - 1].close
    return pdo, pdh, pdl, pdc


def _swing_highs(bars: list[Bar], start: int, end: int) -> list[tuple[int, float]]:
    pivots = []
    for i in range(start + 2, end - 1):
        if (bars[i].high > bars[i - 1].high and bars[i].high > bars[i - 2].high
                and bars[i].high > bars[i + 1].high and bars[i].high > bars[i + 2].high):
            pivots.append((i, bars[i].high))
    return pivots


def _swing_lows(bars: list[Bar], start: int, end: int) -> list[tuple[int, float]]:
    pivots = []
    for i in range(start + 2, end - 1):
        if (bars[i].low < bars[i - 1].low and bars[i].low < bars[i - 2].low
                and bars[i].low < bars[i + 1].low and bars[i].low < bars[i + 2].low):
            pivots.append((i, bars[i].low))
    return pivots


def _linear_reg_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


def _vol_sma(bars: list[Bar], idx: int, period: int = 20) -> float:
    start = max(0, idx - period + 1)
    vols = [b.volume for b in bars[start:idx + 1]]
    return sum(vols) / len(vols) if vols else 1.0


def _nearest_level(price: float, levels: list[float], vwap: float) -> tuple[float, float]:
    if not levels:
        return price, 0.0
    dists = [(abs(price - lv), lv) for lv in levels]
    dists.sort(key=lambda x: (x[0], abs(x[1] - vwap)))
    return dists[0][1], dists[0][0]


def _body_ratio(bars: list[Bar], idx: int, lookback: int = 10) -> float:
    start = max(0, idx - lookback + 1)
    ratios = []
    for b in bars[start:idx + 1]:
        rng = b.high - b.low
        if rng < 0.001:
            ratios.append(0.0)
        else:
            ratios.append(abs(b.close - b.open) / rng)
    return sum(ratios) / len(ratios) if ratios else 0.0


def _entropy_score(bars: list[Bar], idx: int, atr: float, window: int = 20) -> float:
    start = max(1, idx - window + 1)
    count = 0
    for i in range(start, idx + 1):
        b = bars[i]
        body = abs(b.close - b.open)
        rng = b.high - b.low
        if rng > 0 and body <= 0.25 * rng:
            count += 1
        elif (b.high <= bars[i - 1].high and b.low >= bars[i - 1].low):
            count += 1
        elif atr > 0 and body <= 0.15 * atr:
            count += 1
    actual_window = idx - start + 1
    return 100 * count / actual_window if actual_window > 0 else 0


def _check_abt(bars: list[Bar], idx: int, atr: float, vol_sma: float) -> bool:
    for j in range(max(0, idx - 2), idx + 1):
        tr = bars[j].high - bars[j].low
        if atr > 0 and tr >= 2.2 * atr:
            return True
        if vol_sma > 0 and bars[j].volume >= 2.5 * vol_sma:
            return True
    return False


def _check_compression(bars: list[Bar], idx: int, atr: float, atr_prev: float) -> tuple[bool, float, float, float]:
    n = 12
    start = max(0, idx - n + 1)
    window = bars[start:idx + 1]
    if len(window) < 3:
        return False, 0, 0, 0
    highs = [b.high for b in window]
    lows = [b.low for b in window]
    overlap_range = max(0, min(highs) - max(lows))
    ranges = sorted([b.high - b.low for b in window])
    median_range = ranges[len(ranges) // 2] if ranges else 1.0
    overlap_pct = overlap_range / median_range if median_range > 0 else 0
    contraction = atr / atr_prev if atr_prev > 0 else 1.0
    vol_slope = _linear_reg_slope([b.volume for b in window])
    valid = overlap_pct >= 0.60 and contraction <= 0.85 and vol_slope <= 0
    return valid, overlap_pct, contraction, vol_slope


def _check_expansion(bars: list[Bar], idx: int, atr: float, vol_sma: float) -> tuple[bool, bool]:
    b = bars[idx]
    tr = b.high - b.low
    body = abs(b.close - b.open)
    start = max(0, idx - 9)
    avg_body = sum(abs(bars[j].close - bars[j].open) for j in range(start, idx + 1)) / max(1, idx - start + 1)
    exp_valid = ((tr >= 1.2 * atr or b.volume >= vol_sma) and body >= 1.2 * avg_body) if atr > 0 else False
    exp_strong = ((tr >= 1.4 * atr or b.volume >= 1.4 * vol_sma) and body >= 1.4 * avg_body) if atr > 0 else False
    return exp_valid, exp_strong


# ---------------------------------------------------------------------------
# v14 Regime + RCS + SES
# ---------------------------------------------------------------------------

def _compute_rcs_v14(htf_bin: int, vol_bin: int, beh_bin: int, lvl_bin: int, time_bin: int) -> float:
    return 0.30 * htf_bin + 0.20 * vol_bin + 0.20 * beh_bin + 0.15 * lvl_bin + 0.15 * time_bin


def _compute_ses_v14(trig_bin: int, str_bin: int, lvlq_bin: int, eff_bin: int) -> float:
    return 0.30 * trig_bin + 0.25 * str_bin + 0.25 * lvlq_bin + 0.20 * eff_bin


def _regime_v14(abt: bool, vol_bin: int, comp_valid: bool, exp_valid: bool,
                entropy: float, rcs: float) -> str:
    if abt or vol_bin == 0:
        return "SHOCK"
    if comp_valid and not exp_valid:
        return "RANGE"
    if exp_valid and entropy <= 40 and rcs >= 70:
        return "TREND"
    if 41 <= entropy <= 59 or 65 <= rcs <= 69:
        return "UNCLEAR"
    return "UNCLEAR"


# ---------------------------------------------------------------------------
# v15 TAS + MOM + VOLP + PQS + RCS + SES
# ---------------------------------------------------------------------------

def _compute_tas_v15(ema20_1h: float, ema50_1h: float, vwap: float, price: float,
                     ema9_5m: float, ema21_5m: float, rsi_5m: float,
                     direction: str) -> tuple[float, int, int]:
    # HTF layer
    slope_1h = ema20_1h - ema50_1h
    price_vs_vwap = 1 if price > vwap else (-1 if price < vwap else 0)
    slope_aligns = (slope_1h > 0 and direction == "LONG") or (slope_1h < 0 and direction == "SHORT")
    vwap_aligns = (price_vs_vwap == 1 and direction == "LONG") or (price_vs_vwap == -1 and direction == "SHORT")
    if slope_aligns and vwap_aligns:
        htf = 100
    elif slope_aligns or vwap_aligns:
        htf = 50
    else:
        htf = 0

    # EXEC layer
    if direction == "LONG":
        trigger = ema9_5m > ema21_5m and (rsi_5m > 40 if rsi_5m else True)
    else:
        trigger = ema9_5m < ema21_5m and (rsi_5m < 60 if rsi_5m else True)
    exec_bin = 100 if trigger else 0

    tas = 0.60 * htf + 0.40 * exec_bin
    return tas, htf, exec_bin


def _compute_mom_v15(rsi_5m: float, direction: str) -> tuple[float, int]:
    if rsi_5m is None:
        return 50, 0
    if direction == "LONG":
        in_range = 40 <= rsi_5m <= 70
    else:
        in_range = 30 <= rsi_5m <= 60
    mom_rsi = 100 if in_range else 0
    mom = max(0, mom_rsi)
    return mom, 0


def _compute_volp_v15(bars: list[Bar], idx: int, vol_sma: float) -> int:
    vol = bars[idx].volume
    expanding = vol > 1.2 * vol_sma if vol_sma > 0 else False
    dryup = False
    if idx >= 2 and vol_sma > 0:
        dryup = all(bars[idx - k].volume < 0.5 * vol_sma for k in range(3))
    if dryup:
        return 0
    if expanding:
        return 100
    return 50


def _compute_rcs_v15(tas_bin: int, vol_bin: int, beh_bin: int, lvl_bin: int,
                     volp_bin: int, time_bin: int) -> float:
    return 0.25 * tas_bin + 0.15 * vol_bin + 0.15 * beh_bin + 0.15 * lvl_bin + 0.15 * volp_bin + 0.15 * time_bin


def _compute_ses_v15(trig_bin: int, str_bin: int, lvlq_bin: int, eff_bin: int, mom_bin: int) -> float:
    return 0.25 * trig_bin + 0.25 * str_bin + 0.20 * lvlq_bin + 0.15 * eff_bin + 0.15 * mom_bin


def _regime_v15(abt: bool, vol_bin: int, comp_valid: bool, exp_valid: bool, exp_strong: bool,
                entropy: float, rcs: float, tas: float) -> str:
    if abt or vol_bin == 0:
        return "SHOCK"
    if comp_valid and not exp_valid and entropy <= 40:
        return "RANGE"
    if exp_strong and tas >= 60 and entropy <= 40 and rcs >= 70:
        return "STRONG_TREND"
    if exp_valid and entropy <= 40 and rcs >= 65:
        return "TREND"
    return "UNCLEAR"


# ---------------------------------------------------------------------------
# Common scoring helpers
# ---------------------------------------------------------------------------

def _vol_stability(atr_values: list[float], bars: list[Bar], idx: int) -> float:
    start = max(0, idx - 19)
    series = []
    for j in range(start, idx + 1):
        tr = bars[j].high - bars[j].low
        if atr_values[j] > 0 and tr < 2.2 * atr_values[j]:
            series.append(atr_values[j])
    if len(series) < 2:
        return 1.0
    mean_v = sum(series) / len(series)
    if mean_v == 0:
        return 1.0
    var = sum((x - mean_v) ** 2 for x in series) / len(series)
    return math.sqrt(var) / mean_v


def _vol_bin(vstab: float, pullback_norm: float) -> int:
    if vstab <= 0.12 and pullback_norm <= 1.0:
        return 100
    if vstab <= 0.20 and pullback_norm <= 1.3:
        return 50
    return 0


def _time_bin(bar_idx: int, total_bars: int) -> int:
    # Map bar index to approximate session time fraction
    frac = bar_idx / max(1, total_bars)
    if frac < 0.03:  # before 09:20
        return 0
    if frac < 0.80:  # 09:20 - 20:30
        return 100
    if frac < 0.93:  # 20:30 - 22:30
        return 50
    return 0


def _lvl_chop_count(bars: list[Bar], idx: int, levels: list[float], lookback: int = 24) -> int:
    start = max(0, idx - lookback + 1)
    count = 0
    for i in range(start, idx + 1):
        for lv in levels:
            crossed = (bars[i].low < lv < bars[i].high)
            if crossed:
                if bars[i].close > lv and bars[i].open < lv:
                    count += 1
                elif bars[i].close < lv and bars[i].open > lv:
                    count += 1
    return count


def _eff_bin(eff: float) -> int:
    if eff <= 1.0:
        return 100
    if eff <= 1.3:
        return 50
    return 0


def _structure_bins(swing_highs: list[tuple[int, float]], swing_lows: list[tuple[int, float]],
                    direction: str) -> int:
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 50
    if direction == "LONG":
        hh = swing_highs[-1][1] > swing_highs[-2][1]
        hl = swing_lows[-1][1] > swing_lows[-2][1]
        if hh and hl:
            return 100
        if hh or hl:
            return 50
    else:
        ll = swing_lows[-1][1] < swing_lows[-2][1]
        lh = swing_highs[-1][1] < swing_highs[-2][1]
        if ll and lh:
            return 100
        if ll or lh:
            return 50
    return 0


# ---------------------------------------------------------------------------
# v14 Simulator
# ---------------------------------------------------------------------------

def simulate_v14(scenario: Scenario) -> AuditResult:
    """Simulate SATVA v14.4.2 rules."""
    bars = scenario.bars
    if len(bars) < 50:
        return AuditResult("v14", scenario.name)

    closes = [b.close for b in bars]
    atr = _atr(bars, 14)
    rsi = _rsi(closes, 14)
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    # 1H proxies using SMA
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)

    result = AuditResult("v14", scenario.name)
    pdo, pdh, pdl, pdc = _compute_pd_levels(bars)
    trade_count = 0
    session_loss_r = 0.0
    consec_losses = 0
    cooldown = False
    in_position = False
    position_exit_bar = 0

    for i in range(30, len(bars) - 5):
        if in_position and i <= position_exit_bar:
            continue
        in_position = False

        if trade_count >= 3 or session_loss_r >= 2.0:
            result.halted = True
            result.halt_reason = "SESSION_LOCK"
            break

        atr_i = atr[i]
        if atr_i < 0.001:
            continue

        atr_prev = _compute_atr_prev(atr, i)
        vwap = _compute_vwap(bars, 24, i)
        vsma = _vol_sma(bars, i)
        levels = [pdo, pdh, pdl, pdc, vwap]

        # ABT
        abt_active = _check_abt(bars, i, atr_i, vsma)
        if abt_active:
            result.regime_counts["SHOCK"] = result.regime_counts.get("SHOCK", 0) + 1
            continue

        # Compression / Expansion
        comp_valid, _, _, _ = _check_compression(bars, i, atr_i, atr_prev)
        exp_valid, exp_strong = _check_expansion(bars, i, atr_i, vsma)
        entropy = _entropy_score(bars, i, atr_i)

        # HTF
        slope = sma20[i] - sma50[i] if i >= 50 else 0
        price_vs_vwap = 1 if bars[i].close > vwap else -1

        # Try both directions
        for direction in ["LONG", "SHORT"]:
            if trade_count >= 3 or session_loss_r >= 2.0:
                break

            slope_aligns = (slope > 0 and direction == "LONG") or (slope < 0 and direction == "SHORT")
            vwap_aligns = (price_vs_vwap == 1 and direction == "LONG") or (price_vs_vwap == -1 and direction == "SHORT")
            htf_bin = 100 if (slope_aligns and vwap_aligns) else (50 if (slope_aligns or vwap_aligns) else 0)

            vstab = _vol_stability(atr, bars, i)
            vbin = _vol_bin(vstab, 0.5)
            beh_bin = 100 if _body_ratio(bars, i) >= 0.55 else (50 if _body_ratio(bars, i) >= 0.45 else 0)
            chop = _lvl_chop_count(bars, i, levels)
            lvl_bin = 100 if chop <= 1 else (50 if chop <= 3 else 0)
            tbin = _time_bin(i, len(bars))

            rcs = _compute_rcs_v14(htf_bin, vbin, beh_bin, lvl_bin, tbin)
            regime = _regime_v14(abt_active, vbin, comp_valid, exp_valid, entropy, rcs)
            result.regime_counts[regime] = result.regime_counts.get(regime, 0) + 1

            if regime == "SHOCK":
                continue

            # Entry signal: EMA cross aligned + expansion
            if direction == "LONG":
                signal = ema9[i] > ema21[i] and 40 < rsi[i] < 75 and exp_valid
            else:
                signal = ema9[i] < ema21[i] and 25 < rsi[i] < 60 and exp_valid

            if not signal:
                continue

            # Determine setup type
            if regime == "TREND" and rcs >= 70 and exp_strong:
                setup = "A"
            elif regime == "RANGE" and comp_valid and entropy <= 40:
                setup = "C"
            elif rcs >= 65:
                setup = "B"
            else:
                continue

            # SES
            trig_bin = 100 if exp_strong else (50 if exp_valid else 0)
            sh = _swing_highs(bars, max(0, i - 40), min(i + 3, len(bars)))
            sl = _swing_lows(bars, max(0, i - 40), min(i + 3, len(bars)))
            str_bin = _structure_bins(sh, sl, direction)
            _, lvl_dist = _nearest_level(bars[i].close, levels, vwap)
            lvlq_bin = 100 if lvl_dist <= 0.25 * atr_i else (50 if lvl_dist <= 0.50 * atr_i else 0)

            entry = bars[i].close
            if direction == "LONG":
                stop = entry - 1.2 * atr_i
            else:
                stop = entry + 1.2 * atr_i
            r_trade = abs(entry - stop)
            if r_trade < 0.001:
                continue
            eff = r_trade / atr_i
            if eff > 1.8:
                continue
            eff_b = _eff_bin(eff)

            ses = _compute_ses_v14(trig_bin, str_bin, lvlq_bin, eff_b)
            if ses < 65:
                continue
            if entropy >= 60:
                continue

            # Cooldown check
            if cooldown and (rcs < 75 or ses < 80 or entropy > 40):
                continue

            # --- Execute trade (v14: 100% exit at T1) ---
            t1_dist = max(0.9 * atr_i, lvl_dist)
            if direction == "LONG":
                t1 = entry + t1_dist
            else:
                t1 = entry - t1_dist

            exit_price = None
            exit_bar = i
            exit_reason = ""
            for j in range(i + 1, min(i + 30, len(bars))):
                if direction == "LONG":
                    if bars[j].low <= stop:
                        exit_price = stop
                        exit_bar = j
                        exit_reason = "stop_hit"
                        break
                    if bars[j].high >= t1:
                        exit_price = t1
                        exit_bar = j
                        exit_reason = "t1_hit"
                        break
                else:
                    if bars[j].high >= stop:
                        exit_price = stop
                        exit_bar = j
                        exit_reason = "stop_hit"
                        break
                    if bars[j].low <= t1:
                        exit_price = t1
                        exit_bar = j
                        exit_reason = "t1_hit"
                        break
            else:
                exit_bar = min(i + 29, len(bars) - 1)
                exit_price = bars[exit_bar].close
                exit_reason = "time_exit"

            if direction == "LONG":
                pnl_pct = (exit_price - entry) / entry * 100
                r_mult = (exit_price - entry) / r_trade
            else:
                pnl_pct = (entry - exit_price) / entry * 100
                r_mult = (entry - exit_price) / r_trade

            trade = AuditTrade(
                version="v14", scenario=scenario.name, direction=direction,
                setup_type=setup, regime=regime, entry_bar=i, exit_bar=exit_bar,
                entry_price=entry, exit_price=exit_price, stop_price=stop,
                r_trade=r_trade, r_multiple=r_mult, pnl_pct=pnl_pct,
                exit_reason=exit_reason, rcs_score=rcs, ses_score=ses,
                tier_reached=1 if exit_reason == "t1_hit" else 0
            )
            result.trades.append(trade)
            result.setup_counts[setup] = result.setup_counts.get(setup, 0) + 1
            trade_count += 1
            in_position = True
            position_exit_bar = exit_bar

            if trade.is_loser:
                session_loss_r += abs(r_mult)
                consec_losses += 1
                if consec_losses >= 2:
                    cooldown = True
            else:
                consec_losses = 0
                cooldown = False
            break  # one trade per bar

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


# ---------------------------------------------------------------------------
# v15 Simulator
# ---------------------------------------------------------------------------

def simulate_v15(scenario: Scenario) -> AuditResult:
    """Simulate SATVA v15.0.0 rules with 3-tier exits."""
    bars = scenario.bars
    if len(bars) < 50:
        return AuditResult("v15", scenario.name)

    closes = [b.close for b in bars]
    atr = _atr(bars, 14)
    rsi = _rsi(closes, 14)
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    ema20_1h = _ema(closes, 20)  # proxy
    ema50_1h = _ema(closes, 50)  # proxy

    result = AuditResult("v15", scenario.name)
    pdo, pdh, pdl, pdc = _compute_pd_levels(bars)
    trade_count = 0
    session_loss_r = 0.0
    consec_losses = 0
    cooldown = False
    in_position = False
    position_exit_bar = 0

    for i in range(30, len(bars) - 5):
        if in_position and i <= position_exit_bar:
            continue
        in_position = False

        if trade_count >= 3 or session_loss_r >= 2.0:
            result.halted = True
            result.halt_reason = "SESSION_LOCK"
            break

        atr_i = atr[i]
        if atr_i < 0.001:
            continue

        atr_prev = _compute_atr_prev(atr, i)
        vwap = _compute_vwap(bars, 24, i)
        vsma = _vol_sma(bars, i)
        levels = [pdo, pdh, pdl, pdc, vwap]

        abt_active = _check_abt(bars, i, atr_i, vsma)
        if abt_active:
            result.regime_counts["SHOCK"] = result.regime_counts.get("SHOCK", 0) + 1
            continue

        comp_valid, _, _, _ = _check_compression(bars, i, atr_i, atr_prev)
        exp_valid, exp_strong = _check_expansion(bars, i, atr_i, vsma)
        entropy = _entropy_score(bars, i, atr_i)

        for direction in ["LONG", "SHORT"]:
            if trade_count >= 3 or session_loss_r >= 2.0:
                break

            # TAS
            tas, htf_bin, exec_bin = _compute_tas_v15(
                ema20_1h[i], ema50_1h[i], vwap, bars[i].close,
                ema9[i], ema21[i], rsi[i], direction)
            if tas < 40:
                continue

            # MOM
            mom, _ = _compute_mom_v15(rsi[i], direction)

            # VOLP
            volp_bin = _compute_volp_v15(bars, i, vsma)

            # RCS components
            vstab = _vol_stability(atr, bars, i)
            vbin = _vol_bin(vstab, 0.5)
            beh_bin = 100 if _body_ratio(bars, i) >= 0.55 else (50 if _body_ratio(bars, i) >= 0.45 else 0)
            chop = _lvl_chop_count(bars, i, levels)
            lvl_bin = 100 if chop <= 1 else (50 if chop <= 3 else 0)
            tbin = _time_bin(i, len(bars))
            tas_rcs_bin = 100 if tas >= 60 else (50 if tas >= 40 else 0)

            rcs = _compute_rcs_v15(tas_rcs_bin, vbin, beh_bin, lvl_bin, volp_bin, tbin)
            regime = _regime_v15(abt_active, vbin, comp_valid, exp_valid, exp_strong,
                                entropy, rcs, tas)
            result.regime_counts[regime] = result.regime_counts.get(regime, 0) + 1

            if regime == "SHOCK":
                continue

            # Entry signal
            if direction == "LONG":
                signal = ema9[i] > ema21[i] and 40 < rsi[i] < 70 and (exp_valid or (regime in ("TREND", "STRONG_TREND")))
            else:
                signal = ema9[i] < ema21[i] and 30 < rsi[i] < 60 and (exp_valid or (regime in ("TREND", "STRONG_TREND")))

            if not signal:
                continue

            # Determine setup
            if regime == "STRONG_TREND" and rcs >= 70 and tas >= 60 and exp_strong:
                setup = "A"
            elif regime in ("TREND", "STRONG_TREND") and rcs >= 70 and mom >= 50:
                setup = "D"
            elif regime == "RANGE" and comp_valid and entropy <= 40:
                setup = "C"
            elif rcs >= 65:
                setup = "B"
            else:
                continue

            # SES
            trig_bin = 100 if exp_strong else (50 if exp_valid else 0)
            sh = _swing_highs(bars, max(0, i - 40), min(i + 3, len(bars)))
            sl = _swing_lows(bars, max(0, i - 40), min(i + 3, len(bars)))
            str_bin = _structure_bins(sh, sl, direction)
            _, lvl_dist = _nearest_level(bars[i].close, levels, vwap)
            lvlq_bin = 100 if lvl_dist <= 0.25 * atr_i else (50 if lvl_dist <= 0.50 * atr_i else 0)

            entry = bars[i].close
            if direction == "LONG":
                stop = entry - 1.2 * atr_i
            else:
                stop = entry + 1.2 * atr_i
            r_trade = abs(entry - stop)
            if r_trade < 0.001:
                continue
            eff = r_trade / atr_i
            if eff > 1.8:
                continue
            eff_b = _eff_bin(eff)
            mom_bin = 100 if mom >= 80 else (50 if mom >= 40 else 0)

            ses = _compute_ses_v15(trig_bin, str_bin, lvlq_bin, eff_b, mom_bin)
            if ses < 65:
                continue
            if entropy >= 60:
                continue

            if cooldown and (rcs < 75 or ses < 80 or entropy > 40 or mom < 50):
                continue

            # --- Execute trade (v15: 3-tier exit) ---
            t1_dist = max(0.9 * atr_i, lvl_dist)
            t2_dist = 1.6 * atr_i
            t3_dist = 2.4 * atr_i

            if direction == "LONG":
                t1 = entry + t1_dist
                t2 = entry + t2_dist
                t3 = entry + t3_dist
            else:
                t1 = entry - t1_dist
                t2 = entry - t2_dist
                t3 = entry - t3_dist

            # Simulate 3-tier exit
            tier = 0
            position_pct = 1.0  # fraction remaining
            realized_r = 0.0
            highest_close = entry
            lowest_close = entry
            trail_stop = stop
            exit_bar = i
            exit_reason = ""
            final_exit = False

            for j in range(i + 1, min(i + 60, len(bars))):
                if direction == "LONG":
                    highest_close = max(highest_close, bars[j].close)
                    # Check stop
                    active_stop = trail_stop if tier >= 2 else stop
                    if tier == 1:
                        active_stop = max(stop, entry + 0.10 * atr_i)  # BE pad
                    if bars[j].low <= active_stop:
                        realized_r += (active_stop - entry) / r_trade * position_pct
                        exit_bar = j
                        exit_reason = "stop_hit" if tier == 0 else "trail_stop"
                        final_exit = True
                        break
                    # T1
                    if tier == 0 and bars[j].high >= t1:
                        realized_r += (t1 - entry) / r_trade * 0.40
                        position_pct -= 0.40
                        tier = 1
                    # T2
                    if tier == 1 and bars[j].high >= t2:
                        realized_r += (t2 - entry) / r_trade * 0.30
                        position_pct -= 0.30
                        tier = 2
                        trail_stop = highest_close - 1.0 * atr_i
                    # T3 / runner
                    if tier == 2:
                        new_trail = highest_close - 1.0 * atr_i
                        trail_stop = max(trail_stop, new_trail)
                        if bars[j].high >= t3:
                            realized_r += (t3 - entry) / r_trade * position_pct
                            exit_bar = j
                            exit_reason = "t3_hit"
                            final_exit = True
                            break
                        if bars[j].low <= trail_stop:
                            realized_r += (trail_stop - entry) / r_trade * position_pct
                            exit_bar = j
                            exit_reason = "trail_stop"
                            final_exit = True
                            break
                else:  # SHORT
                    lowest_close = min(lowest_close, bars[j].close)
                    active_stop = trail_stop if tier >= 2 else stop
                    if tier == 1:
                        active_stop = min(stop, entry - 0.10 * atr_i)
                    if bars[j].high >= active_stop:
                        realized_r += (entry - active_stop) / r_trade * position_pct
                        exit_bar = j
                        exit_reason = "stop_hit" if tier == 0 else "trail_stop"
                        final_exit = True
                        break
                    if tier == 0 and bars[j].low <= t1:
                        realized_r += (entry - t1) / r_trade * 0.40
                        position_pct -= 0.40
                        tier = 1
                    if tier == 1 and bars[j].low <= t2:
                        realized_r += (entry - t2) / r_trade * 0.30
                        position_pct -= 0.30
                        tier = 2
                        trail_stop = lowest_close + 1.0 * atr_i
                    if tier == 2:
                        new_trail = lowest_close + 1.0 * atr_i
                        trail_stop = min(trail_stop, new_trail)
                        if bars[j].low <= t3:
                            realized_r += (entry - t3) / r_trade * position_pct
                            exit_bar = j
                            exit_reason = "t3_hit"
                            final_exit = True
                            break
                        if bars[j].high >= trail_stop:
                            realized_r += (entry - trail_stop) / r_trade * position_pct
                            exit_bar = j
                            exit_reason = "trail_stop"
                            final_exit = True
                            break

            if not final_exit:
                # Time exit remaining position
                exit_bar = min(i + 59, len(bars) - 1)
                exit_p = bars[exit_bar].close
                if direction == "LONG":
                    realized_r += (exit_p - entry) / r_trade * position_pct
                else:
                    realized_r += (entry - exit_p) / r_trade * position_pct
                exit_reason = "time_exit"

            pnl_pct = realized_r * r_trade / entry * 100

            trade = AuditTrade(
                version="v15", scenario=scenario.name, direction=direction,
                setup_type=setup, regime=regime, entry_bar=i, exit_bar=exit_bar,
                entry_price=entry, exit_price=bars[exit_bar].close,
                stop_price=stop, r_trade=r_trade, r_multiple=realized_r,
                pnl_pct=pnl_pct, exit_reason=exit_reason,
                rcs_score=rcs, ses_score=ses, tas_score=tas, mom_score=mom,
                tier_reached=tier
            )
            result.trades.append(trade)
            result.setup_counts[setup] = result.setup_counts.get(setup, 0) + 1
            trade_count += 1
            in_position = True
            position_exit_bar = exit_bar

            if trade.is_loser:
                session_loss_r += abs(realized_r)
                consec_losses += 1
                if consec_losses >= 2:
                    cooldown = True
            else:
                consec_losses = 0
                cooldown = False
            break

    result.total_pnl_pct = sum(t.pnl_pct for t in result.trades)
    return result


# ---------------------------------------------------------------------------
# Comparative audit report
# ---------------------------------------------------------------------------

def _agg(results: list[AuditResult]) -> dict:
    all_trades = []
    for r in results:
        all_trades.extend(r.trades)
    total = len(all_trades)
    wins = sum(1 for t in all_trades if t.is_winner)
    losses = sum(1 for t in all_trades if t.is_loser)
    win_r = [t.r_multiple for t in all_trades if t.is_winner]
    loss_r = [abs(t.r_multiple) for t in all_trades if t.is_loser]
    gross_w = sum(t.pnl_pct for t in all_trades if t.is_winner)
    gross_l = abs(sum(t.pnl_pct for t in all_trades if t.is_loser))
    total_pnl = sum(t.pnl_pct for t in all_trades)
    total_r = sum(t.r_multiple for t in all_trades)

    setups = {}
    tiers = {0: 0, 1: 0, 2: 0, 3: 0}
    regimes = {}
    for t in all_trades:
        setups[t.setup_type] = setups.get(t.setup_type, 0) + 1
        tiers[min(t.tier_reached, 3)] = tiers.get(min(t.tier_reached, 3), 0) + 1
        regimes[t.regime] = regimes.get(t.regime, 0) + 1

    # Max drawdown
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in all_trades:
        equity += t.pnl_pct
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    return {
        "total": total, "wins": wins, "losses": losses,
        "win_rate": wins / total * 100 if total else 0,
        "avg_win_r": sum(win_r) / len(win_r) if win_r else 0,
        "avg_loss_r": sum(loss_r) / len(loss_r) if loss_r else 0,
        "profit_factor": gross_w / gross_l if gross_l > 0 else float('inf'),
        "expectancy_r": total_r / total if total else 0,
        "total_pnl": total_pnl,
        "max_dd": max_dd,
        "setups": setups, "tiers": tiers, "regimes": regimes,
        "halted": sum(1 for r in results if r.halted),
    }


def run_audit(n_bars: int = 500):
    """Run full v14 vs v15 comparative audit."""
    scenarios = generate_all_scenarios(n_bars)

    v14_results = []
    v15_results = []
    for sc in scenarios:
        v14_results.append(simulate_v14(sc))
        v15_results.append(simulate_v15(sc))

    v14_agg = _agg(v14_results)
    v15_agg = _agg(v15_results)

    print("=" * 100)
    print("  SATVA DEEP AUDIT — v14.4.2 vs v15.0.0 COMPARATIVE REPORT")
    print("=" * 100)
    print()

    # Summary table
    print("-" * 100)
    fmt = "{:<25} {:>15} {:>15} {:>15}"
    print(fmt.format("METRIC", "v14.4.2", "v15.0.0", "DELTA"))
    print("-" * 100)

    metrics = [
        ("Total Trades", v14_agg["total"], v15_agg["total"]),
        ("Wins", v14_agg["wins"], v15_agg["wins"]),
        ("Losses", v14_agg["losses"], v15_agg["losses"]),
    ]
    for name, v14v, v15v in metrics:
        print(fmt.format(name, str(v14v), str(v15v), f"{v15v - v14v:+d}"))

    float_metrics = [
        ("Win Rate %", v14_agg["win_rate"], v15_agg["win_rate"]),
        ("Avg Winner (R)", v14_agg["avg_win_r"], v15_agg["avg_win_r"]),
        ("Avg Loser (R)", v14_agg["avg_loss_r"], v15_agg["avg_loss_r"]),
        ("Profit Factor", v14_agg["profit_factor"], v15_agg["profit_factor"]),
        ("Expectancy (R/trade)", v14_agg["expectancy_r"], v15_agg["expectancy_r"]),
        ("Total P&L %", v14_agg["total_pnl"], v15_agg["total_pnl"]),
        ("Max Drawdown %", v14_agg["max_dd"], v15_agg["max_dd"]),
    ]
    for name, v14v, v15v in float_metrics:
        pf14 = f"{v14v:.3f}" if v14v != float('inf') else "INF"
        pf15 = f"{v15v:.3f}" if v15v != float('inf') else "INF"
        delta = v15v - v14v if v14v != float('inf') and v15v != float('inf') else 0
        print(fmt.format(name, pf14, pf15, f"{delta:+.3f}"))

    print("-" * 100)
    print()

    # Setup distribution
    print("  SETUP DISTRIBUTION")
    print("-" * 60)
    all_setups = sorted(set(list(v14_agg["setups"].keys()) + list(v15_agg["setups"].keys())))
    for s in all_setups:
        c14 = v14_agg["setups"].get(s, 0)
        c15 = v15_agg["setups"].get(s, 0)
        print(f"    Setup {s}: v14={c14:>4}  v15={c15:>4}  delta={c15 - c14:+d}")
    print()

    # Tier distribution (v15 only)
    print("  v15 EXIT TIER DISTRIBUTION")
    print("-" * 60)
    for tier, count in sorted(v15_agg["tiers"].items()):
        label = {0: "Stop/Time", 1: "T1 (40%)", 2: "T2 (30%)", 3: "T3/Runner (30%)"}
        pct = count / v15_agg["total"] * 100 if v15_agg["total"] else 0
        print(f"    {label.get(tier, f'Tier {tier}')}: {count:>4} ({pct:.1f}%)")
    print()

    # Regime distribution
    print("  REGIME DISTRIBUTION")
    print("-" * 60)
    all_regimes = sorted(set(list(v14_agg["regimes"].keys()) + list(v15_agg["regimes"].keys())))
    for r in all_regimes:
        c14 = v14_agg["regimes"].get(r, 0)
        c15 = v15_agg["regimes"].get(r, 0)
        print(f"    {r:<15}: v14={c14:>4}  v15={c15:>4}")
    print()

    # Per-scenario breakdown
    print("=" * 100)
    print("  PER-SCENARIO COMPARISON")
    print("=" * 100)
    print()
    hdr = "{:<20} {:>6} {:>7} {:>8} {:>6} {:>7} {:>8} {:>10}"
    print(hdr.format("Scenario", "v14 #", "v14 WR", "v14 Exp", "v15 #", "v15 WR", "v15 Exp", "Winner"))
    print("-" * 100)

    for v14r, v15r in zip(v14_results, v15_results):
        v14_wr = f"{v14r.win_rate:.1f}%" if v14r.trades else "---"
        v15_wr = f"{v15r.win_rate:.1f}%" if v15r.trades else "---"
        v14_exp = f"{v14r.expectancy_r:+.3f}" if v14r.trades else "---"
        v15_exp = f"{v15r.expectancy_r:+.3f}" if v15r.trades else "---"
        winner = "v15" if v15r.expectancy_r > v14r.expectancy_r else "v14" if v14r.expectancy_r > v15r.expectancy_r else "TIE"
        print(hdr.format(v14r.scenario[:20], v14r.total_trades, v14_wr, v14_exp,
                         v15r.total_trades, v15_wr, v15_exp, winner))
    print("-" * 100)
    print()

    # Runner analysis for v15
    print("  v15 RUNNER SUCCESS ANALYSIS")
    print("-" * 60)
    runners = [t for t in sum((r.trades for r in v15_results), []) if t.tier_reached >= 2]
    if runners:
        runner_wins = sum(1 for t in runners if t.r_multiple > 1.5)
        runner_avg_r = sum(t.r_multiple for t in runners) / len(runners)
        print(f"    Trades reaching T2+: {len(runners)}")
        print(f"    Runner success (>1.5R): {runner_wins} ({runner_wins / len(runners) * 100:.1f}%)")
        print(f"    Avg R on runner trades: {runner_avg_r:+.3f}")
    else:
        print("    No trades reached T2+")
    print()

    print("=" * 100)
    print("  VERDICT")
    print("=" * 100)
    if v15_agg["expectancy_r"] > v14_agg["expectancy_r"]:
        delta_pct = ((v15_agg["expectancy_r"] - v14_agg["expectancy_r"]) /
                     abs(v14_agg["expectancy_r"]) * 100) if v14_agg["expectancy_r"] != 0 else 0
        print(f"  v15 WINS — Expectancy improvement: {delta_pct:+.1f}%")
    else:
        print(f"  v14 WINS — v15 regression detected")
    print(f"  v14 expectancy: {v14_agg['expectancy_r']:+.4f}R/trade")
    print(f"  v15 expectancy: {v15_agg['expectancy_r']:+.4f}R/trade")
    print()

    return v14_results, v15_results


def main():
    parser = argparse.ArgumentParser(description="SATVA Deep Audit: v14 vs v15")
    parser.add_argument("--bars", type=int, default=500)
    args = parser.parse_args()
    run_audit(args.bars)


if __name__ == "__main__":
    main()
