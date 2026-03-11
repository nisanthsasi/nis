"""SATVA v15 Gate Threshold Optimizer.

Finds optimal gate thresholds that maximize expectancy by:
1. Computing all SATVA v15 scores on synthetic bar data
2. Labeling forward outcomes (win/loss/breakeven)
3. Grid-searching threshold combinations
4. Optimizing component weights
5. Analyzing component contribution and redundancy

Run as:  python -m prompt_validator.gate_optimizer
"""

from __future__ import annotations

import itertools
import math
import statistics
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

from prompt_validator.scenarios import Bar, generate_all_scenarios
from prompt_validator.simulator import _ema, _sma, _atr, _rsi


# ---------------------------------------------------------------------------
# Constants matching SATVA v15.0.0
# ---------------------------------------------------------------------------

TICK_SIZE = 1
ROUND_STEP = 50
COMPRESSION_WINDOW = 12
ENTROPY_WINDOW = 20
ATR_PREV_WINDOW = 24
FRACTAL_LEN = 2

# Current v15 thresholds
CURRENT_THRESHOLDS = {
    "RCS_min": 65,
    "RCS_full": 70,
    "SES_min": 65,
    "SES_full": 80,
    "TAS_min": 40,
    "TAS_full": 60,
    "MOM_min": 40,
    "MOM_mid": 50,
    "MOM_full": 80,
    "PQS_min": 50,
    "PQS_full": 70,
    "Entropy_good": 40,
    "Entropy_caution": 59,
}

# Current v15 RCS weights
CURRENT_RCS_WEIGHTS = {
    "TAS": 0.25,
    "VOL": 0.15,
    "BEH": 0.15,
    "LVL": 0.15,
    "VOLP": 0.15,
    "TIME": 0.15,
}

# Current v15 SES weights
CURRENT_SES_WEIGHTS = {
    "TRIG": 0.25,
    "STR": 0.25,
    "LVLQ": 0.20,
    "EFF": 0.15,
    "MOM": 0.15,
}


# ---------------------------------------------------------------------------
# Data structures for computed signals
# ---------------------------------------------------------------------------

@dataclass
class BarSignals:
    """All computed SATVA v15 scores for a single bar."""
    bar_idx: int = 0
    price: float = 0.0

    # Core measurements
    atr5m: float = 0.0
    atr_prev: float = 0.0
    rsi_5m: float = 50.0

    # Compression
    overlap_pct: float = 0.0
    contraction: float = 0.0
    volume_slope: float = 0.0
    compression_valid: bool = False

    # Expansion
    expansion_valid: bool = False
    expansion_strong: bool = False

    # Entropy
    entropy_score: float = 100.0

    # 1H derived
    ema_20_1h: float = 0.0
    ema_50_1h: float = 0.0
    slope_1h: float = 0.0
    rsi_1h: float = 50.0

    # 5m EMAs
    ema_9_5m: float = 0.0
    ema_21_5m: float = 0.0

    # VWAP
    vwap: float = 0.0

    # Swing pivots
    last_swing_high: float = 0.0
    last_swing_low: float = 0.0
    prev_swing_high: float = 0.0
    prev_swing_low: float = 0.0

    # PD levels
    pd_high: float = 0.0
    pd_low: float = 0.0
    pd_open: float = 0.0
    pd_close: float = 0.0

    # Volume
    avg_vol_20: float = 0.0
    current_volume: int = 0

    # ABT
    abt_active: bool = False

    # Component scores (0/50/100)
    # TAS components
    tas_htf: int = 0
    tas_exec: int = 0
    tas_total: float = 0.0

    # MOM components
    mom_rsi: int = 0
    mom_div: int = 0
    mom_total: float = 0.0

    # RCS components
    rcs_tas_bin: int = 0
    rcs_vol: int = 0
    rcs_beh: int = 0
    rcs_lvl: int = 0
    rcs_volp: int = 0
    rcs_time: int = 0
    rcs_total: float = 0.0

    # SES components
    ses_trig: int = 0
    ses_str: int = 0
    ses_lvlq: int = 0
    ses_eff: int = 0
    ses_mom: int = 0
    ses_total: float = 0.0

    # PQS components
    pqs_depth: int = 0
    pqs_candle: int = 0
    pqs_vol: int = 0
    pqs_total: float = 0.0
    pqs_applicable: bool = False

    # Regime
    regime: str = "UNCLEAR"

    # Directions possible
    long_signal: bool = False
    short_signal: bool = False
    direction: str = ""  # best direction if any


@dataclass
class TradeOutcome:
    """Labeled outcome for a potential trade entry."""
    entry_bar: int
    direction: str
    entry_price: float
    stop_price: float
    r_trade: float
    outcome: str  # WIN, SMALL_WIN, BREAKEVEN, LOSS
    r_multiple: float
    signals: BarSignals


# ---------------------------------------------------------------------------
# Helper: linear regression slope
# ---------------------------------------------------------------------------

def _linreg_slope(values: list[float]) -> float:
    """Least-squares slope for a series of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = 0.0
    den = 0.0
    for i, y in enumerate(values):
        dx = i - x_mean
        num += dx * (y - y_mean)
        den += dx * dx
    return num / den if den != 0 else 0.0


def _median(values: list[float]) -> float:
    """Median of a list."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


# ---------------------------------------------------------------------------
# 1. Full SATVA v15 Signal Generator
# ---------------------------------------------------------------------------

def compute_signals(bars: list[Bar]) -> list[BarSignals]:
    """Compute ALL SATVA v15 scores at each bar.

    Parameters
    ----------
    bars : list[Bar]
        5-minute OHLCV bars (at least 120 recommended).

    Returns
    -------
    list[BarSignals]
        One BarSignals per bar (early bars may have incomplete data).
    """
    n = len(bars)
    if n < 30:
        return [BarSignals(bar_idx=i, price=b.close) for i, b in enumerate(bars)]

    # -- Pre-compute indicator series --
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [float(b.volume) for b in bars]
    bodies = [abs(b.close - b.open) for b in bars]
    ranges_ = [max(b.high - b.low, TICK_SIZE) for b in bars]

    atr_series = _atr(bars, 14)
    rsi_series = _rsi(closes, 14)
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    vol_sma20 = _sma(volumes, 20)

    # 1H aggregation: every 12 bars
    h1_closes: list[float] = []
    h1_highs: list[float] = []
    h1_lows: list[float] = []
    h1_bar_map: list[int] = []  # which 1H bar index each 5m bar maps to
    for i in range(n):
        bucket = i // 12
        h1_bar_map.append(bucket)
        if (i + 1) % 12 == 0 or i == n - 1:
            start = bucket * 12
            end = i + 1
            h1_closes.append(closes[i])
            h1_highs.append(max(highs[start:end]))
            h1_lows.append(min(lows[start:end]))

    ema20_1h = _ema(h1_closes, 20) if len(h1_closes) >= 20 else [0.0] * len(h1_closes)
    ema50_1h = _ema(h1_closes, 50) if len(h1_closes) >= 50 else [0.0] * len(h1_closes)
    rsi_1h = _rsi(h1_closes, 14) if len(h1_closes) >= 15 else [50.0] * len(h1_closes)
    have_1h = len(h1_closes) >= 50

    # PD levels: use first 24 bars as "previous day"
    pd_high = max(highs[:24]) if n >= 24 else max(highs)
    pd_low = min(lows[:24]) if n >= 24 else min(lows)
    pd_open = bars[0].open
    pd_close = bars[min(23, n - 1)].close

    # VWAP: running calculation (cumulative typical_price * volume / cumulative volume)
    vwap_series = [0.0] * n
    cum_tpv = 0.0
    cum_vol = 0.0
    for i in range(n):
        tp = (bars[i].high + bars[i].low + bars[i].close) / 3.0
        cum_tpv += tp * bars[i].volume
        cum_vol += bars[i].volume
        vwap_series[i] = cum_tpv / cum_vol if cum_vol > 0 else closes[i]

    # Swing pivots (fractal length=2)
    swing_highs: list[Tuple[int, float]] = []
    swing_lows: list[Tuple[int, float]] = []
    for i in range(FRACTAL_LEN, n - FRACTAL_LEN):
        is_sh = all(highs[i] > highs[i - j] for j in range(1, FRACTAL_LEN + 1)) and \
                all(highs[i] > highs[i + j] for j in range(1, FRACTAL_LEN + 1))
        is_sl = all(lows[i] < lows[i - j] for j in range(1, FRACTAL_LEN + 1)) and \
                all(lows[i] < lows[i + j] for j in range(1, FRACTAL_LEN + 1))
        if is_sh:
            swing_highs.append((i, highs[i]))
        if is_sl:
            swing_lows.append((i, lows[i]))

    # Build level set L for each bar
    def _get_levels(bar_idx: int) -> list[float]:
        levels = [pd_open, pd_high, pd_low, pd_close, vwap_series[bar_idx]]
        price = closes[bar_idx]
        atr = atr_series[bar_idx] if atr_series[bar_idx] > 0 else 1.0
        low_round = int((price - 2 * atr) / ROUND_STEP) * ROUND_STEP
        high_round = int((price + 2 * atr) / ROUND_STEP + 1) * ROUND_STEP
        for r in range(low_round, high_round + ROUND_STEP, ROUND_STEP):
            if r > 0:
                levels.append(float(r))
        return levels

    def _nearest_level(price: float, levels: list[float], vwap: float) -> float:
        if not levels:
            return price
        best = min(levels, key=lambda lv: (abs(price - lv), abs(lv - vwap)))
        return best

    # -- Compute per-bar signals --
    results: list[BarSignals] = []
    for i in range(n):
        sig = BarSignals()
        sig.bar_idx = i
        sig.price = closes[i]
        sig.atr5m = atr_series[i]
        sig.rsi_5m = rsi_series[i]
        sig.ema_9_5m = ema9[i]
        sig.ema_21_5m = ema21[i]
        sig.vwap = vwap_series[i]
        sig.pd_high = pd_high
        sig.pd_low = pd_low
        sig.pd_open = pd_open
        sig.pd_close = pd_close
        sig.current_volume = bars[i].volume
        sig.avg_vol_20 = vol_sma20[i]

        # ATR_prev = mean ATR over prior 24 bars
        if i >= ATR_PREV_WINDOW:
            sig.atr_prev = sum(atr_series[i - ATR_PREV_WINDOW:i]) / ATR_PREV_WINDOW
        else:
            sig.atr_prev = sig.atr5m

        # 1H values
        h1_idx = min(h1_bar_map[i], len(h1_closes) - 1)
        if have_1h and h1_idx < len(ema20_1h):
            sig.ema_20_1h = ema20_1h[h1_idx]
            sig.ema_50_1h = ema50_1h[h1_idx]
            sig.slope_1h = sig.ema_20_1h - sig.ema_50_1h
            sig.rsi_1h = rsi_1h[h1_idx]
        else:
            sig.slope_1h = 0.0

        # Swing pivots confirmed at i (confirmed after i+2, so available if pivot_bar + 2 <= i)
        confirmed_sh = [(idx, val) for idx, val in swing_highs if idx + FRACTAL_LEN <= i]
        confirmed_sl = [(idx, val) for idx, val in swing_lows if idx + FRACTAL_LEN <= i]
        if len(confirmed_sh) >= 2:
            sig.last_swing_high = confirmed_sh[-1][1]
            sig.prev_swing_high = confirmed_sh[-2][1]
        elif len(confirmed_sh) == 1:
            sig.last_swing_high = confirmed_sh[-1][1]
            sig.prev_swing_high = confirmed_sh[-1][1]
        if len(confirmed_sl) >= 2:
            sig.last_swing_low = confirmed_sl[-1][1]
            sig.prev_swing_low = confirmed_sl[-2][1]
        elif len(confirmed_sl) == 1:
            sig.last_swing_low = confirmed_sl[-1][1]
            sig.prev_swing_low = confirmed_sl[-1][1]

        # ---- Compression (Section 8) ----
        if i >= COMPRESSION_WINDOW - 1:
            window_bars = bars[i - COMPRESSION_WINDOW + 1:i + 1]
            w_highs = [b.high for b in window_bars]
            w_lows = [b.low for b in window_bars]
            overlap_range = min(w_highs) - max(w_lows)
            if overlap_range < 0:
                overlap_range = 0.0
            median_range = _median([b.high - b.low for b in window_bars])
            sig.overlap_pct = overlap_range / median_range if median_range > 0 else 0.0
            sig.contraction = sig.atr5m / sig.atr_prev if sig.atr_prev > 0 else 1.0
            w_volumes = [float(b.volume) for b in window_bars]
            sig.volume_slope = _linreg_slope(w_volumes)
            sig.compression_valid = (
                sig.overlap_pct >= 0.60
                and sig.contraction <= 0.85
                and sig.volume_slope <= 0
            )

        # ---- Expansion (Section 9) ----
        if i >= 10:
            avg_body_10 = sum(bodies[i - 9:i + 1]) / 10.0
            tr_i = max(bars[i].high - bars[i].low,
                       abs(bars[i].high - bars[max(0, i - 1)].close),
                       abs(bars[i].low - bars[max(0, i - 1)].close))
            vol_cond_valid = tr_i >= 1.2 * sig.atr5m or bars[i].volume >= vol_sma20[i]
            body_cond_valid = bodies[i] >= 1.2 * avg_body_10 if avg_body_10 > 0 else False
            sig.expansion_valid = vol_cond_valid and body_cond_valid

            vol_cond_strong = tr_i >= 1.4 * sig.atr5m or bars[i].volume >= 1.4 * vol_sma20[i]
            body_cond_strong = bodies[i] >= 1.4 * avg_body_10 if avg_body_10 > 0 else False
            sig.expansion_strong = vol_cond_strong and body_cond_strong

        # ---- Entropy (Section 10) ----
        if i >= ENTROPY_WINDOW - 1:
            indecision_count = 0
            for j in range(i - ENTROPY_WINDOW + 1, i + 1):
                bar_range = max(bars[j].high - bars[j].low, TICK_SIZE)
                body_j = abs(bars[j].close - bars[j].open)
                is_indecision = False
                # small body vs range
                if body_j <= 0.25 * bar_range:
                    is_indecision = True
                # inside bar
                if j > 0 and bars[j].high <= bars[j - 1].high and bars[j].low >= bars[j - 1].low:
                    is_indecision = True
                # doji-like
                if sig.atr5m > 0 and body_j <= 0.15 * sig.atr5m:
                    is_indecision = True
                if is_indecision:
                    indecision_count += 1
            sig.entropy_score = 100.0 * indecision_count / ENTROPY_WINDOW

        # ---- ABT (Section 6) ----
        if i >= 3:
            abt_triggered = False
            for j in range(max(0, i - 2), i + 1):
                tr_j = max(bars[j].high - bars[j].low,
                           abs(bars[j].high - bars[max(0, j - 1)].close),
                           abs(bars[j].low - bars[max(0, j - 1)].close))
                if sig.atr5m > 0:
                    if tr_j >= 2.2 * sig.atr5m:
                        abt_triggered = True
                    if (bars[j].high - bars[j].low) >= 2.2 * sig.atr5m:
                        abt_triggered = True
                if vol_sma20[j] > 0 and bars[j].volume >= 2.5 * vol_sma20[j]:
                    abt_triggered = True
            sig.abt_active = abt_triggered

        # ---- VOL (RCS.VOL) Section 11.1 ----
        if i >= 20:
            atr_clean = []
            for j in range(i - 19, i + 1):
                tr_j = max(bars[j].high - bars[j].low,
                           abs(bars[j].high - bars[max(0, j - 1)].close),
                           abs(bars[j].low - bars[max(0, j - 1)].close))
                if sig.atr5m > 0 and tr_j < 2.2 * sig.atr5m:
                    atr_clean.append(atr_series[j])
            if len(atr_clean) >= 2:
                vstab = statistics.stdev(atr_clean) / statistics.mean(atr_clean) if statistics.mean(atr_clean) > 0 else 1.0
            else:
                vstab = 1.0
        else:
            vstab = 0.5

        # Compute for both directions, pick best later
        for direction in ("LONG", "SHORT"):
            if direction == "LONG":
                pb_depth = (sig.last_swing_high - closes[i]) if sig.last_swing_high > closes[i] else 0.0
            else:
                pb_depth = (closes[i] - sig.last_swing_low) if closes[i] > sig.last_swing_low else 0.0
            pb_norm = pb_depth / sig.atr5m if sig.atr5m > 0 else 0.0

            if vstab <= 0.12 and pb_norm <= 1.0:
                vol_bin = 100
            elif vstab <= 0.20 and pb_norm <= 1.3:
                vol_bin = 50
            else:
                vol_bin = 0

            # ---- TAS (Section 12) ----
            price_vs_vwap = 1 if closes[i] > vwap_series[i] else (-1 if closes[i] < vwap_series[i] else 0)

            if have_1h:
                slope_aligns = (sig.slope_1h > 0 and direction == "LONG") or \
                               (sig.slope_1h < 0 and direction == "SHORT")
                vwap_aligns = (price_vs_vwap == 1 and direction == "LONG") or \
                              (price_vs_vwap == -1 and direction == "SHORT")
                if slope_aligns and vwap_aligns:
                    htf_bin = 100
                elif slope_aligns or vwap_aligns:
                    htf_bin = 50
                else:
                    htf_bin = 0
            else:
                htf_bin = 0

            # 5m exec layer
            if direction == "LONG":
                trigger_5m = ema9[i] > ema21[i] and rsi_series[i] > 40
            else:
                trigger_5m = ema9[i] < ema21[i] and rsi_series[i] < 60
            exec_bin = 100 if trigger_5m else 0

            tas_val = 0.60 * htf_bin + 0.40 * exec_bin

            # ---- MOM (Section 13) ----
            if direction == "LONG":
                rsi_in_range = 40 <= rsi_series[i] <= 70
                # "moving toward direction" approximation: RSI increasing
                rsi_moving = rsi_series[i] > rsi_series[max(0, i - 1)] if i > 0 else False
            else:
                rsi_in_range = 30 <= rsi_series[i] <= 60
                rsi_moving = rsi_series[i] < rsi_series[max(0, i - 1)] if i > 0 else False

            if rsi_in_range and rsi_moving:
                mom_rsi_bin = 100
            elif rsi_in_range:
                mom_rsi_bin = 50
            else:
                mom_rsi_bin = 0

            # Divergence detection (simplified over last 40 bars)
            mom_div_val = 0
            if i >= 40:
                price_window = closes[i - 39:i + 1]
                rsi_window = rsi_series[i - 39:i + 1]
                price_ll = closes[i] < min(price_window[:-1])
                rsi_hl = rsi_series[i] > min(rsi_window[:-1])
                price_hh = closes[i] > max(price_window[:-1])
                rsi_lh = rsi_series[i] < max(rsi_window[:-1])
                if direction == "SHORT" and price_ll and rsi_hl:
                    mom_div_val = -50  # bull div while short candidate
                elif direction == "LONG" and price_hh and rsi_lh:
                    mom_div_val = -50  # bear div while long candidate

            mom_val = max(0, mom_rsi_bin + mom_div_val)

            # ---- BEH (Section 16.3) ----
            if i >= 10:
                body_ratio = sum(
                    abs(bars[j].close - bars[j].open) / max(bars[j].high - bars[j].low, TICK_SIZE)
                    for j in range(i - 9, i + 1)
                ) / 10.0
            else:
                body_ratio = 0.5

            if body_ratio >= 0.55:
                beh_bin = 100
            elif body_ratio >= 0.45:
                beh_bin = 50
            else:
                beh_bin = 0

            # ---- LVL (Section 16.4) ----
            levels = _get_levels(i)
            chop_count = 0
            if i >= 24:
                for j in range(i - 23, i + 1):
                    for lv in levels:
                        crosses = (bars[j].low < lv < bars[j].high)
                        if crosses:
                            # closes on opposite side
                            if (bars[j].open < lv and bars[j].close > lv) or \
                               (bars[j].open > lv and bars[j].close < lv):
                                chop_count += 1
                                break
            if chop_count <= 1:
                lvl_bin = 100
            elif chop_count <= 3:
                lvl_bin = 50
            else:
                lvl_bin = 0

            # ---- VOLP (Section 14) ----
            vol_expanding = bars[i].volume > 1.2 * vol_sma20[i] if vol_sma20[i] > 0 else False
            vol_dryup = False
            if i >= 2 and vol_sma20[i] > 0:
                vol_dryup = all(
                    bars[i - k].volume < 0.5 * vol_sma20[i] for k in range(3)
                )
            # VP divergence
            vp_div_against = False
            if i >= 6:
                price_slope = _linreg_slope(closes[i - 5:i + 1])
                vol_slope_6 = _linreg_slope(volumes[i - 5:i + 1])
                if direction == "LONG" and price_slope > 0 and vol_slope_6 < 0:
                    vp_div_against = True
                if direction == "SHORT" and price_slope < 0 and vol_slope_6 < 0:
                    vp_div_against = True

            if vol_expanding and not vp_div_against:
                volp_bin = 100
            elif not vol_dryup and not vp_div_against:
                volp_bin = 50
            else:
                volp_bin = 0

            # ---- TIME (Section 16.6) ----
            # Simulate time based on bar index within a session (~174 bars per session)
            bars_per_session = 174
            bar_in_session = i % bars_per_session
            if 4 <= bar_in_session <= 138:  # 09:20-20:30
                time_bin = 100
            elif 138 < bar_in_session <= 162:  # 20:30-22:30
                time_bin = 50
            else:
                time_bin = 0

            # ---- RCS (Section 16) ----
            if tas_val >= 60:
                rcs_tas_bin = 100
            elif tas_val >= 40:
                rcs_tas_bin = 50
            else:
                rcs_tas_bin = 0

            rcs_val = (0.25 * rcs_tas_bin + 0.15 * vol_bin + 0.15 * beh_bin +
                       0.15 * lvl_bin + 0.15 * volp_bin + 0.15 * time_bin)

            # ---- SES components ----
            # TRIG
            if sig.expansion_strong:
                trig_bin = 100
            elif sig.expansion_valid:
                trig_bin = 50
            else:
                trig_bin = 0

            # STR (structure quality)
            if direction == "LONG":
                hh = sig.last_swing_high > sig.prev_swing_high if sig.prev_swing_high > 0 else False
                hl = sig.last_swing_low > sig.prev_swing_low if sig.prev_swing_low > 0 else False
            else:
                hh = sig.last_swing_low < sig.prev_swing_low if sig.prev_swing_low > 0 else False
                hl = sig.last_swing_high < sig.prev_swing_high if sig.prev_swing_high > 0 else False

            # DualViolation
            dual_violation = False
            if i >= 12 and len(confirmed_sh) >= 1 and len(confirmed_sl) >= 1:
                recent_sh = confirmed_sh[-1][1]
                recent_sl = confirmed_sl[-1][1]
                for j in range(max(0, i - 11), i + 1):
                    above_sh = bars[j].close > recent_sh
                    below_sl = bars[j].close < recent_sl
                    if above_sh:
                        for k in range(max(0, i - 11), i + 1):
                            if bars[k].close < recent_sl:
                                dual_violation = True
                                break
                    if dual_violation:
                        break

            if dual_violation:
                str_bin = 0
            elif hh and hl:
                str_bin = 100
            elif hh or hl:
                str_bin = 50
            else:
                str_bin = 0

            # LVLQ
            nearest = _nearest_level(closes[i], levels, vwap_series[i])
            dist = abs(closes[i] - nearest)
            atr_for_lvlq = sig.atr5m if sig.atr5m > 0 else 1.0
            if dist <= 0.25 * atr_for_lvlq:
                lvlq_bin = 100
            elif dist <= 0.50 * atr_for_lvlq:
                lvlq_bin = 50
            else:
                lvlq_bin = 0

            # EFF (stop efficiency) - estimate stop distance
            if direction == "LONG":
                stop_price = sig.last_swing_low if sig.last_swing_low > 0 else closes[i] - sig.atr5m
            else:
                stop_price = sig.last_swing_high if sig.last_swing_high > 0 else closes[i] + sig.atr5m
            stop_dist = abs(closes[i] - stop_price)
            eff_ratio = stop_dist / sig.atr5m if sig.atr5m > 0 else 2.0

            if eff_ratio <= 1.0:
                eff_bin = 100
            elif eff_ratio <= 1.3:
                eff_bin = 50
            else:
                eff_bin = 0

            # MOM bin for SES
            if mom_val >= 80:
                ses_mom_bin = 100
            elif mom_val >= 40:
                ses_mom_bin = 50
            else:
                ses_mom_bin = 0

            ses_val = (0.25 * trig_bin + 0.25 * str_bin + 0.20 * lvlq_bin +
                       0.15 * eff_bin + 0.15 * ses_mom_bin)

            # ---- PQS (Section 15) ----
            pqs_applicable = False
            pqs_val = 0.0
            pqs_depth_bin = 0
            pqs_candle_bin = 0
            pqs_vol_bin = 0
            if pb_norm >= 0.3:  # pullback detected
                pqs_applicable = True
                if 0.5 <= pb_norm <= 1.5:
                    pqs_depth_bin = 100
                elif pb_norm <= 2.0 or (0.3 <= pb_norm < 0.5):
                    pqs_depth_bin = 50
                else:
                    pqs_depth_bin = 0

                # Candle count in pullback (approximation: bars since swing)
                if direction == "LONG" and len(confirmed_sh) >= 1:
                    pb_bars = i - confirmed_sh[-1][0]
                elif direction == "SHORT" and len(confirmed_sl) >= 1:
                    pb_bars = i - confirmed_sl[-1][0]
                else:
                    pb_bars = 0
                if 3 <= pb_bars <= 5:
                    pqs_candle_bin = 100
                elif pb_bars == 2 or 6 <= pb_bars <= 7:
                    pqs_candle_bin = 50
                else:
                    pqs_candle_bin = 0

                # Volume contraction during pullback
                if pb_bars > 0 and vol_sma20[i] > 0:
                    pb_start = max(0, i - pb_bars)
                    mean_pb_vol = sum(volumes[pb_start:i + 1]) / max(1, i + 1 - pb_start)
                    if mean_pb_vol < 0.8 * vol_sma20[i]:
                        pqs_vol_bin = 100
                    elif mean_pb_vol < vol_sma20[i]:
                        pqs_vol_bin = 50
                    else:
                        pqs_vol_bin = 0

                pqs_val = 0.40 * pqs_depth_bin + 0.30 * pqs_candle_bin + 0.30 * pqs_vol_bin

            # ---- Regime (Section 17) ----
            if sig.abt_active or vol_bin == 0:
                regime = "SHOCK"
            elif sig.compression_valid and not sig.expansion_valid and sig.entropy_score <= 40:
                regime = "RANGE"
            elif sig.expansion_strong and tas_val >= 60 and sig.entropy_score <= 40 and rcs_val >= 70:
                regime = "STRONG_TREND"
            elif sig.expansion_valid and sig.entropy_score <= 40 and rcs_val >= 65:
                regime = "TREND"
            elif sig.entropy_score <= 59 or 65 <= rcs_val <= 69:
                regime = "UNCLEAR"
            else:
                regime = "UNCLEAR"

            # Decide if this direction produces a better signal
            is_better = False
            if direction == "LONG":
                sig.long_signal = (
                    rcs_val >= 65 and ses_val >= 65 and
                    tas_val >= 40 and not sig.abt_active and
                    sig.entropy_score <= 59 and time_bin > 0
                )
                is_better = sig.long_signal
            else:
                sig.short_signal = (
                    rcs_val >= 65 and ses_val >= 65 and
                    tas_val >= 40 and not sig.abt_active and
                    sig.entropy_score <= 59 and time_bin > 0
                )
                is_better = sig.short_signal and not sig.long_signal

            if is_better or direction == "LONG":
                # Store first pass (LONG), overwrite only if SHORT is better
                if direction == "LONG" or (direction == "SHORT" and rcs_val > sig.rcs_total):
                    sig.tas_htf = htf_bin
                    sig.tas_exec = exec_bin
                    sig.tas_total = tas_val
                    sig.mom_rsi = mom_rsi_bin
                    sig.mom_div = mom_div_val
                    sig.mom_total = mom_val
                    sig.rcs_tas_bin = rcs_tas_bin
                    sig.rcs_vol = vol_bin
                    sig.rcs_beh = beh_bin
                    sig.rcs_lvl = lvl_bin
                    sig.rcs_volp = volp_bin
                    sig.rcs_time = time_bin
                    sig.rcs_total = rcs_val
                    sig.ses_trig = trig_bin
                    sig.ses_str = str_bin
                    sig.ses_lvlq = lvlq_bin
                    sig.ses_eff = eff_bin
                    sig.ses_mom = ses_mom_bin
                    sig.ses_total = ses_val
                    sig.pqs_depth = pqs_depth_bin
                    sig.pqs_candle = pqs_candle_bin
                    sig.pqs_vol = pqs_vol_bin
                    sig.pqs_total = pqs_val
                    sig.pqs_applicable = pqs_applicable
                    sig.regime = regime
                    sig.direction = direction

        results.append(sig)

    return results


# ---------------------------------------------------------------------------
# 2. Forward-Looking Labeler
# ---------------------------------------------------------------------------

def label_outcomes(
    bars: list[Bar],
    entry_bar: int,
    direction: str,
    atr: float,
) -> TradeOutcome:
    """Simulate next 30 bars from entry and label the outcome.

    Returns
    -------
    TradeOutcome with outcome in {WIN, SMALL_WIN, BREAKEVEN, LOSS}
    and actual R-multiple achieved.
    """
    entry_price = bars[entry_bar].close
    if atr <= 0:
        atr = max(abs(bars[entry_bar].high - bars[entry_bar].low), TICK_SIZE)

    r_trade = atr  # 1R = 1 ATR (stop distance approximation)
    if direction == "LONG":
        stop = entry_price - r_trade
        t1 = entry_price + 1.0 * r_trade
        t15 = entry_price + 1.5 * r_trade
    else:
        stop = entry_price + r_trade
        t1 = entry_price - 1.0 * r_trade
        t15 = entry_price - 1.5 * r_trade

    best_r = 0.0
    exit_r = 0.0
    outcome = "BREAKEVEN"
    hit_stop = False
    hit_t1 = False
    hit_t15 = False

    end_bar = min(entry_bar + 30, len(bars) - 1)
    for j in range(entry_bar + 1, end_bar + 1):
        if direction == "LONG":
            # Check stop
            if bars[j].low <= stop:
                hit_stop = True
                exit_r = -1.0
                break
            # Check favorable
            excursion = bars[j].high - entry_price
            r_now = excursion / r_trade
            if r_now > best_r:
                best_r = r_now
            if bars[j].high >= t15:
                hit_t15 = True
                exit_r = 1.5
                break
            if bars[j].high >= t1:
                hit_t1 = True
        else:
            if bars[j].high >= stop:
                hit_stop = True
                exit_r = -1.0
                break
            excursion = entry_price - bars[j].low
            r_now = excursion / r_trade
            if r_now > best_r:
                best_r = r_now
            if bars[j].low <= t15:
                hit_t15 = True
                exit_r = 1.5
                break
            if bars[j].low <= t1:
                hit_t1 = True

    if hit_stop:
        outcome = "LOSS"
        exit_r = -1.0
    elif hit_t15:
        outcome = "WIN"
        exit_r = 1.5
    elif hit_t1:
        outcome = "SMALL_WIN"
        exit_r = 1.0
    else:
        # Exited at end of window
        if direction == "LONG":
            exit_r = (bars[end_bar].close - entry_price) / r_trade
        else:
            exit_r = (entry_price - bars[end_bar].close) / r_trade
        if exit_r >= 1.0:
            outcome = "SMALL_WIN"
        elif exit_r > 0.1:
            outcome = "BREAKEVEN"
        else:
            outcome = "LOSS"

    return TradeOutcome(
        entry_bar=entry_bar,
        direction=direction,
        entry_price=entry_price,
        stop_price=stop,
        r_trade=r_trade,
        outcome=outcome,
        r_multiple=exit_r,
        signals=BarSignals(),  # placeholder, filled by caller
    )


# ---------------------------------------------------------------------------
# 3. Threshold Grid Search
# ---------------------------------------------------------------------------

def _collect_labeled_signals(n_bars: int = 500) -> list[Tuple[BarSignals, TradeOutcome]]:
    """Generate scenarios, compute signals, and label every potential trade."""
    scenarios = generate_all_scenarios(n=n_bars)
    all_pairs: list[Tuple[BarSignals, TradeOutcome]] = []

    for scenario in scenarios:
        bars = scenario.bars
        signals = compute_signals(bars)
        for i, sig in enumerate(signals):
            if i < 30 or i >= len(bars) - 31:
                continue
            for direction in ("LONG", "SHORT"):
                outcome = label_outcomes(bars, i, direction, sig.atr5m)
                outcome.signals = sig
                outcome.direction = direction
                all_pairs.append((sig, outcome))

    return all_pairs


def _passes_gates(
    sig: BarSignals,
    direction: str,
    rcs_min: float,
    ses_min: float,
    tas_min: float,
    mom_min: float,
    pqs_min: float,
    entropy_max: float,
) -> bool:
    """Check if a signal passes all gates with the given thresholds."""
    if sig.abt_active:
        return False
    if sig.rcs_time == 0:
        return False
    if sig.entropy_score > entropy_max:
        return False
    if sig.rcs_total < rcs_min:
        return False
    if sig.ses_total < ses_min:
        return False
    if sig.tas_total < tas_min:
        return False
    if sig.mom_total < mom_min:
        return False
    if sig.pqs_applicable and sig.pqs_total < pqs_min:
        return False
    return True


def optimize_gates(n_bars: int = 500) -> dict:
    """Grid search over gate thresholds to maximize expectancy.

    Returns
    -------
    dict with keys: best_thresholds, pareto_frontier, current_performance
    """
    print("  Collecting labeled signals...")
    pairs = _collect_labeled_signals(n_bars)
    print(f"  Total signal-outcome pairs: {len(pairs)}")

    rcs_vals = [50, 55, 60, 65, 70, 75, 80]
    ses_vals = [50, 55, 60, 65, 70, 75, 80, 85]
    tas_vals = [20, 30, 40, 50, 60, 70]
    mom_vals = [20, 30, 40, 50, 60, 70]
    pqs_vals = [30, 40, 50, 60, 70, 80]
    entropy_vals = [30, 35, 40, 45, 50, 55, 60]

    best_expectancy = -999.0
    best_combo = None
    pareto: list[dict] = []

    # Evaluate current thresholds first
    current_trades = []
    for sig, outcome in pairs:
        if _passes_gates(sig, outcome.direction,
                         CURRENT_THRESHOLDS["RCS_min"],
                         CURRENT_THRESHOLDS["SES_min"],
                         CURRENT_THRESHOLDS["TAS_min"],
                         CURRENT_THRESHOLDS["MOM_min"],
                         CURRENT_THRESHOLDS["PQS_min"],
                         CURRENT_THRESHOLDS["Entropy_caution"]):
            current_trades.append(outcome)

    current_n = len(current_trades)
    current_wins = sum(1 for t in current_trades if t.outcome in ("WIN", "SMALL_WIN"))
    current_wr = current_wins / current_n * 100 if current_n > 0 else 0
    current_exp = sum(t.r_multiple for t in current_trades) / current_n if current_n > 0 else 0

    current_perf = {
        "trades": current_n,
        "win_rate": round(current_wr, 2),
        "expectancy": round(current_exp, 4),
    }

    # Grid search — sample to keep runtime reasonable
    # Instead of full cartesian product (huge), do coordinate descent
    print("  Running coordinate descent optimization...")
    best = {
        "RCS": CURRENT_THRESHOLDS["RCS_min"],
        "SES": CURRENT_THRESHOLDS["SES_min"],
        "TAS": CURRENT_THRESHOLDS["TAS_min"],
        "MOM": CURRENT_THRESHOLDS["MOM_min"],
        "PQS": CURRENT_THRESHOLDS["PQS_min"],
        "Entropy": CURRENT_THRESHOLDS["Entropy_caution"],
    }

    improved = True
    iteration = 0
    while improved and iteration < 5:
        improved = False
        iteration += 1

        for gate_name, test_values in [
            ("RCS", rcs_vals),
            ("SES", ses_vals),
            ("TAS", tas_vals),
            ("MOM", mom_vals),
            ("PQS", pqs_vals),
            ("Entropy", entropy_vals),
        ]:
            best_gate_exp = -999.0
            best_gate_val = best[gate_name]

            for val in test_values:
                test = dict(best)
                test[gate_name] = val

                trades = []
                for sig, outcome in pairs:
                    if _passes_gates(sig, outcome.direction,
                                     test["RCS"], test["SES"], test["TAS"],
                                     test["MOM"], test["PQS"], test["Entropy"]):
                        trades.append(outcome)

                if len(trades) < 5:
                    continue

                exp = sum(t.r_multiple for t in trades) / len(trades)
                wins = sum(1 for t in trades if t.outcome in ("WIN", "SMALL_WIN"))
                wr = wins / len(trades) * 100

                # Pareto candidate: track if interesting
                pareto.append({
                    "thresholds": dict(test),
                    "trades": len(trades),
                    "win_rate": round(wr, 2),
                    "expectancy": round(exp, 4),
                })

                if exp > best_gate_exp:
                    best_gate_exp = exp
                    best_gate_val = val

            if best_gate_val != best[gate_name]:
                best[gate_name] = best_gate_val
                improved = True

    # Evaluate final best
    final_trades = []
    for sig, outcome in pairs:
        if _passes_gates(sig, outcome.direction,
                         best["RCS"], best["SES"], best["TAS"],
                         best["MOM"], best["PQS"], best["Entropy"]):
            final_trades.append(outcome)

    final_n = len(final_trades)
    final_wins = sum(1 for t in final_trades if t.outcome in ("WIN", "SMALL_WIN"))
    final_wr = final_wins / final_n * 100 if final_n > 0 else 0
    final_exp = sum(t.r_multiple for t in final_trades) / final_n if final_n > 0 else 0

    # Build Pareto frontier (non-dominated points by expectancy and trade count)
    pareto.sort(key=lambda p: (-p["expectancy"], -p["trades"]))
    frontier = []
    max_trades_seen = 0
    for p in pareto:
        if p["trades"] > max_trades_seen:
            max_trades_seen = p["trades"]
            frontier.append(p)
    frontier = frontier[:10]

    return {
        "best_thresholds": best,
        "best_performance": {
            "trades": final_n,
            "win_rate": round(final_wr, 2),
            "expectancy": round(final_exp, 4),
        },
        "current_performance": current_perf,
        "pareto_frontier": frontier,
        "iterations": iteration,
    }


# ---------------------------------------------------------------------------
# 4. Weight Optimizer
# ---------------------------------------------------------------------------

def optimize_weights() -> dict:
    """Test different weight distributions for RCS and SES components.

    Current RCS: TAS 25% | VOL 15% | BEH 15% | LVL 15% | VOLP 15% | TIME 15%
    Test variations: +/-5% on each component (keeping sum = 100%).

    Returns
    -------
    dict with best_rcs_weights, best_ses_weights, and separation metrics.
    """
    print("  Collecting labeled signals for weight optimization...")
    pairs = _collect_labeled_signals(n_bars=300)

    winners = [(sig, out) for sig, out in pairs
               if out.outcome in ("WIN", "SMALL_WIN") and out.r_multiple > 0]
    losers = [(sig, out) for sig, out in pairs
              if out.outcome == "LOSS"]

    print(f"  Winners: {len(winners)}, Losers: {len(losers)}")

    # --- RCS weight optimization ---
    rcs_components = ["TAS", "VOL", "BEH", "LVL", "VOLP", "TIME"]
    base_rcs = [0.25, 0.15, 0.15, 0.15, 0.15, 0.15]

    def _rcs_score(sig: BarSignals, weights: list[float]) -> float:
        vals = [sig.rcs_tas_bin, sig.rcs_vol, sig.rcs_beh,
                sig.rcs_lvl, sig.rcs_volp, sig.rcs_time]
        return sum(w * v for w, v in zip(weights, vals))

    def _ses_score(sig: BarSignals, weights: list[float]) -> float:
        vals = [sig.ses_trig, sig.ses_str, sig.ses_lvlq,
                sig.ses_eff, sig.ses_mom]
        return sum(w * v for w, v in zip(weights, vals))

    def _separation_score(
        winners: list, losers: list, score_fn, weights: list[float]
    ) -> float:
        """Higher is better: measures how well the score separates wins from losses."""
        if not winners or not losers:
            return 0.0
        win_scores = [score_fn(sig, weights) for sig, _ in winners]
        loss_scores = [score_fn(sig, weights) for sig, _ in losers]
        win_mean = sum(win_scores) / len(win_scores)
        loss_mean = sum(loss_scores) / len(loss_scores)
        # Pooled stddev
        all_scores = win_scores + loss_scores
        overall_std = statistics.stdev(all_scores) if len(all_scores) > 1 else 1.0
        return (win_mean - loss_mean) / overall_std if overall_std > 0 else 0.0

    # Generate weight perturbations for RCS
    best_rcs_sep = _separation_score(winners, losers, _rcs_score, base_rcs)
    best_rcs_weights = list(base_rcs)

    step = 0.05
    for target_idx in range(len(rcs_components)):
        for donor_idx in range(len(rcs_components)):
            if target_idx == donor_idx:
                continue
            candidate = list(best_rcs_weights)
            candidate[target_idx] += step
            candidate[donor_idx] -= step
            if min(candidate) < 0.05:
                continue
            sep = _separation_score(winners, losers, _rcs_score, candidate)
            if sep > best_rcs_sep:
                best_rcs_sep = sep
                best_rcs_weights = candidate

    # --- SES weight optimization ---
    ses_components = ["TRIG", "STR", "LVLQ", "EFF", "MOM"]
    base_ses = [0.25, 0.25, 0.20, 0.15, 0.15]

    best_ses_sep = _separation_score(winners, losers, _ses_score, base_ses)
    best_ses_weights = list(base_ses)

    for target_idx in range(len(ses_components)):
        for donor_idx in range(len(ses_components)):
            if target_idx == donor_idx:
                continue
            candidate = list(best_ses_weights)
            candidate[target_idx] += step
            candidate[donor_idx] -= step
            if min(candidate) < 0.05:
                continue
            sep = _separation_score(winners, losers, _ses_score, candidate)
            if sep > best_ses_sep:
                best_ses_sep = sep
                best_ses_weights = candidate

    return {
        "rcs": {
            "current_weights": dict(zip(rcs_components, base_rcs)),
            "optimal_weights": dict(zip(rcs_components, [round(w, 2) for w in best_rcs_weights])),
            "current_separation": round(best_rcs_sep if best_rcs_weights == base_rcs else
                                        _separation_score(winners, losers, _rcs_score, base_rcs), 4),
            "optimal_separation": round(best_rcs_sep, 4),
        },
        "ses": {
            "current_weights": dict(zip(ses_components, base_ses)),
            "optimal_weights": dict(zip(ses_components, [round(w, 2) for w in best_ses_weights])),
            "current_separation": round(best_ses_sep if best_ses_weights == base_ses else
                                        _separation_score(winners, losers, _ses_score, base_ses), 4),
            "optimal_separation": round(best_ses_sep, 4),
        },
    }


# ---------------------------------------------------------------------------
# 5. Component Contribution Analysis
# ---------------------------------------------------------------------------

def analyze_components() -> dict:
    """Analyze each RCS/SES component's predictive value.

    Measures:
    - Correlation with trade outcome
    - Information value (does 100 predict better than 50?)
    - Redundancy (correlation between components)
    """
    print("  Collecting labeled signals for component analysis...")
    pairs = _collect_labeled_signals(n_bars=300)
    if not pairs:
        return {"error": "No pairs generated"}

    # Encode outcome: 1 for win, 0 for loss
    outcomes = []
    component_values: Dict[str, list[int]] = {
        "RCS.TAS": [], "RCS.VOL": [], "RCS.BEH": [],
        "RCS.LVL": [], "RCS.VOLP": [], "RCS.TIME": [],
        "SES.TRIG": [], "SES.STR": [], "SES.LVLQ": [],
        "SES.EFF": [], "SES.MOM": [],
    }

    for sig, out in pairs:
        win = 1 if out.outcome in ("WIN", "SMALL_WIN") else 0
        outcomes.append(win)
        component_values["RCS.TAS"].append(sig.rcs_tas_bin)
        component_values["RCS.VOL"].append(sig.rcs_vol)
        component_values["RCS.BEH"].append(sig.rcs_beh)
        component_values["RCS.LVL"].append(sig.rcs_lvl)
        component_values["RCS.VOLP"].append(sig.rcs_volp)
        component_values["RCS.TIME"].append(sig.rcs_time)
        component_values["SES.TRIG"].append(sig.ses_trig)
        component_values["SES.STR"].append(sig.ses_str)
        component_values["SES.LVLQ"].append(sig.ses_lvlq)
        component_values["SES.EFF"].append(sig.ses_eff)
        component_values["SES.MOM"].append(sig.ses_mom)

    n = len(outcomes)

    def _pearson(x: list, y: list) -> float:
        if len(x) < 2:
            return 0.0
        mx = sum(x) / len(x)
        my = sum(y) / len(y)
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        return num / (dx * dy) if dx * dy > 0 else 0.0

    # 1. Correlation with outcome
    correlations = {}
    for comp, vals in component_values.items():
        correlations[comp] = round(_pearson(vals, outcomes), 4)

    # 2. Information value: win rate when component=100 vs component=50 vs component=0
    info_value = {}
    for comp, vals in component_values.items():
        by_bin: Dict[int, list[int]] = {}
        for v, o in zip(vals, outcomes):
            by_bin.setdefault(v, []).append(o)
        bin_wr = {}
        for bv, outs in sorted(by_bin.items()):
            bin_wr[bv] = round(sum(outs) / len(outs) * 100, 1) if outs else 0.0
        info_value[comp] = bin_wr

    # 3. Redundancy: pairwise correlation between components
    comp_names = list(component_values.keys())
    redundancy: Dict[str, Dict[str, float]] = {}
    for i, c1 in enumerate(comp_names):
        for j, c2 in enumerate(comp_names):
            if j <= i:
                continue
            r = _pearson(component_values[c1], component_values[c2])
            if abs(r) > 0.5:  # only report notable redundancies
                key = f"{c1} <-> {c2}"
                redundancy[key] = round(r, 4)

    # Rank by absolute correlation with outcome
    rankings = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)

    return {
        "outcome_correlations": correlations,
        "information_value": info_value,
        "redundancy_pairs": redundancy,
        "value_rankings": [(name, corr) for name, corr in rankings],
        "total_samples": n,
    }


# ---------------------------------------------------------------------------
# 6. Report
# ---------------------------------------------------------------------------

def print_optimization_report() -> None:
    """Run all optimizations and print a comprehensive report."""
    sep = "=" * 72
    thin = "-" * 72

    print(sep)
    print("  SATVA v15 GATE THRESHOLD OPTIMIZER — REPORT")
    print(sep)
    print()

    # --- Gate optimization ---
    print("[1] GATE THRESHOLD OPTIMIZATION")
    print(thin)
    gate_results = optimize_gates(n_bars=500)
    print()

    curr = gate_results["current_performance"]
    best = gate_results["best_performance"]
    thresh = gate_results["best_thresholds"]

    print("  Current v15.0.0 Thresholds:")
    for k, v in CURRENT_THRESHOLDS.items():
        print(f"    {k:>16s} = {v}")
    print(f"    Trades: {curr['trades']}, Win Rate: {curr['win_rate']:.1f}%, "
          f"Expectancy: {curr['expectancy']:.4f}R")
    print()

    print("  Optimal Thresholds (grid search):")
    for k, v in thresh.items():
        current_key = {
            "RCS": "RCS_min", "SES": "SES_min", "TAS": "TAS_min",
            "MOM": "MOM_min", "PQS": "PQS_min", "Entropy": "Entropy_caution",
        }.get(k, k)
        old = CURRENT_THRESHOLDS.get(current_key, "?")
        marker = " <-- CHANGED" if v != old else ""
        print(f"    {k:>16s} = {v}  (was {old}){marker}")
    print(f"    Trades: {best['trades']}, Win Rate: {best['win_rate']:.1f}%, "
          f"Expectancy: {best['expectancy']:.4f}R")
    print()

    if curr["expectancy"] != 0:
        exp_improvement = ((best["expectancy"] - curr["expectancy"]) / abs(curr["expectancy"])) * 100
    else:
        exp_improvement = 0.0
    wr_improvement = best["win_rate"] - curr["win_rate"]
    print(f"  Expected Improvement:")
    print(f"    Win Rate: {wr_improvement:+.1f}pp")
    print(f"    Expectancy: {exp_improvement:+.1f}%")
    print()

    if gate_results["pareto_frontier"]:
        print("  Pareto Frontier (expectancy vs trade frequency):")
        for i, p in enumerate(gate_results["pareto_frontier"][:5]):
            print(f"    [{i+1}] Trades={p['trades']:>5d}  WR={p['win_rate']:>5.1f}%  "
                  f"Exp={p['expectancy']:>+.4f}R  "
                  f"RCS>={p['thresholds']['RCS']} SES>={p['thresholds']['SES']} "
                  f"Ent<={p['thresholds']['Entropy']}")
    print()

    # --- Weight optimization ---
    print("[2] COMPONENT WEIGHT OPTIMIZATION")
    print(thin)
    weight_results = optimize_weights()
    print()

    for score_name in ("rcs", "ses"):
        r = weight_results[score_name]
        print(f"  {score_name.upper()} Weights:")
        print(f"    {'Component':>10s}  {'Current':>8s}  {'Optimal':>8s}  {'Delta':>8s}")
        for comp in r["current_weights"]:
            curr_w = r["current_weights"][comp]
            opt_w = r["optimal_weights"][comp]
            delta = opt_w - curr_w
            marker = " *" if abs(delta) > 0.001 else ""
            print(f"    {comp:>10s}  {curr_w:>8.0%}  {opt_w:>8.0%}  {delta:>+8.0%}{marker}")
        print(f"    Separation score: {r['current_separation']:.4f} -> {r['optimal_separation']:.4f}")
        print()

    # --- Component analysis ---
    print("[3] COMPONENT CONTRIBUTION ANALYSIS")
    print(thin)
    comp_results = analyze_components()
    print()

    print(f"  Total samples analyzed: {comp_results['total_samples']}")
    print()

    print("  Component Value Rankings (correlation with win/loss):")
    for rank, (name, corr) in enumerate(comp_results["value_rankings"], 1):
        bar = "+" * int(abs(corr) * 50) if corr > 0 else "-" * int(abs(corr) * 50)
        print(f"    {rank:>2d}. {name:<12s}  r={corr:>+.4f}  {bar}")
    print()

    print("  Information Value (win rate by bin):")
    for comp, bins in comp_results["information_value"].items():
        parts = "  ".join(f"bin={b}: {wr:.0f}%" for b, wr in sorted(bins.items()))
        print(f"    {comp:<12s}  {parts}")
    print()

    if comp_results["redundancy_pairs"]:
        print("  Redundant Pairs (|r| > 0.5):")
        for pair, r in comp_results["redundancy_pairs"].items():
            print(f"    {pair}  r={r:+.4f}")
    else:
        print("  Redundant Pairs: None detected (|r| > 0.5)")
    print()

    # --- Recommendations ---
    print("[4] RECOMMENDED v15.1 PATCH CHANGES")
    print(thin)
    print()

    patch_id = 1
    for k, v in thresh.items():
        current_key = {
            "RCS": "RCS_min", "SES": "SES_min", "TAS": "TAS_min",
            "MOM": "MOM_min", "PQS": "PQS_min", "Entropy": "Entropy_caution",
        }.get(k, k)
        old = CURRENT_THRESHOLDS.get(current_key, "?")
        if v != old:
            section = {
                "RCS": "16.7", "SES": "19.6", "TAS": "12.3",
                "MOM": "13.3", "PQS": "15.4", "Entropy": "10",
            }.get(k, "?")
            print(f"  GOV-V15.1-PATCH-{patch_id:02d}")
            print(f"    Section: {section} ({k} gate)")
            print(f"    Before: {k} threshold = {old}")
            print(f"    After:  {k} threshold = {v}")
            print(f"    Rationale: Optimizer found {v} maximizes expectancy on synthetic data")
            print()
            patch_id += 1

    for score_name in ("rcs", "ses"):
        r = weight_results[score_name]
        changed = any(
            abs(r["optimal_weights"][c] - r["current_weights"][c]) > 0.001
            for c in r["current_weights"]
        )
        if changed:
            section = "16" if score_name == "rcs" else "19"
            old_w = ", ".join(f"{c} {int(r['current_weights'][c]*100)}%"
                              for c in r["current_weights"])
            new_w = ", ".join(f"{c} {int(r['optimal_weights'][c]*100)}%"
                              for c in r["optimal_weights"])
            print(f"  GOV-V15.1-PATCH-{patch_id:02d}")
            print(f"    Section: {section} ({score_name.upper()} weights)")
            print(f"    Before: {old_w}")
            print(f"    After:  {new_w}")
            print(f"    Rationale: Weight shift improves winner/loser separation "
                  f"({r['current_separation']:.4f} -> {r['optimal_separation']:.4f})")
            print()
            patch_id += 1

    if patch_id == 1:
        print("  No changes recommended — current thresholds are near-optimal.")
        print()

    print(sep)
    print("  OPTIMIZATION COMPLETE")
    print(sep)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_optimization_report()
