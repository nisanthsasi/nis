"""Alpha Discovery Engine for SATVA v15.

Discovers new alpha signals that could improve SATVA's deterministic
intraday execution. Tests each alpha factor across all 10 market
scenarios and ranks by predictive power.

Alpha factors are scored 0-100 and evaluated for:
  - Hit rate (profitable move within next 10 bars)
  - Average R gained when signal fires
  - False positive rate
  - Information ratio (signal return / signal std)
  - Correlation with existing SATVA signals (orthogonality)

Usage:
    python -m prompt_validator.alpha_discovery
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import Callable

from prompt_validator.scenarios import Bar, Scenario, generate_all_scenarios
from prompt_validator.simulator import _ema, _sma, _atr, _rsi


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AlphaSignal:
    """A single alpha signal firing at a specific bar."""
    bar_index: int
    score: float          # 0-100 signal strength
    direction: str        # "LONG", "SHORT", or "NEUTRAL"


@dataclass
class AlphaMetrics:
    """Performance metrics for one alpha factor across scenarios."""
    name: str
    hit_rate: float = 0.0          # % of signals leading to profit in 10 bars
    avg_r: float = 0.0             # average R gained when signal fires
    false_positive_rate: float = 0.0
    information_ratio: float = 0.0  # signal return / signal std
    orthogonality: float = 0.0     # 1 - abs(correlation with SATVA signals)
    signal_count: int = 0
    combined_score: float = 0.0
    integration_point: str = ""     # recommended SATVA integration


@dataclass
class AlphaResult:
    """Full result for one alpha factor tested across all scenarios."""
    name: str
    metrics_by_scenario: dict[str, AlphaMetrics] = field(default_factory=dict)
    aggregate: AlphaMetrics = field(default_factory=lambda: AlphaMetrics(""))

    def compute_aggregate(self) -> None:
        all_m = list(self.metrics_by_scenario.values())
        if not all_m:
            return
        total_signals = sum(m.signal_count for m in all_m)
        if total_signals == 0:
            self.aggregate = AlphaMetrics(self.name)
            return
        # Weighted average by signal count
        self.aggregate.name = self.name
        self.aggregate.signal_count = total_signals
        self.aggregate.hit_rate = (
            sum(m.hit_rate * m.signal_count for m in all_m) / total_signals
        )
        self.aggregate.avg_r = (
            sum(m.avg_r * m.signal_count for m in all_m) / total_signals
        )
        self.aggregate.false_positive_rate = (
            sum(m.false_positive_rate * m.signal_count for m in all_m)
            / total_signals
        )
        self.aggregate.information_ratio = (
            sum(m.information_ratio * m.signal_count for m in all_m)
            / total_signals
        )
        self.aggregate.orthogonality = (
            sum(m.orthogonality * m.signal_count for m in all_m)
            / total_signals
        )
        self.aggregate.combined_score = (
            self.aggregate.hit_rate
            * max(self.aggregate.avg_r, 0.01)
            * max(self.aggregate.orthogonality, 0.01)
        )


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _vwap(bars: list[Bar]) -> list[float]:
    """Cumulative session VWAP computed from OHLCV bars."""
    result: list[float] = []
    cum_pv = 0.0
    cum_vol = 0
    for b in bars:
        typical = (b.high + b.low + b.close) / 3.0
        cum_pv += typical * b.volume
        cum_vol += b.volume
        result.append(cum_pv / cum_vol if cum_vol > 0 else b.close)
    return result


def _volume_sma(bars: list[Bar], period: int = 20) -> list[float]:
    """SMA of bar volumes."""
    vols = [float(b.volume) for b in bars]
    return _sma(vols, period)


def _linear_reg_slope(values: list[float]) -> float:
    """Ordinary least-squares slope over the provided values."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _pearson_corr(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation between two equal-length sequences."""
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0
    xs, ys = xs[:n], ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


# ---------------------------------------------------------------------------
# SATVA baseline signal (for orthogonality measurement)
# ---------------------------------------------------------------------------

def _satva_baseline_signals(bars: list[Bar]) -> list[float]:
    """Produce a per-bar SATVA-like signal score for correlation testing.

    Combines EMA crossover + RSI + volume check (the core SATVA entry logic).
    Returns a list of scores 0-100 per bar.
    """
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    rsi = _rsi(closes, 14)
    vol_sma = _volume_sma(bars, 20)
    atr = _atr(bars, 14)

    scores: list[float] = []
    for i in range(len(bars)):
        s = 50.0
        # EMA trend alignment
        if atr[i] > 0:
            spread_norm = (ema9[i] - ema21[i]) / atr[i]
            s += _clamp(spread_norm * 20, -30, 30)
        # RSI
        if 40 < rsi[i] < 70:
            s += 10
        elif rsi[i] <= 30 or rsi[i] >= 80:
            s -= 15
        # Volume
        if vol_sma[i] > 0 and bars[i].volume > vol_sma[i]:
            s += 10
        scores.append(_clamp(s))
    return scores


# ---------------------------------------------------------------------------
# Outcome measurement (shared by all alpha evaluators)
# ---------------------------------------------------------------------------

def _measure_outcome(
    bars: list[Bar],
    idx: int,
    direction: str,
    atr_val: float,
    lookahead: int = 10,
) -> tuple[bool, float]:
    """Measure whether a signal at bar `idx` leads to a profitable move.

    Returns (is_hit, r_multiple) where r_multiple uses ATR as the risk unit.
    """
    if atr_val <= 0:
        return False, 0.0
    entry = bars[idx].close
    best_r = 0.0
    worst_r = 0.0
    end = min(idx + lookahead + 1, len(bars))
    for j in range(idx + 1, end):
        if direction == "LONG":
            move = bars[j].close - entry
        else:
            move = entry - bars[j].close
        r = move / atr_val
        best_r = max(best_r, r)
        worst_r = min(worst_r, r)

    # Hit = best excursion > 1R before worst exceeds -1R
    if best_r >= 1.0:
        return True, best_r
    if best_r > 0:
        return False, best_r
    return False, worst_r


def _evaluate_signals(
    bars: list[Bar],
    signals: list[AlphaSignal],
    atr: list[float],
    satva_scores: list[float],
) -> AlphaMetrics:
    """Evaluate a list of alpha signals against bar outcomes."""
    if not signals:
        return AlphaMetrics("")

    hits = 0
    r_values: list[float] = []
    false_positives = 0
    signal_scores_at_fire: list[float] = []
    satva_at_fire: list[float] = []

    for sig in signals:
        i = sig.bar_index
        if i >= len(bars) - 1 or i >= len(atr):
            continue
        is_hit, r_val = _measure_outcome(bars, i, sig.direction, atr[i])
        if is_hit:
            hits += 1
        else:
            false_positives += 1
        r_values.append(r_val)
        signal_scores_at_fire.append(sig.score)
        if i < len(satva_scores):
            satva_at_fire.append(satva_scores[i])

    total = len(r_values)
    if total == 0:
        return AlphaMetrics("")

    hit_rate = hits / total * 100
    avg_r = sum(r_values) / total
    fp_rate = false_positives / total * 100

    # Information ratio
    r_mean = avg_r
    r_std = statistics.pstdev(r_values) if len(r_values) > 1 else 1.0
    info_ratio = r_mean / r_std if r_std > 0 else 0.0

    # Orthogonality: 1 - abs(correlation with SATVA baseline)
    if len(signal_scores_at_fire) >= 3 and len(satva_at_fire) >= 3:
        corr = _pearson_corr(signal_scores_at_fire, satva_at_fire)
        ortho = 1.0 - abs(corr)
    else:
        ortho = 0.5  # assume moderate orthogonality when insufficient data

    return AlphaMetrics(
        name="",
        hit_rate=hit_rate,
        avg_r=avg_r,
        false_positive_rate=fp_rate,
        information_ratio=info_ratio,
        orthogonality=ortho,
        signal_count=total,
    )


# ---------------------------------------------------------------------------
# Alpha Factor Implementations (12 factors)
# ---------------------------------------------------------------------------

def alpha_vwap_deviation(bars: list[Bar]) -> list[AlphaSignal]:
    """1. VWAP Deviation Alpha.

    Distance from VWAP normalized by ATR. Entries near VWAP (within 0.3*ATR)
    score high; far from VWAP score low.
    """
    vwap = _vwap(bars)
    atr = _atr(bars, 14)
    signals: list[AlphaSignal] = []
    for i in range(20, len(bars)):
        if atr[i] <= 0:
            continue
        dev = abs(bars[i].close - vwap[i]) / atr[i]
        if dev <= 0.3:
            score = _clamp(100 - dev * 100)
            direction = "LONG" if bars[i].close > vwap[i] else "SHORT"
            signals.append(AlphaSignal(i, score, direction))
        elif dev >= 2.0:
            # Contrarian: price stretched far from VWAP
            score = _clamp(min(dev * 15, 80))
            direction = "SHORT" if bars[i].close > vwap[i] else "LONG"
            signals.append(AlphaSignal(i, score, direction))
    return signals


def alpha_volume_climax(bars: list[Bar]) -> list[AlphaSignal]:
    """2. Volume Climax Alpha.

    Volume > 3x average followed by reversal candle = contrarian signal.
    """
    vol_sma = _volume_sma(bars, 20)
    signals: list[AlphaSignal] = []
    for i in range(21, len(bars)):
        if vol_sma[i] <= 0:
            continue
        vol_ratio = bars[i].volume / vol_sma[i]
        if vol_ratio >= 3.0:
            # Climax detected. Contrarian direction.
            if bars[i].is_bullish:
                direction = "SHORT"
            else:
                direction = "LONG"
            score = _clamp(min(vol_ratio * 20, 100))
            signals.append(AlphaSignal(i, score, direction))
    return signals


def alpha_atr_contraction_expansion(bars: list[Bar]) -> list[AlphaSignal]:
    """3. ATR Contraction-Expansion Ratio.

    Current ATR / ATR(50-bar lookback). Low ratio = compression about to expand.
    """
    atr14 = _atr(bars, 14)
    atr50 = _atr(bars, 50)
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    signals: list[AlphaSignal] = []
    for i in range(50, len(bars)):
        if atr50[i] <= 0:
            continue
        ratio = atr14[i] / atr50[i]
        if ratio <= 0.6:
            # Strong compression: breakout imminent
            score = _clamp((1.0 - ratio) * 120)
            direction = "LONG" if ema9[i] > ema21[i] else "SHORT"
            signals.append(AlphaSignal(i, score, direction))
        elif ratio >= 1.8:
            # Overextended expansion: potential reversion
            score = _clamp(min((ratio - 1.0) * 40, 80))
            direction = "SHORT" if ema9[i] > ema21[i] else "LONG"
            signals.append(AlphaSignal(i, score, direction))
    return signals


def alpha_order_flow_imbalance(bars: list[Bar]) -> list[AlphaSignal]:
    """4. Order Flow Imbalance Proxy.

    (Close-Low)/(High-Low) as buying pressure. Average over 5 bars.
    """
    signals: list[AlphaSignal] = []
    for i in range(5, len(bars)):
        pressures: list[float] = []
        for k in range(i - 4, i + 1):
            rng = bars[k].high - bars[k].low
            if rng > 0:
                pressures.append((bars[k].close - bars[k].low) / rng)
            else:
                pressures.append(0.5)
        avg_pressure = sum(pressures) / len(pressures)
        if avg_pressure >= 0.75:
            score = _clamp(avg_pressure * 100)
            signals.append(AlphaSignal(i, score, "LONG"))
        elif avg_pressure <= 0.25:
            score = _clamp((1.0 - avg_pressure) * 100)
            signals.append(AlphaSignal(i, score, "SHORT"))
    return signals


def alpha_momentum_divergence(bars: list[Bar]) -> list[AlphaSignal]:
    """5. Multi-Bar Momentum Divergence.

    Price making new highs but RSI declining over 20 bars = reversal warning.
    """
    closes = [b.close for b in bars]
    rsi = _rsi(closes, 14)
    signals: list[AlphaSignal] = []
    lookback = 20
    for i in range(lookback + 14, len(bars)):
        window_start = i - lookback
        # Check bearish divergence: price HH, RSI LH
        price_max_idx = max(range(window_start, i + 1), key=lambda k: bars[k].high)
        rsi_max_idx = max(range(window_start, i + 1), key=lambda k: rsi[k])
        if (price_max_idx >= i - 3 and rsi_max_idx <= window_start + lookback // 2
                and bars[i].high >= max(b.high for b in bars[window_start:i])):
            rsi_slope = _linear_reg_slope(rsi[window_start:i + 1])
            if rsi_slope < -0.3:
                score = _clamp(min(abs(rsi_slope) * 80, 95))
                signals.append(AlphaSignal(i, score, "SHORT"))

        # Bullish divergence: price LL, RSI HL
        price_min_idx = min(range(window_start, i + 1), key=lambda k: bars[k].low)
        rsi_min_idx = min(range(window_start, i + 1), key=lambda k: rsi[k])
        if (price_min_idx >= i - 3 and rsi_min_idx <= window_start + lookback // 2
                and bars[i].low <= min(b.low for b in bars[window_start:i])):
            rsi_slope = _linear_reg_slope(rsi[window_start:i + 1])
            if rsi_slope > 0.3:
                score = _clamp(min(abs(rsi_slope) * 80, 95))
                signals.append(AlphaSignal(i, score, "LONG"))
    return signals


def alpha_time_of_day(bars: list[Bar]) -> list[AlphaSignal]:
    """6. Time-of-Day Edge.

    Split bars into early (0-33%), mid (34-66%), late (67-100%) of session.
    Assign higher scores to historically better buckets.
    Early sessions tend to have better breakouts; late sessions are riskier.
    """
    n = len(bars)
    if n < 30:
        return []
    third = n // 3
    # Pre-compute win rates per bucket by measuring 10-bar forward returns
    atr = _atr(bars, 14)
    bucket_returns: dict[str, list[float]] = {"early": [], "mid": [], "late": []}
    for i in range(20, n - 10):
        if atr[i] <= 0:
            continue
        fwd_return = (bars[min(i + 10, n - 1)].close - bars[i].close) / atr[i]
        if i < third:
            bucket_returns["early"].append(fwd_return)
        elif i < 2 * third:
            bucket_returns["mid"].append(fwd_return)
        else:
            bucket_returns["late"].append(fwd_return)

    # Rank buckets by average absolute return
    bucket_scores: dict[str, float] = {}
    for name, rets in bucket_returns.items():
        if rets:
            avg_abs = sum(abs(r) for r in rets) / len(rets)
            win_pct = sum(1 for r in rets if r > 0) / len(rets)
            bucket_scores[name] = win_pct * 100
        else:
            bucket_scores[name] = 50.0

    signals: list[AlphaSignal] = []
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    for i in range(20, n):
        if i < third:
            bucket = "early"
        elif i < 2 * third:
            bucket = "mid"
        else:
            bucket = "late"
        score = bucket_scores.get(bucket, 50.0)
        if score >= 55:
            direction = "LONG" if ema9[i] > ema21[i] else "SHORT"
            signals.append(AlphaSignal(i, _clamp(score), direction))
    return signals


def alpha_consecutive_bodies(bars: list[Bar]) -> list[AlphaSignal]:
    """7. Consecutive Body Direction.

    Count consecutive bullish/bearish candle bodies.
    3+ consecutive same-direction bodies predict continuation.
    """
    signals: list[AlphaSignal] = []
    for i in range(3, len(bars)):
        # Count consecutive bullish
        bull_count = 0
        for k in range(i, max(i - 8, -1), -1):
            if bars[k].is_bullish:
                bull_count += 1
            else:
                break
        # Count consecutive bearish
        bear_count = 0
        for k in range(i, max(i - 8, -1), -1):
            if not bars[k].is_bullish and bars[k].close != bars[k].open:
                bear_count += 1
            else:
                break

        if bull_count >= 3:
            score = _clamp(50 + bull_count * 10)
            signals.append(AlphaSignal(i, score, "LONG"))
        elif bear_count >= 3:
            score = _clamp(50 + bear_count * 10)
            signals.append(AlphaSignal(i, score, "SHORT"))
    return signals


def alpha_wick_ratio(bars: list[Bar]) -> list[AlphaSignal]:
    """8. Wick Ratio Alpha.

    Upper wick / body and lower wick / body ratios.
    High wick ratios signal rejection.
    """
    signals: list[AlphaSignal] = []
    for i in range(1, len(bars)):
        b = bars[i]
        body = b.body
        if body < 0.001:
            continue
        upper_wick = b.high - max(b.open, b.close)
        lower_wick = min(b.open, b.close) - b.low
        upper_ratio = upper_wick / body
        lower_ratio = lower_wick / body

        if upper_ratio >= 2.0:
            # Strong upper wick rejection: bearish signal
            score = _clamp(min(upper_ratio * 25, 95))
            signals.append(AlphaSignal(i, score, "SHORT"))
        elif lower_ratio >= 2.0:
            # Strong lower wick rejection: bullish signal
            score = _clamp(min(lower_ratio * 25, 95))
            signals.append(AlphaSignal(i, score, "LONG"))
    return signals


def alpha_gap_fill(bars: list[Bar]) -> list[AlphaSignal]:
    """9. Gap Fill Probability.

    When price gaps from previous close, measure fill probability
    and generate signal toward the gap fill direction.
    """
    atr = _atr(bars, 14)
    signals: list[AlphaSignal] = []
    for i in range(1, len(bars)):
        if atr[i] <= 0:
            continue
        gap = bars[i].open - bars[i - 1].close
        gap_norm = abs(gap) / atr[i]
        if gap_norm >= 0.5:
            # Gap detected; signal toward fill direction
            if gap > 0:
                # Gap up; fill direction is SHORT
                direction = "SHORT"
            else:
                # Gap down; fill direction is LONG
                direction = "LONG"
            # Check historical fill rate over next 10 bars
            fill_count = 0
            check_count = 0
            for prev in range(max(1, i - 50), i):
                prev_gap = bars[prev].open - bars[prev - 1].close
                if abs(prev_gap) / atr[prev] >= 0.5 if atr[prev] > 0 else False:
                    check_count += 1
                    # Did it fill?
                    target_fill = bars[prev - 1].close
                    for fwd in range(prev, min(prev + 10, len(bars))):
                        if prev_gap > 0 and bars[fwd].low <= target_fill:
                            fill_count += 1
                            break
                        elif prev_gap < 0 and bars[fwd].high >= target_fill:
                            fill_count += 1
                            break
            fill_rate = fill_count / check_count if check_count > 0 else 0.5
            score = _clamp(fill_rate * 100)
            if score >= 40:
                signals.append(AlphaSignal(i, score, direction))
    return signals


def alpha_volatility_regime_persistence(bars: list[Bar]) -> list[AlphaSignal]:
    """10. Volatility Regime Persistence.

    Classifies vol regime (low/normal/high) and measures duration.
    Long regime durations signal imminent regime change.
    """
    atr = _atr(bars, 14)
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)

    # Compute rolling ATR percentile for regime classification
    signals: list[AlphaSignal] = []
    regime_duration = 0
    prev_regime = ""

    for i in range(50, len(bars)):
        if atr[i] <= 0:
            continue
        # Use 50-bar lookback for ATR percentile
        window = atr[max(0, i - 50):i + 1]
        window_sorted = sorted(window)
        rank = window_sorted.index(atr[i]) / max(len(window_sorted) - 1, 1)

        if rank <= 0.25:
            regime = "low"
        elif rank >= 0.75:
            regime = "high"
        else:
            regime = "normal"

        if regime == prev_regime:
            regime_duration += 1
        else:
            regime_duration = 1
            prev_regime = regime

        # Long duration in low vol = breakout imminent
        if regime == "low" and regime_duration >= 15:
            score = _clamp(50 + regime_duration * 2)
            direction = "LONG" if ema9[i] > ema21[i] else "SHORT"
            signals.append(AlphaSignal(i, score, direction))
        # Long duration in high vol = mean reversion imminent
        elif regime == "high" and regime_duration >= 10:
            score = _clamp(50 + regime_duration * 2)
            # Contrarian to recent direction
            direction = "SHORT" if ema9[i] > ema21[i] else "LONG"
            signals.append(AlphaSignal(i, score, direction))
    return signals


def alpha_level_proximity_bounce(bars: list[Bar]) -> list[AlphaSignal]:
    """11. Level Proximity Bounce Rate.

    At PD levels (approximated as session extremes), measure bounce vs break
    probability based on approach speed (ATR of last 3 bars vs ATR14).
    """
    atr14 = _atr(bars, 14)
    signals: list[AlphaSignal] = []

    for i in range(80, len(bars)):
        # Use rolling 80-bar high/low as proxy for PD levels
        window = bars[i - 80:i]
        pdh = max(b.high for b in window)
        pdl = min(b.low for b in window)
        pdc = bars[i - 1].close

        # Approach speed: ATR of last 3 bars
        recent_trs = [
            bars[k].high - bars[k].low for k in range(i - 2, i + 1)
        ]
        approach_atr = sum(recent_trs) / 3.0
        if atr14[i] <= 0:
            continue
        speed_ratio = approach_atr / atr14[i]

        price = bars[i].close
        atr_val = atr14[i]

        # Near PDH
        if abs(price - pdh) <= 0.3 * atr_val:
            if speed_ratio <= 0.8:
                # Slow approach: likely bounce (rejection)
                score = _clamp(70 + (1.0 - speed_ratio) * 50)
                signals.append(AlphaSignal(i, score, "SHORT"))
            elif speed_ratio >= 1.5:
                # Fast approach: likely breakout
                score = _clamp(60 + speed_ratio * 15)
                signals.append(AlphaSignal(i, score, "LONG"))

        # Near PDL
        if abs(price - pdl) <= 0.3 * atr_val:
            if speed_ratio <= 0.8:
                score = _clamp(70 + (1.0 - speed_ratio) * 50)
                signals.append(AlphaSignal(i, score, "LONG"))
            elif speed_ratio >= 1.5:
                score = _clamp(60 + speed_ratio * 15)
                signals.append(AlphaSignal(i, score, "SHORT"))
    return signals


def alpha_ema_ribbon_spread(bars: list[Bar]) -> list[AlphaSignal]:
    """12. EMA Ribbon Spread.

    EMA9 - EMA21 spread normalized by ATR. Narrow spreads predict breakouts;
    wide spreads predict mean reversion.
    """
    closes = [b.close for b in bars]
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    atr = _atr(bars, 14)
    signals: list[AlphaSignal] = []

    for i in range(21, len(bars)):
        if atr[i] <= 0:
            continue
        spread = (ema9[i] - ema21[i]) / atr[i]
        abs_spread = abs(spread)

        if abs_spread <= 0.15:
            # Very narrow spread: breakout imminent
            # Direction from slight EMA bias
            score = _clamp(80 - abs_spread * 200)
            direction = "LONG" if spread >= 0 else "SHORT"
            signals.append(AlphaSignal(i, score, direction))
        elif abs_spread >= 2.5:
            # Very wide spread: mean reversion likely
            score = _clamp(min(abs_spread * 20, 90))
            direction = "SHORT" if spread > 0 else "LONG"
            signals.append(AlphaSignal(i, score, direction))
    return signals


# ---------------------------------------------------------------------------
# Alpha factor registry
# ---------------------------------------------------------------------------

ALPHA_FACTORS: list[tuple[str, Callable[[list[Bar]], list[AlphaSignal]], str]] = [
    (
        "VWAP Deviation",
        alpha_vwap_deviation,
        "RCS.LVLQ or new VWAP proximity gate",
    ),
    (
        "Volume Climax",
        alpha_volume_climax,
        "ABT enhancement or new contrarian filter",
    ),
    (
        "ATR Contraction-Expansion",
        alpha_atr_contraction_expansion,
        "Compression Engine (Section 8) expansion timing",
    ),
    (
        "Order Flow Imbalance",
        alpha_order_flow_imbalance,
        "MOM module (Section 13) as additional confirmation",
    ),
    (
        "Momentum Divergence",
        alpha_momentum_divergence,
        "MOM.DIV enhancement (Section 13.2)",
    ),
    (
        "Time-of-Day Edge",
        alpha_time_of_day,
        "TIME component in RCS (Section 16.6)",
    ),
    (
        "Consecutive Bodies",
        alpha_consecutive_bodies,
        "BEH component in RCS (Section 16.3)",
    ),
    (
        "Wick Ratio",
        alpha_wick_ratio,
        "New rejection filter for Setup C/D entries",
    ),
    (
        "Gap Fill Probability",
        alpha_gap_fill,
        "New gap-aware gate in Session Governor (Section 3)",
    ),
    (
        "Volatility Regime Persistence",
        alpha_volatility_regime_persistence,
        "Regime Banner (Section 17) persistence enrichment",
    ),
    (
        "Level Proximity Bounce",
        alpha_level_proximity_bounce,
        "Setup A/B entry trigger speed filter",
    ),
    (
        "EMA Ribbon Spread",
        alpha_ema_ribbon_spread,
        "TAS module (Section 12) spread-based gate",
    ),
]


# ---------------------------------------------------------------------------
# Core discovery engine
# ---------------------------------------------------------------------------

def _test_alpha_on_scenario(
    name: str,
    alpha_fn: Callable[[list[Bar]], list[AlphaSignal]],
    scenario: Scenario,
    integration_point: str,
) -> AlphaMetrics:
    """Test one alpha factor on one scenario and return metrics."""
    bars = scenario.bars
    atr = _atr(bars, 14)
    satva_scores = _satva_baseline_signals(bars)

    signals = alpha_fn(bars)
    metrics = _evaluate_signals(bars, signals, atr, satva_scores)
    metrics.name = name
    metrics.integration_point = integration_point
    return metrics


def discover_alphas(n_bars: int = 500) -> list[AlphaResult]:
    """Discover and rank alpha factors across all 10 scenarios.

    Generates all scenarios, tests all 12 alpha factors, ranks by combined
    score (hit_rate * avg_R * orthogonality), prints a ranked table, and
    returns the top 5 alphas with recommended integration points.
    """
    scenarios = generate_all_scenarios(n_bars)
    results: list[AlphaResult] = []

    for name, alpha_fn, integration in ALPHA_FACTORS:
        ar = AlphaResult(name=name)
        for scenario in scenarios:
            metrics = _test_alpha_on_scenario(
                name, alpha_fn, scenario, integration,
            )
            metrics.integration_point = integration
            ar.metrics_by_scenario[scenario.name] = metrics
        ar.compute_aggregate()
        ar.aggregate.integration_point = integration
        results.append(ar)

    # Sort by combined score descending
    results.sort(key=lambda r: r.aggregate.combined_score, reverse=True)

    # Print ranked table
    _print_ranked_table(results)

    # Return top 5 with integration recommendations
    top5 = results[:5]
    print("\n" + "=" * 78)
    print("TOP 5 ALPHA FACTORS — INTEGRATION RECOMMENDATIONS")
    print("=" * 78)
    for rank, ar in enumerate(top5, 1):
        a = ar.aggregate
        print(f"\n  #{rank}: {a.name}")
        print(f"      Combined Score : {a.combined_score:8.2f}")
        print(f"      Hit Rate       : {a.hit_rate:8.1f}%")
        print(f"      Avg R          : {a.avg_r:8.3f}")
        print(f"      Info Ratio     : {a.information_ratio:8.3f}")
        print(f"      Orthogonality  : {a.orthogonality:8.3f}")
        print(f"      Signal Count   : {a.signal_count:8d}")
        print(f"      Integration    : {a.integration_point}")

    return results


def _print_ranked_table(results: list[AlphaResult]) -> None:
    """Print a formatted table of ranked alpha factors."""
    print("\n" + "=" * 110)
    print(f"{'Rank':<5} {'Alpha Factor':<30} {'HitRate%':>8} {'AvgR':>8} "
          f"{'FP%':>8} {'InfoRatio':>10} {'Ortho':>8} {'Signals':>8} "
          f"{'Combined':>10}")
    print("-" * 110)
    for rank, ar in enumerate(results, 1):
        a = ar.aggregate
        print(f"{rank:<5} {a.name:<30} {a.hit_rate:>7.1f}% {a.avg_r:>8.3f} "
              f"{a.false_positive_rate:>7.1f}% {a.information_ratio:>10.3f} "
              f"{a.orthogonality:>8.3f} {a.signal_count:>8d} "
              f"{a.combined_score:>10.2f}")
    print("=" * 110)


# ---------------------------------------------------------------------------
# Combination backtester
# ---------------------------------------------------------------------------

def backtest_alpha_combo(
    alphas: list[tuple[str, Callable[[list[Bar]], list[AlphaSignal]]]],
    scenario: Scenario,
) -> dict[str, float]:
    """Test combinations of alpha factors as additional filters.

    Measures incremental improvement to win rate and expectancy when
    multiple alphas must agree (AND logic) for a signal.

    Args:
        alphas: List of (name, alpha_function) tuples to combine.
        scenario: The market scenario to test on.

    Returns:
        Dictionary with baseline and enhanced metrics.
    """
    bars = scenario.bars
    atr = _atr(bars, 14)
    satva_scores = _satva_baseline_signals(bars)

    # Collect per-bar signal sets for each alpha
    alpha_bar_signals: list[dict[int, AlphaSignal]] = []
    for name, alpha_fn in alphas:
        signals = alpha_fn(bars)
        bar_map: dict[int, AlphaSignal] = {}
        for s in signals:
            if s.bar_index not in bar_map or s.score > bar_map[s.bar_index].score:
                bar_map[s.bar_index] = s
        alpha_bar_signals.append(bar_map)

    # Find bars where ALL alphas fire and agree on direction
    combo_signals: list[AlphaSignal] = []
    all_bars_with_any: set[int] = set()
    for bmap in alpha_bar_signals:
        all_bars_with_any.update(bmap.keys())

    for bar_idx in sorted(all_bars_with_any):
        if all(bar_idx in bmap for bmap in alpha_bar_signals):
            sigs = [bmap[bar_idx] for bmap in alpha_bar_signals]
            directions = {s.direction for s in sigs if s.direction != "NEUTRAL"}
            if len(directions) == 1:
                direction = directions.pop()
                avg_score = sum(s.score for s in sigs) / len(sigs)
                combo_signals.append(AlphaSignal(bar_idx, avg_score, direction))

    # Evaluate baseline (individual alphas averaged) and combo
    individual_metrics: list[AlphaMetrics] = []
    for name, alpha_fn in alphas:
        signals = alpha_fn(bars)
        m = _evaluate_signals(bars, signals, atr, satva_scores)
        individual_metrics.append(m)

    combo_metrics = _evaluate_signals(bars, combo_signals, atr, satva_scores)

    # Compute baseline averages
    baseline_hit = (
        sum(m.hit_rate for m in individual_metrics) / len(individual_metrics)
        if individual_metrics else 0.0
    )
    baseline_r = (
        sum(m.avg_r for m in individual_metrics) / len(individual_metrics)
        if individual_metrics else 0.0
    )
    baseline_count = sum(m.signal_count for m in individual_metrics)
    baseline_expectancy = baseline_hit / 100.0 * baseline_r

    combo_expectancy = combo_metrics.hit_rate / 100.0 * combo_metrics.avg_r

    result = {
        "scenario": scenario.name,
        "n_alphas_combined": len(alphas),
        "baseline_hit_rate": baseline_hit,
        "baseline_avg_r": baseline_r,
        "baseline_signal_count": baseline_count,
        "baseline_expectancy": baseline_expectancy,
        "combo_hit_rate": combo_metrics.hit_rate,
        "combo_avg_r": combo_metrics.avg_r,
        "combo_signal_count": combo_metrics.signal_count,
        "combo_expectancy": combo_expectancy,
        "hit_rate_improvement": combo_metrics.hit_rate - baseline_hit,
        "expectancy_improvement": combo_expectancy - baseline_expectancy,
    }
    return result


def run_combo_analysis(
    top_results: list[AlphaResult],
    n_bars: int = 500,
) -> None:
    """Run combination backtests on the top alpha factors."""
    scenarios = generate_all_scenarios(n_bars)
    top_names = [r.name for r in top_results[:5]]

    # Build lookup for alpha functions
    fn_lookup: dict[str, Callable[[list[Bar]], list[AlphaSignal]]] = {
        name: fn for name, fn, _ in ALPHA_FACTORS
    }

    # Test pairwise and triple combinations
    print("\n" + "=" * 100)
    print("ALPHA COMBINATION BACKTEST")
    print("=" * 100)

    combos_to_test: list[list[str]] = []
    # Pairwise
    for i in range(min(5, len(top_names))):
        for j in range(i + 1, min(5, len(top_names))):
            combos_to_test.append([top_names[i], top_names[j]])
    # Best triple
    if len(top_names) >= 3:
        combos_to_test.append(top_names[:3])

    for combo_names in combos_to_test:
        alpha_list = [(n, fn_lookup[n]) for n in combo_names if n in fn_lookup]
        if len(alpha_list) < 2:
            continue

        combo_label = " + ".join(combo_names)
        print(f"\n  Combo: {combo_label}")
        print(f"  {'Scenario':<20} {'BL Hit%':>8} {'Combo Hit%':>10} "
              f"{'BL AvgR':>8} {'Combo AvgR':>10} {'Signals':>8} "
              f"{'Expect Impr':>12}")
        print(f"  {'-' * 88}")

        total_improvement = 0.0
        scenario_count = 0
        for scenario in scenarios:
            r = backtest_alpha_combo(alpha_list, scenario)
            total_improvement += r["expectancy_improvement"]
            scenario_count += 1
            print(f"  {r['scenario']:<20} {r['baseline_hit_rate']:>7.1f}% "
                  f"{r['combo_hit_rate']:>9.1f}% {r['baseline_avg_r']:>8.3f} "
                  f"{r['combo_avg_r']:>10.3f} {r['combo_signal_count']:>8d} "
                  f"{r['expectancy_improvement']:>+11.4f}")

        avg_improvement = total_improvement / scenario_count if scenario_count else 0
        print(f"  {'AVERAGE':<20} {'':>8} {'':>10} {'':>8} {'':>10} {'':>8} "
              f"{avg_improvement:>+11.4f}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 78)
    print("SATVA v15 ALPHA DISCOVERY ENGINE")
    print("Testing 12 alpha factors across 10 market scenarios")
    print("=" * 78)

    results = discover_alphas(n_bars=500)

    # Run combination analysis on top alphas
    run_combo_analysis(results, n_bars=500)

    print("\n" + "=" * 78)
    print("Discovery complete.")
    print("=" * 78)


if __name__ == "__main__":
    main()
