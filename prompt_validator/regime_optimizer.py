"""Regime Detection Optimizer for SATVA v15.

Evaluates the accuracy of SATVA's regime classifier against ground-truth labels
derived from known scenario characteristics, tests alternative detectors, and
reports regime-setup alignment findings.

Run:  python -m prompt_validator.regime_optimizer
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from prompt_validator.scenarios import Bar, Scenario, generate_all_scenarios


# ======================================================================
# Indicator helpers (mirrors simulator.py)
# ======================================================================

def _sma(values: list[float], period: int) -> list[float]:
    result = [0.0] * len(values)
    for i in range(len(values)):
        if i < period - 1:
            result[i] = sum(values[: i + 1]) / (i + 1)
        else:
            result[i] = sum(values[i - period + 1 : i + 1]) / period
    return result


def _ema(values: list[float], period: int) -> list[float]:
    result = [0.0] * len(values)
    if not values or period < 1:
        return result
    k = 2.0 / (period + 1)
    result[0] = values[0]
    for i in range(1, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def _atr(bars: list[Bar], period: int = 14) -> list[float]:
    trs = _true_ranges(bars)
    return _sma(trs, period)


def _true_ranges(bars: list[Bar]) -> list[float]:
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
    return trs


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


def _adx(bars: list[Bar], period: int = 14) -> list[float]:
    result = [0.0] * len(bars)
    if len(bars) < period * 2:
        return result
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    trs: list[float] = []
    for i in range(1, len(bars)):
        high_diff = bars[i].high - bars[i - 1].high
        low_diff = bars[i - 1].low - bars[i].low
        plus_dm.append(max(high_diff, 0) if high_diff > low_diff else 0)
        minus_dm.append(max(low_diff, 0) if low_diff > high_diff else 0)
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i - 1].close),
            abs(bars[i].low - bars[i - 1].close),
        )
        trs.append(tr)
    atr_vals = _sma(trs, period)
    plus_di_raw = _sma(plus_dm, period)
    minus_di_raw = _sma(minus_dm, period)
    dx_vals: list[float] = []
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


def _linear_regression_slope(values: list[float]) -> float:
    """Ordinary least-squares slope over the given window."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0.0


# ======================================================================
# Constants
# ======================================================================

REGIMES = ["STRONG_TREND", "TREND", "RANGE", "UNCLEAR", "SHOCK"]

SETUP_REGIME_MAP = {
    "A": {"STRONG_TREND"},
    "B": {"STRONG_TREND", "TREND", "RANGE", "UNCLEAR"},  # any except SHOCK
    "C": {"RANGE"},
    "D": {"TREND", "STRONG_TREND"},
}


# ======================================================================
# 1. Ground Truth Labeler
# ======================================================================

def label_regime_ground_truth(scenario: Scenario) -> list[str]:
    """Label each bar with its ground-truth regime based on scenario metadata.

    Uses the scenario name, expected_bias, and volatility_regime to assign a
    regime per bar.  For scenarios that change regime mid-stream (BREAKOUT,
    TREND_REVERSAL, V_RECOVERY) the transition point is estimated from the
    scenario generator's structure.
    """
    n = len(scenario.bars)
    name = scenario.name

    if name == "STRONG_UPTREND":
        return ["STRONG_TREND"] * n

    if name == "STRONG_DOWNTREND":
        return ["STRONG_TREND"] * n

    if name == "RANGE_BOUND":
        return ["RANGE"] * n

    if name == "HIGH_VOLATILITY":
        return ["SHOCK"] * n

    if name == "LOW_VOLATILITY":
        return ["RANGE"] * n

    if name == "FLASH_CRASH":
        # First half normal->TREND, crash bars->SHOCK, recovery->TREND
        pre = n // 2
        crash_end = pre + 15
        labels = ["TREND"] * pre + ["SHOCK"] * 15
        labels += ["TREND"] * (n - crash_end)
        return labels[:n]

    if name == "BREAKOUT":
        # 60% compression (RANGE) then breakout (transition bar RANGE->STRONG_TREND)
        compress = int(n * 0.6)
        labels = ["RANGE"] * compress + ["STRONG_TREND"] * (n - compress)
        return labels[:n]

    if name == "CHOPPY":
        return ["UNCLEAR"] * n

    if name == "TREND_REVERSAL":
        # First half: TREND, transition zone: UNCLEAR, second half: TREND
        half = n // 2
        transition_width = max(1, n // 10)
        labels: list[str] = []
        for i in range(n):
            if i < half - transition_width:
                labels.append("TREND")
            elif i < half + transition_width:
                labels.append("UNCLEAR")
            else:
                labels.append("TREND")
        return labels

    if name == "V_RECOVERY":
        # Drop phase: SHOCK, bottom: SHOCK, recovery: TREND
        third = n // 3
        labels = (
            ["SHOCK"] * third
            + ["SHOCK"] * third
            + ["TREND"] * (n - 2 * third)
        )
        return labels[:n]

    # Fallback
    return ["UNCLEAR"] * n


# ======================================================================
# 2. Current v15 Regime Classifier
# ======================================================================

@dataclass
class V15Indicators:
    """Pre-computed indicator arrays for the v15 classifier."""
    trs: list[float]
    atr5m: list[float]
    atr_prev: list[float]  # mean ATR over prior 24 bars
    vol_sma20: list[float]
    overlap_pct: list[float]
    contraction: list[float]
    volume_slope: list[float]
    compression_valid: list[bool]
    body_sizes: list[float]
    avg_body10: list[float]
    expansion_valid: list[bool]
    expansion_strong: list[bool]
    entropy_score: list[float]
    vstab: list[float]
    pullback_norm: list[float]
    rcs_vol: list[float]  # 100/50/0
    ema9_5m: list[float]
    ema21_5m: list[float]
    rsi_5m: list[float]
    # For TAS we approximate 1H from 5m (every 12 bars)
    tas: list[float]
    rcs: list[float]


def _compute_v15_indicators(bars: list[Bar]) -> V15Indicators:
    """Compute all v15 regime-relevant indicators for a bar series."""
    n = len(bars)
    closes = [b.close for b in bars]
    volumes = [float(b.volume) for b in bars]

    # True ranges and ATR
    trs = _true_ranges(bars)
    atr5m = _sma(trs, 14)

    # ATR_prev: mean of ATR values over prior 24 bars
    atr_prev = [0.0] * n
    for i in range(n):
        start = max(0, i - 24)
        window = atr5m[start:i] if i > 0 else [atr5m[0]]
        atr_prev[i] = sum(window) / len(window) if window else atr5m[i]

    # Volume SMA(20)
    vol_sma20 = _sma(volumes, 20)

    # --- Compression (Section 8) ---
    COMP_N = 12
    overlap_pct = [0.0] * n
    contraction = [0.0] * n
    volume_slope = [0.0] * n
    compression_valid = [False] * n

    for i in range(n):
        if i < COMP_N - 1:
            contraction[i] = atr5m[i] / atr_prev[i] if atr_prev[i] > 0 else 1.0
            continue
        window_bars = bars[i - COMP_N + 1 : i + 1]
        highs_w = [b.high for b in window_bars]
        lows_w = [b.low for b in window_bars]
        overlap_range = min(highs_w) - max(lows_w)
        if overlap_range < 0:
            overlap_range = 0
        ranges_w = [b.high - b.low for b in window_bars]
        sorted_ranges = sorted(ranges_w)
        mid = len(sorted_ranges) // 2
        median_range = (
            (sorted_ranges[mid - 1] + sorted_ranges[mid]) / 2
            if len(sorted_ranges) % 2 == 0
            else sorted_ranges[mid]
        )
        overlap_pct[i] = overlap_range / median_range if median_range > 0 else 0

        cont = atr5m[i] / atr_prev[i] if atr_prev[i] > 0 else 1.0
        contraction[i] = cont

        vol_w = volumes[i - COMP_N + 1 : i + 1]
        volume_slope[i] = _linear_regression_slope(vol_w)

        compression_valid[i] = (
            overlap_pct[i] >= 0.60
            and cont <= 0.85
            and volume_slope[i] <= 0
        )

    # --- Expansion (Section 9) ---
    body_sizes = [abs(b.close - b.open) for b in bars]
    avg_body10 = [0.0] * n
    for i in range(n):
        start = max(0, i - 9)
        window = body_sizes[start : i + 1]
        avg_body10[i] = sum(window) / len(window)

    expansion_valid = [False] * n
    expansion_strong = [False] * n
    for i in range(n):
        a = atr5m[i]
        vs = vol_sma20[i]
        body = body_sizes[i]
        ab = avg_body10[i]
        if a <= 0:
            continue
        tr_cond_valid = trs[i] >= 1.2 * a or volumes[i] >= vs
        body_cond_valid = body >= 1.2 * ab if ab > 0 else False
        expansion_valid[i] = tr_cond_valid and body_cond_valid

        tr_cond_strong = trs[i] >= 1.4 * a or volumes[i] >= 1.4 * vs
        body_cond_strong = body >= 1.4 * ab if ab > 0 else False
        expansion_strong[i] = tr_cond_strong and body_cond_strong

    # --- Entropy (Section 10) ---
    ENTROPY_W = 20
    entropy_score = [0.0] * n
    for i in range(n):
        start = max(0, i - ENTROPY_W + 1)
        count = 0
        for j in range(start, i + 1):
            b = bars[j]
            hl = b.high - b.low
            body = abs(b.close - b.open)
            is_indecision = False
            if hl > 0 and body <= 0.25 * hl:
                is_indecision = True
            if j > 0:
                if b.high <= bars[j - 1].high and b.low >= bars[j - 1].low:
                    is_indecision = True
            if atr5m[j] > 0 and body <= 0.15 * atr5m[j]:
                is_indecision = True
            if is_indecision:
                count += 1
        window_len = i - start + 1
        entropy_score[i] = 100.0 * count / max(window_len, 1)

    # --- RCS.VOL (Section 11.1) ---
    vstab = [0.0] * n
    pullback_norm = [0.0] * n
    rcs_vol = [0.0] * n

    # Track swing highs / lows for pullback depth
    swing_highs: list[float] = []
    swing_lows: list[float] = []
    for i in range(n):
        # Simple swing detection (fractal length 2) -- confirmed at i when we
        # have bars i-2..i+2, so only look backward.
        if i >= 4:
            mid_idx = i - 2
            if (
                bars[mid_idx].high > bars[mid_idx - 1].high
                and bars[mid_idx].high > bars[mid_idx - 2].high
                and bars[mid_idx].high > bars[mid_idx + 1].high
                and bars[mid_idx].high > bars[mid_idx + 2].high
            ):
                swing_highs.append(bars[mid_idx].high)
            if (
                bars[mid_idx].low < bars[mid_idx - 1].low
                and bars[mid_idx].low < bars[mid_idx - 2].low
                and bars[mid_idx].low < bars[mid_idx + 1].low
                and bars[mid_idx].low < bars[mid_idx + 2].low
            ):
                swing_lows.append(bars[mid_idx].low)

        # VStab: stdev/mean of cleaned ATR series (last 20 bars)
        start = max(0, i - 19)
        atr_window = []
        for j in range(start, i + 1):
            if atr5m[j] > 0 and trs[j] < 2.2 * atr5m[j]:
                atr_window.append(atr5m[j])
        if len(atr_window) >= 2:
            mean_a = sum(atr_window) / len(atr_window)
            std_a = math.sqrt(
                sum((x - mean_a) ** 2 for x in atr_window) / len(atr_window)
            )
            vstab[i] = std_a / mean_a if mean_a > 0 else 999
        else:
            vstab[i] = 0

        # PullbackNorm (use LONG perspective -- distance from last swing high)
        if swing_highs and bars[i].close < swing_highs[-1]:
            pb_depth = swing_highs[-1] - bars[i].close
        else:
            pb_depth = 0
        pullback_norm[i] = pb_depth / atr5m[i] if atr5m[i] > 0 else 0

        # RCS.VOL bins
        if vstab[i] <= 0.12 and pullback_norm[i] <= 1.0:
            rcs_vol[i] = 100
        elif vstab[i] <= 0.20 and pullback_norm[i] <= 1.3:
            rcs_vol[i] = 50
        else:
            rcs_vol[i] = 0

    # --- TAS (Section 12) approximation ---
    # We don't have true 1H bars, so we synthesize from 5m bars (12 bars = 1H).
    ema9_5m = _ema(closes, 9)
    ema21_5m = _ema(closes, 21)
    rsi_5m = _rsi(closes, 14)

    # Synthesize 1H close series (every 12 bars)
    hourly_closes: list[float] = []
    for i in range(0, n, 12):
        hourly_closes.append(bars[min(i + 11, n - 1)].close)
    ema20_1h = _ema(hourly_closes, 20) if len(hourly_closes) >= 20 else [0.0] * len(hourly_closes)
    ema50_1h = _ema(hourly_closes, 50) if len(hourly_closes) >= 50 else [0.0] * len(hourly_closes)
    has_1h = len(hourly_closes) >= 50

    # VWAP approximation: cumulative VWAP
    cum_vp = 0.0
    cum_vol = 0.0
    vwap = [0.0] * n
    for i in range(n):
        cum_vp += bars[i].close * bars[i].volume
        cum_vol += bars[i].volume
        vwap[i] = cum_vp / cum_vol if cum_vol > 0 else bars[i].close

    tas = [0.0] * n
    for i in range(n):
        # HTF layer
        h_idx = min(i // 12, len(hourly_closes) - 1)
        if has_1h and h_idx < len(ema20_1h) and h_idx < len(ema50_1h):
            slope_1h = ema20_1h[h_idx] - ema50_1h[h_idx]
        else:
            slope_1h = 0
        price_vs_vwap = 1 if bars[i].close > vwap[i] else (-1 if bars[i].close < vwap[i] else 0)

        # For simplicity compute for LONG direction
        slope_aligns = slope_1h > 0
        vwap_aligns = price_vs_vwap > 0
        if slope_aligns and vwap_aligns:
            htf = 100
        elif slope_aligns or vwap_aligns:
            htf = 50
        else:
            htf = 0
        if not has_1h:
            htf = 0

        # EXEC layer
        bull_trigger = ema9_5m[i] > ema21_5m[i] and rsi_5m[i] > 40
        exec_score = 100 if bull_trigger else 0

        tas[i] = 0.60 * htf + 0.40 * exec_score

    # --- BEH (Section 16.3) ---
    beh = [0.0] * n
    for i in range(n):
        start = max(0, i - 9)
        ratios = []
        for j in range(start, i + 1):
            hl = bars[j].high - bars[j].low
            if hl > 0:
                ratios.append(abs(bars[j].close - bars[j].open) / hl)
            else:
                ratios.append(0)
        body_ratio = sum(ratios) / len(ratios) if ratios else 0
        if body_ratio >= 0.55:
            beh[i] = 100
        elif body_ratio >= 0.45:
            beh[i] = 50
        else:
            beh[i] = 0

    # --- TIME (Section 16.6) --- all bars scored 100 (simulation has no real time)
    time_score = 100

    # --- VOLP (Section 14.5) simplified ---
    volp = [50.0] * n  # default neutral
    for i in range(n):
        if vol_sma20[i] > 0 and volumes[i] > 1.2 * vol_sma20[i]:
            volp[i] = 100
        elif vol_sma20[i] > 0 and volumes[i] < 0.5 * vol_sma20[i]:
            volp[i] = 0

    # --- LVL (Section 16.4) simplified ---
    lvl = [100.0] * n  # no real level set in simulation; assume clean

    # --- RCS (Section 16) ---
    rcs = [0.0] * n
    for i in range(n):
        tas_comp = 100 if tas[i] >= 60 else (50 if tas[i] >= 40 else 0)
        rcs[i] = (
            0.25 * tas_comp
            + 0.15 * rcs_vol[i]
            + 0.15 * beh[i]
            + 0.15 * lvl[i]
            + 0.15 * volp[i]
            + 0.15 * time_score
        )

    return V15Indicators(
        trs=trs,
        atr5m=atr5m,
        atr_prev=atr_prev,
        vol_sma20=vol_sma20,
        overlap_pct=overlap_pct,
        contraction=contraction,
        volume_slope=volume_slope,
        compression_valid=compression_valid,
        body_sizes=body_sizes,
        avg_body10=avg_body10,
        expansion_valid=expansion_valid,
        expansion_strong=expansion_strong,
        entropy_score=entropy_score,
        vstab=vstab,
        pullback_norm=pullback_norm,
        rcs_vol=rcs_vol,
        ema9_5m=ema9_5m,
        ema21_5m=ema21_5m,
        rsi_5m=rsi_5m,
        tas=tas,
        rcs=rcs,
    )


def classify_v15(bars: list[Bar]) -> list[str]:
    """Classify regime for each bar using exact SATVA v15 Section 17 rules.

    Returns a list of regime strings, one per bar.
    """
    ind = _compute_v15_indicators(bars)
    n = len(bars)
    regimes: list[str] = []
    volumes = [float(b.volume) for b in bars]

    for i in range(n):
        # --- ABT check (Section 6): any of last 3 bars ---
        abt_active = False
        for j in range(max(0, i - 2), i + 1):
            if ind.atr5m[j] > 0:
                if ind.trs[j] >= 2.2 * ind.atr5m[j]:
                    abt_active = True
                if ind.vol_sma20[j] > 0 and volumes[j] >= 2.5 * ind.vol_sma20[j]:
                    abt_active = True

        # Section 17 regime rules (in priority order)
        if abt_active or ind.rcs_vol[i] == 0:
            regime = "SHOCK"
        elif (
            ind.compression_valid[i]
            and not ind.expansion_valid[i]
            and ind.entropy_score[i] <= 40
        ):
            regime = "RANGE"
        elif (
            ind.expansion_strong[i]
            and ind.tas[i] >= 60
            and ind.entropy_score[i] <= 40
            and ind.rcs[i] >= 70
        ):
            regime = "STRONG_TREND"
        elif (
            ind.expansion_valid[i]
            and ind.entropy_score[i] <= 40
            and ind.rcs[i] >= 65
        ):
            regime = "TREND"
        elif ind.entropy_score[i] > 40 and ind.entropy_score[i] < 60:
            regime = "UNCLEAR"
        elif ind.rcs[i] >= 65 and ind.rcs[i] < 70:
            regime = "UNCLEAR"
        else:
            regime = "UNCLEAR"

        regimes.append(regime)

    return regimes


# ======================================================================
# 3. Regime Accuracy Scorer
# ======================================================================

@dataclass
class RegimeAccuracy:
    overall: float = 0.0
    per_regime_precision: dict[str, float] = field(default_factory=dict)
    per_regime_recall: dict[str, float] = field(default_factory=dict)
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    transition_accuracy: float = 0.0
    avg_lag: float = 0.0


def score_regime_accuracy(
    predicted: list[str], ground_truth: list[str]
) -> RegimeAccuracy:
    """Compute accuracy, precision/recall, confusion matrix, and transition lag."""
    assert len(predicted) == len(ground_truth)
    n = len(predicted)

    # Overall accuracy
    correct = sum(1 for p, g in zip(predicted, ground_truth) if p == g)
    overall = correct / n if n > 0 else 0.0

    # Confusion matrix
    confusion: dict[str, dict[str, int]] = {}
    for r in REGIMES:
        confusion[r] = {r2: 0 for r2 in REGIMES}
    for p, g in zip(predicted, ground_truth):
        if g in confusion and p in confusion[g]:
            confusion[g][p] += 1

    # Per-regime precision and recall
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    for r in REGIMES:
        tp = confusion[r][r]
        # Predicted as r (column sum)
        pred_total = sum(confusion[gt][r] for gt in REGIMES)
        # Actually r (row sum)
        actual_total = sum(confusion[r].values())
        precision[r] = tp / pred_total if pred_total > 0 else 0.0
        recall[r] = tp / actual_total if actual_total > 0 else 0.0

    # Transition detection accuracy and lag measurement
    # Find ground-truth transition points
    gt_transitions: list[int] = []
    for i in range(1, n):
        if ground_truth[i] != ground_truth[i - 1]:
            gt_transitions.append(i)

    transition_detected = 0
    total_lag = 0
    LOOK_AHEAD = 15  # bars to look ahead for detector to catch up

    for t_idx in gt_transitions:
        new_regime = ground_truth[t_idx]
        # Check if predicted catches the change within LOOK_AHEAD bars
        detected = False
        for offset in range(min(LOOK_AHEAD, n - t_idx)):
            if predicted[t_idx + offset] == new_regime:
                transition_detected += 1
                total_lag += offset
                detected = True
                break
        if not detected:
            total_lag += LOOK_AHEAD

    transition_accuracy = (
        transition_detected / len(gt_transitions) if gt_transitions else 1.0
    )
    avg_lag = total_lag / len(gt_transitions) if gt_transitions else 0.0

    return RegimeAccuracy(
        overall=overall,
        per_regime_precision=precision,
        per_regime_recall=recall,
        confusion=confusion,
        transition_accuracy=transition_accuracy,
        avg_lag=avg_lag,
    )


# ======================================================================
# 4. Alternative Regime Detectors
# ======================================================================

def classify_adx_based(bars: list[Bar]) -> list[str]:
    """ADX-based regime detection.

    ADX > 45 -> STRONG_TREND, ADX > 30 -> TREND, ADX < 20 -> RANGE, else UNCLEAR.
    Shock detected via ABT-like spike rule.
    """
    n = len(bars)
    adx_vals = _adx(bars, 14)
    trs = _true_ranges(bars)
    atr = _sma(trs, 14)
    regimes: list[str] = []

    for i in range(n):
        # Shock check
        shock = False
        if atr[i] > 0 and trs[i] >= 2.2 * atr[i]:
            shock = True
        if shock:
            regimes.append("SHOCK")
        elif adx_vals[i] > 45:
            regimes.append("STRONG_TREND")
        elif adx_vals[i] > 30:
            regimes.append("TREND")
        elif adx_vals[i] < 20:
            regimes.append("RANGE")
        else:
            regimes.append("UNCLEAR")
    return regimes


def _hurst_proxy(closes: list[float], window: int = 40) -> list[float]:
    """Rescaled range analysis Hurst exponent proxy over a rolling window."""
    n = len(closes)
    result = [0.5] * n
    for i in range(window, n):
        segment = closes[i - window : i]
        mean_s = sum(segment) / window
        deviations = [x - mean_s for x in segment]
        cumulative = []
        s = 0
        for d in deviations:
            s += d
            cumulative.append(s)
        R = max(cumulative) - min(cumulative)
        S = math.sqrt(sum(d ** 2 for d in deviations) / window)
        if S > 0 and R > 0:
            rs = R / S
            # H ~ log(R/S) / log(n)
            result[i] = math.log(rs) / math.log(window)
        else:
            result[i] = 0.5
    return result


def classify_hurst(bars: list[Bar]) -> list[str]:
    """Hurst exponent proxy regime detection.

    H > 0.6 -> trending, H < 0.4 -> mean-reverting (RANGE), 0.4-0.6 -> random (UNCLEAR).
    """
    closes = [b.close for b in bars]
    hurst = _hurst_proxy(closes, 40)
    trs = _true_ranges(bars)
    atr = _sma(trs, 14)

    regimes: list[str] = []
    for i in range(len(bars)):
        shock = atr[i] > 0 and trs[i] >= 2.2 * atr[i]
        if shock:
            regimes.append("SHOCK")
        elif hurst[i] > 0.7:
            regimes.append("STRONG_TREND")
        elif hurst[i] > 0.6:
            regimes.append("TREND")
        elif hurst[i] < 0.4:
            regimes.append("RANGE")
        else:
            regimes.append("UNCLEAR")
    return regimes


def _efficiency_ratio(closes: list[float], period: int = 20) -> list[float]:
    """Kaufman Efficiency Ratio: |net move| / sum(|bar-to-bar moves|)."""
    n = len(closes)
    result = [0.0] * n
    for i in range(period, n):
        net = abs(closes[i] - closes[i - period])
        path = sum(abs(closes[j] - closes[j - 1]) for j in range(i - period + 1, i + 1))
        result[i] = net / path if path > 0 else 0.0
    return result


def classify_efficiency_ratio(bars: list[Bar]) -> list[str]:
    """Efficiency ratio regime detection.

    High ER (>0.5) -> STRONG_TREND, >0.35 -> TREND, <0.15 -> RANGE, else UNCLEAR.
    """
    closes = [b.close for b in bars]
    er = _efficiency_ratio(closes, 20)
    trs = _true_ranges(bars)
    atr = _sma(trs, 14)

    regimes: list[str] = []
    for i in range(len(bars)):
        shock = atr[i] > 0 and trs[i] >= 2.2 * atr[i]
        if shock:
            regimes.append("SHOCK")
        elif er[i] > 0.50:
            regimes.append("STRONG_TREND")
        elif er[i] > 0.35:
            regimes.append("TREND")
        elif er[i] < 0.15:
            regimes.append("RANGE")
        else:
            regimes.append("UNCLEAR")
    return regimes


def classify_volatility_regime(bars: list[Bar]) -> list[str]:
    """GARCH-like volatility percentile regime detection.

    Classifies current volatility by percentile rank vs last 50 bars.
    Top 10% -> SHOCK, top 30% -> TREND (volatile trending), bottom 30% -> RANGE, else UNCLEAR.
    """
    trs = _true_ranges(bars)
    n = len(bars)
    regimes: list[str] = []

    for i in range(n):
        window_start = max(0, i - 49)
        vol_window = trs[window_start : i + 1]
        sorted_w = sorted(vol_window)
        rank = sorted_w.index(trs[i]) if trs[i] in sorted_w else 0
        pct = rank / len(sorted_w) if len(sorted_w) > 0 else 0.5

        if pct >= 0.90:
            regimes.append("SHOCK")
        elif pct >= 0.70:
            regimes.append("STRONG_TREND")
        elif pct >= 0.50:
            regimes.append("TREND")
        elif pct <= 0.30:
            regimes.append("RANGE")
        else:
            regimes.append("UNCLEAR")
    return regimes


def classify_combined(bars: list[Bar]) -> list[str]:
    """Ensemble detector: weighted vote of ADX, Hurst, ER, and VolRegime.

    Each classifier votes; regime with highest weighted score wins.
    Weights: ADX 0.30, Hurst 0.25, ER 0.25, VolRegime 0.20.
    """
    adx_r = classify_adx_based(bars)
    hurst_r = classify_hurst(bars)
    er_r = classify_efficiency_ratio(bars)
    vol_r = classify_volatility_regime(bars)

    weights = [0.30, 0.25, 0.25, 0.20]
    classifiers = [adx_r, hurst_r, er_r, vol_r]

    n = len(bars)
    regimes: list[str] = []
    for i in range(n):
        votes: dict[str, float] = defaultdict(float)
        for cls, w in zip(classifiers, weights):
            votes[cls[i]] += w
        best = max(votes, key=lambda r: votes[r])
        regimes.append(best)
    return regimes


# ======================================================================
# 5. Regime Transition Smoother
# ======================================================================

def smooth_transitions(regimes: list[str], min_hold: int = 5) -> list[str]:
    """Prevent rapid regime flipping by requiring min_hold consecutive bars
    of a new regime signal before switching.

    Returns a smoothed regime list of the same length.
    """
    if not regimes:
        return []
    smoothed = [regimes[0]]
    current = regimes[0]
    pending: Optional[str] = None
    pending_count = 0

    for i in range(1, len(regimes)):
        if regimes[i] != current:
            if regimes[i] == pending:
                pending_count += 1
            else:
                pending = regimes[i]
                pending_count = 1
            if pending_count >= min_hold:
                current = pending
                pending = None
                pending_count = 0
        else:
            pending = None
            pending_count = 0
        smoothed.append(current)

    return smoothed


def evaluate_smoothing(
    raw_regimes: list[str], ground_truth: list[str]
) -> dict[int, RegimeAccuracy]:
    """Test multiple min_hold periods and return accuracy for each."""
    results: dict[int, RegimeAccuracy] = {}
    for hold in [0, 3, 5, 8, 12]:
        if hold == 0:
            smoothed = raw_regimes
        else:
            smoothed = smooth_transitions(raw_regimes, hold)
        results[hold] = score_regime_accuracy(smoothed, ground_truth)
    return results


# ======================================================================
# 6. Regime-Setup Alignment Analysis
# ======================================================================

def _simulate_setup_in_regime(
    bars: list[Bar], regime: str, setup: str, direction: str = "LONG"
) -> tuple[int, int]:
    """Simplified simulation: count wins vs losses for a given setup/regime.

    Returns (wins, losses).
    """
    atr = _atr(bars, 14)
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    wins = 0
    losses = 0

    for i in range(30, len(bars) - 10):
        if atr[i] <= 0:
            continue
        risk = 1.5 * atr[i]
        entry = bars[i].close

        if setup == "A":
            # Breakout: need expansion-strong bar
            body = abs(bars[i].close - bars[i].open)
            if body < 1.4 * (atr[i] * 0.5):
                continue
            if not (ema9[i] > ema21[i] if direction == "LONG" else ema9[i] < ema21[i]):
                continue
        elif setup == "B":
            # Level break: need expansion-valid
            body = abs(bars[i].close - bars[i].open)
            if body < 1.0 * (atr[i] * 0.5):
                continue
        elif setup == "C":
            # Range reversion: need bar near range low/high
            window_bars = bars[max(0, i - 80) : i + 1]
            range_high = max(b.high for b in window_bars)
            range_low = min(b.low for b in window_bars)
            if direction == "LONG":
                if bars[i].close > range_low + 0.2 * (range_high - range_low):
                    continue
                if not bars[i].is_bullish:
                    continue
            else:
                if bars[i].close < range_high - 0.2 * (range_high - range_low):
                    continue
                if bars[i].is_bullish:
                    continue
        elif setup == "D":
            # Pullback: need trend + pullback
            if not (ema9[i] > ema21[i] if direction == "LONG" else ema9[i] < ema21[i]):
                continue
            # Need some pullback evidence
            recent = bars[max(0, i - 5) : i + 1]
            if direction == "LONG":
                if not any(b.close < b.open for b in recent[:-1]):
                    continue
                if not bars[i].is_bullish:
                    continue
            else:
                if not any(b.close > b.open for b in recent[:-1]):
                    continue
                if bars[i].is_bullish:
                    continue

        # Simulate exit over next 10 bars
        if direction == "LONG":
            stop = entry - risk
            target = entry + 2.0 * atr[i]
        else:
            stop = entry + risk
            target = entry - 2.0 * atr[i]

        for j in range(i + 1, min(i + 10, len(bars))):
            if direction == "LONG":
                if bars[j].low <= stop:
                    losses += 1
                    break
                if bars[j].high >= target:
                    wins += 1
                    break
            else:
                if bars[j].high >= stop:
                    losses += 1
                    break
                if bars[j].low <= target:
                    wins += 1
                    break

    return wins, losses


def analyze_regime_setup_alignment() -> dict[str, dict[str, dict[str, float]]]:
    """For each regime, test all setups. Report win rates.

    Returns: {regime: {setup: {"wins": N, "losses": N, "win_rate": pct, "enabled": bool}}}
    """
    scenarios = generate_all_scenarios(200)
    results: dict[str, dict[str, dict[str, float]]] = {}

    for regime_name in REGIMES:
        results[regime_name] = {}
        for setup in ["A", "B", "C", "D"]:
            total_wins = 0
            total_losses = 0
            enabled = regime_name in SETUP_REGIME_MAP[setup]

            for scenario in scenarios:
                gt = label_regime_ground_truth(scenario)
                # Extract bars where ground truth matches this regime
                regime_bars: list[Bar] = []
                for i, label in enumerate(gt):
                    if label == regime_name:
                        regime_bars.append(scenario.bars[i])

                if len(regime_bars) < 50:
                    continue

                w, l = _simulate_setup_in_regime(regime_bars, regime_name, setup)
                total_wins += w
                total_losses += l

            total = total_wins + total_losses
            win_rate = total_wins / total * 100 if total > 0 else 0.0
            results[regime_name][setup] = {
                "wins": total_wins,
                "losses": total_losses,
                "win_rate": win_rate,
                "enabled": 1.0 if enabled else 0.0,
            }

    return results


# ======================================================================
# 7. Report
# ======================================================================

def print_regime_report() -> None:
    """Print comprehensive regime detection analysis report."""
    scenarios = generate_all_scenarios(200)

    classifiers = {
        "V15_Current": classify_v15,
        "ADX_Based": classify_adx_based,
        "Hurst_Proxy": classify_hurst,
        "Efficiency_Ratio": classify_efficiency_ratio,
        "Vol_Regime": classify_volatility_regime,
        "Combined_Ensemble": classify_combined,
    }

    # ---- Header ----
    print("=" * 90)
    print("  SATVA v15 REGIME DETECTION OPTIMIZER -- ANALYSIS REPORT")
    print("=" * 90)

    # ---- Per-scenario accuracy table ----
    # Store results for later summary
    all_results: dict[str, dict[str, RegimeAccuracy]] = {}

    for scenario in scenarios:
        gt = label_regime_ground_truth(scenario)
        print(f"\n{'─' * 90}")
        print(f"  SCENARIO: {scenario.name}  |  Bias: {scenario.expected_bias}  |  Vol: {scenario.volatility_regime}")
        print(f"  Ground truth distribution: ", end="")
        dist: dict[str, int] = defaultdict(int)
        for r in gt:
            dist[r] += 1
        for r in REGIMES:
            if dist[r] > 0:
                print(f"{r}={dist[r]} ", end="")
        print()
        print(f"{'─' * 90}")

        header = f"  {'Classifier':<22} {'Accuracy':>8} {'TransAcc':>9} {'AvgLag':>7}"
        for r in REGIMES:
            header += f" {'P-' + r[:5]:>9}"
        print(header)
        print(f"  {'-' * 86}")

        for cls_name, cls_fn in classifiers.items():
            predicted = cls_fn(scenario.bars)
            acc = score_regime_accuracy(predicted, gt)
            if cls_name not in all_results:
                all_results[cls_name] = {}
            all_results[cls_name][scenario.name] = acc

            row = f"  {cls_name:<22} {acc.overall * 100:>7.1f}% {acc.transition_accuracy * 100:>8.1f}% {acc.avg_lag:>6.1f}"
            for r in REGIMES:
                p = acc.per_regime_precision.get(r, 0)
                row += f" {p * 100:>8.1f}%"
            print(row)

    # ---- Smoothing Analysis ----
    print(f"\n{'=' * 90}")
    print("  TRANSITION SMOOTHING ANALYSIS")
    print(f"{'=' * 90}")

    for scenario in scenarios:
        gt = label_regime_ground_truth(scenario)
        # Only show for scenarios with transitions
        transitions = sum(1 for i in range(1, len(gt)) if gt[i] != gt[i - 1])
        if transitions == 0:
            continue

        raw_v15 = classify_v15(scenario.bars)
        smoothing_results = evaluate_smoothing(raw_v15, gt)

        print(f"\n  {scenario.name} (ground truth transitions: {transitions})")
        print(f"  {'MinHold':>8} {'Accuracy':>9} {'TransAcc':>9} {'AvgLag':>7}")
        for hold, acc in sorted(smoothing_results.items()):
            tag = "raw" if hold == 0 else str(hold)
            print(f"  {tag:>8} {acc.overall * 100:>8.1f}% {acc.transition_accuracy * 100:>8.1f}% {acc.avg_lag:>6.1f}")

    # ---- Overall Summary ----
    print(f"\n{'=' * 90}")
    print("  OVERALL ACCURACY SUMMARY (averaged across all scenarios)")
    print(f"{'=' * 90}")
    print(f"  {'Classifier':<22} {'AvgAccuracy':>12} {'AvgTransAcc':>12} {'AvgLag':>8}")
    print(f"  {'-' * 56}")

    best_cls = ""
    best_acc = -1.0
    for cls_name in classifiers:
        accs = all_results[cls_name]
        avg_overall = sum(a.overall for a in accs.values()) / len(accs)
        avg_trans = sum(a.transition_accuracy for a in accs.values()) / len(accs)
        avg_lag = sum(a.avg_lag for a in accs.values()) / len(accs)
        print(f"  {cls_name:<22} {avg_overall * 100:>11.1f}% {avg_trans * 100:>11.1f}% {avg_lag:>7.1f}")
        if avg_overall > best_acc:
            best_acc = avg_overall
            best_cls = cls_name

    # ---- Best detector per scenario ----
    print(f"\n{'=' * 90}")
    print("  BEST DETECTOR PER SCENARIO")
    print(f"{'=' * 90}")
    print(f"  {'Scenario':<22} {'Best Detector':<22} {'Accuracy':>9}")
    print(f"  {'-' * 55}")
    for scenario in scenarios:
        best_name = ""
        best_a = -1.0
        for cls_name in classifiers:
            a = all_results[cls_name][scenario.name].overall
            if a > best_a:
                best_a = a
                best_name = cls_name
        print(f"  {scenario.name:<22} {best_name:<22} {best_a * 100:>8.1f}%")

    # ---- Confusion matrix for v15 (aggregated) ----
    print(f"\n{'=' * 90}")
    print("  AGGREGATED CONFUSION MATRIX (V15 Current)")
    print(f"{'=' * 90}")
    agg_conf: dict[str, dict[str, int]] = {r: {r2: 0 for r2 in REGIMES} for r in REGIMES}
    for scenario in scenarios:
        acc = all_results["V15_Current"][scenario.name]
        for gt_r in REGIMES:
            for pred_r in REGIMES:
                agg_conf[gt_r][pred_r] += acc.confusion.get(gt_r, {}).get(pred_r, 0)

    gt_pred_label = "GT \\ Pred"
    header = f"  {gt_pred_label:<16}"
    for r in REGIMES:
        header += f" {r[:8]:>9}"
    print(header)
    print(f"  {'-' * (16 + 9 * len(REGIMES))}")
    for gt_r in REGIMES:
        row = f"  {gt_r:<16}"
        for pred_r in REGIMES:
            row += f" {agg_conf[gt_r][pred_r]:>9}"
        print(row)

    # ---- Regime-Setup Alignment ----
    print(f"\n{'=' * 90}")
    print("  REGIME-SETUP ALIGNMENT ANALYSIS")
    print(f"{'=' * 90}")
    alignment = analyze_regime_setup_alignment()
    print(f"  {'Regime':<16} {'Setup':>6} {'Enabled':>8} {'Wins':>6} {'Losses':>7} {'WinRate':>8} {'Finding':<30}")
    print(f"  {'-' * 83}")

    misalignments: list[str] = []
    for regime in REGIMES:
        for setup in ["A", "B", "C", "D"]:
            data = alignment[regime][setup]
            enabled = data["enabled"] > 0
            wr = data["win_rate"]
            wins = int(data["wins"])
            losses = int(data["losses"])
            total = wins + losses

            finding = ""
            if enabled and total >= 5 and wr < 40:
                finding = "POOR: enabled but low WR"
                misalignments.append(
                    f"  ** Setup {setup} in {regime}: enabled but win rate only {wr:.1f}% ({wins}W/{losses}L)"
                )
            elif not enabled and total >= 5 and wr > 55:
                finding = "OPPORTUNITY: disabled but good WR"
                misalignments.append(
                    f"  ** Setup {setup} in {regime}: disabled but win rate is {wr:.1f}% ({wins}W/{losses}L)"
                )
            elif total < 5:
                finding = "(insufficient data)"

            enabled_str = "YES" if enabled else "NO"
            print(
                f"  {regime:<16} {setup:>6} {enabled_str:>8} {wins:>6} {losses:>7} {wr:>7.1f}% {finding:<30}"
            )

    # ---- Recommendations ----
    print(f"\n{'=' * 90}")
    print("  RECOMMENDATIONS")
    print(f"{'=' * 90}")

    print(f"\n  1. BEST OVERALL DETECTOR: {best_cls} ({best_acc * 100:.1f}% average accuracy)")
    print(f"     Current V15 accuracy: {sum(a.overall for a in all_results['V15_Current'].values()) / len(scenarios) * 100:.1f}%")

    if best_cls != "V15_Current":
        improvement = (best_acc - sum(a.overall for a in all_results["V15_Current"].values()) / len(scenarios)) * 100
        if improvement > 0:
            print(f"     Potential improvement: +{improvement:.1f}pp by switching to {best_cls}")

    print(f"\n  2. TRANSITION DETECTION:")
    v15_avg_lag = sum(a.avg_lag for a in all_results["V15_Current"].values()) / len(scenarios)
    combined_avg_lag = sum(a.avg_lag for a in all_results["Combined_Ensemble"].values()) / len(scenarios)
    print(f"     V15 average lag: {v15_avg_lag:.1f} bars")
    print(f"     Combined ensemble lag: {combined_avg_lag:.1f} bars")

    print(f"\n  3. REGIME-SETUP MISALIGNMENTS:")
    if misalignments:
        for m in misalignments:
            print(m)
    else:
        print("     No significant misalignments found.")

    print(f"\n  4. KEY FINDINGS:")
    # Find regimes where v15 struggles most
    worst_scenario = ""
    worst_acc = 1.0
    for s_name, acc in all_results["V15_Current"].items():
        if acc.overall < worst_acc:
            worst_acc = acc.overall
            worst_scenario = s_name
    print(f"     - V15 struggles most with: {worst_scenario} ({worst_acc * 100:.1f}% accuracy)")

    # Find which alternative helps most for the worst scenario
    best_alt = ""
    best_alt_acc = -1.0
    for cls_name in classifiers:
        if cls_name == "V15_Current":
            continue
        a = all_results[cls_name][worst_scenario].overall
        if a > best_alt_acc:
            best_alt_acc = a
            best_alt = cls_name
    print(f"     - Best alternative for {worst_scenario}: {best_alt} ({best_alt_acc * 100:.1f}%)")

    # SHOCK detection quality
    shock_precision = sum(
        a.per_regime_precision.get("SHOCK", 0) for a in all_results["V15_Current"].values()
    ) / len(scenarios)
    shock_recall = sum(
        a.per_regime_recall.get("SHOCK", 0) for a in all_results["V15_Current"].values()
    ) / len(scenarios)
    print(f"     - V15 SHOCK detection: precision={shock_precision * 100:.1f}%, recall={shock_recall * 100:.1f}%")

    print(f"\n{'=' * 90}")
    print("  END OF REPORT")
    print(f"{'=' * 90}")


# ======================================================================
# Main entry point
# ======================================================================

if __name__ == "__main__":
    print_regime_report()
