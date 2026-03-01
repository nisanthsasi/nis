"""Tests for all 5 trading strategy validators: VORTEX, NEXUS, PRISM, FLUX, TITAN."""

import pytest
from prompt_validator.result import Severity, Category
from prompt_validator.trading_validator import TradingValidator


# =====================================================================
# VORTEX — Momentum/Trend Following
# =====================================================================

from prompt_validator import vortex_rules

MINIMAL_VORTEX = """
You are a deterministic momentum trading system.
SECTION 0 — AXIOMS
A0. Determinism.
SECTION 1 — DATA CONTRACT
OPEN, HIGH, LOW, CLOSE, VOLUME. CRITICAL-PATH (if missing → HALT).
SECTION 2 — TREND IDENTIFICATION
EMA_FAST = EMA(CLOSE, 9)
EMA_SLOW = EMA(CLOSE, 21)
ADX = ADX(HIGH, LOW, CLOSE, 14)
Golden cross: EMA_FAST cross above EMA_SLOW
Strong trend: ADX > 25. No trend: ADX < 20.
SECTION 3 — MOMENTUM SCORING
RSI = RSI(CLOSE, 14)
MACD = EMA(12) - EMA(26)
TREND_SCORE = 0.35*ADX + 0.30*MACD + 0.20*RSI + 0.15*ROC
MOMENTUM_SCORE = 0.40*RSI + 0.30*MACD + 0.30*VOL
SECTION 4 — ENTRY RULES
All conditions must be true.
SECTION 5 — POSITION SIZING
Risk per trade = 1.0% of account.
SECTION 6 — TRAILING STOP
TRAIL_STOP = CLOSE - 2.0 * ATR_14
Chandelier exit. Trailing stop ratchets up.
SECTION 7 — EXIT RULES
Trail stop hit or crossover reversal. Daily limit → HALT.
SECTION 8 — FSM
SCANNING, TREND_CONFIRMED, RIDING, TRAILING, EXIT, COOLDOWN
SCANNING → TREND_CONFIRMED: ADX > 25
TREND_CONFIRMED → RIDING: entry filled
RIDING → TRAILING: 1*ATR profit
TRAILING → EXIT: trail hit
EXIT → COOLDOWN: closed
SECTION 9 — RISK MANAGEMENT
Max daily loss: 3% → HALT. Max drawdown limit.
SECTION 10 — OUTPUT FORMAT
Print every signal in exact order.
SECTION 11 — GOVERNANCE LOG
GOV-VTX-001
Section: 6
Before: old trail
After: new trail
Rationale: wider trail
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestVortex:
    def test_section_completeness(self):
        assert vortex_rules.check_section_completeness(MINIMAL_VORTEX) == []

    def test_missing_sections(self):
        issues = vortex_rules.check_section_completeness("SECTION 0 — AXIOMS")
        assert len(issues) == 1 and issues[0].severity == Severity.ERROR

    def test_formula_definitions(self):
        assert vortex_rules.check_formula_definitions(MINIMAL_VORTEX) == []

    def test_fsm_states(self):
        assert vortex_rules.check_fsm_states(MINIMAL_VORTEX) == []

    def test_fsm_transitions(self):
        assert vortex_rules.check_fsm_transitions(MINIMAL_VORTEX) == []

    def test_ema_crossover(self):
        assert vortex_rules.check_ema_crossover(MINIMAL_VORTEX) == []

    def test_trailing_stop(self):
        assert vortex_rules.check_trailing_stop(MINIMAL_VORTEX) == []

    def test_determinism_clean(self):
        assert vortex_rules.check_determinism("All computed.") == []

    def test_determinism_dirty(self):
        issues = vortex_rules.check_determinism("Use your judgment here.")
        assert len(issues) == 1

    def test_integration(self):
        with open("prompts/vortex_momentum.txt") as f: prompt = f.read()
        r = TradingValidator("vortex").validate(prompt)
        assert r["domain"].score >= 95
        assert r["combined_score"] >= 90


# =====================================================================
# NEXUS — Mean Reversion
# =====================================================================

from prompt_validator import nexus_rules

MINIMAL_NEXUS = """
You are a deterministic mean reversion system.
SECTION 0 — AXIOMS
A0. Determinism.
SECTION 1 — DATA CONTRACT
VWAP, SMA. CRITICAL-PATH (if missing → HALT).
SECTION 2 — FAIR VALUE CALCULATION
FAIR_VALUE = 0.40*VWAP + 0.35*SMA + 0.25*EMA
BOLLINGER_UPPER = SMA + 2*STDDEV
BOLLINGER_LOWER = SMA - 2*STDDEV
SECTION 3 — DEVIATION SCORING
Z_SCORE = (CLOSE - FAIR_VALUE) / STDDEV
DEVIATION = |CLOSE - FAIR_VALUE| / ATR
REVERSION_SCORE = 0.35*Z + 0.30*BB + 0.20*RSI + 0.15*VOL
Oversold: Z_SCORE < -2.0. Overbought: Z > 2.0.
SECTION 4 — ENTRY RULES
Long when oversold, short when overbought.
SECTION 5 — POSITION SIZING
Risk per trade = 0.75%.
SECTION 6 — EXIT RULES
Target = FAIR_VALUE. Stop = 1*ATR.
MAE = Max Adverse Excursion.
SECTION 7 — TIME STOPS
TIME_STOP = 20 bars. Max holding period, time-based exit.
SECTION 8 — FSM
NEUTRAL, DEVIATED, ENTRY, REVERTING, TARGET, TIME_STOP
NEUTRAL → DEVIATED: Z exceeds threshold
DEVIATED → ENTRY: conditions met
ENTRY → REVERTING: toward fair value
REVERTING → TARGET: reached fair value
ENTRY → TIME_STOP: 20 bars elapsed
SECTION 9 — RISK MANAGEMENT
Max daily loss: 2% → HALT.
SECTION 10 — OUTPUT FORMAT
Print every signal in exact order.
SECTION 11 — GOVERNANCE LOG
GOV-NXS-001
Section: 7
Before: 15 bars
After: 20 bars
Rationale: reduce premature exits
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestNexus:
    def test_section_completeness(self):
        assert nexus_rules.check_section_completeness(MINIMAL_NEXUS) == []

    def test_formula_definitions(self):
        assert nexus_rules.check_formula_definitions(MINIMAL_NEXUS) == []

    def test_fsm_states(self):
        assert nexus_rules.check_fsm_states(MINIMAL_NEXUS) == []

    def test_fsm_transitions(self):
        assert nexus_rules.check_fsm_transitions(MINIMAL_NEXUS) == []

    def test_mean_definition(self):
        assert nexus_rules.check_mean_definition(MINIMAL_NEXUS) == []

    def test_deviation_thresholds(self):
        assert nexus_rules.check_deviation_thresholds(MINIMAL_NEXUS) == []

    def test_time_stop(self):
        assert nexus_rules.check_time_stop(MINIMAL_NEXUS) == []

    def test_integration(self):
        with open("prompts/nexus_reversion.txt") as f: prompt = f.read()
        r = TradingValidator("nexus").validate(prompt)
        assert r["domain"].score >= 95
        assert r["combined_score"] >= 90


# =====================================================================
# PRISM — Options/Greeks
# =====================================================================

from prompt_validator import prism_rules

MINIMAL_PRISM = """
You are a deterministic options system.
SECTION 0 — AXIOMS
A0. Determinism.
SECTION 1 — DATA CONTRACT
UNDERLYING, STRIKE, IV. CRITICAL-PATH (if missing → HALT).
SECTION 2 — GREEKS ENGINE
DELTA = dV/dS
GAMMA = dDelta/dS
THETA = dV/dt
VEGA = dV/dIV
Rho = dV/dr
SECTION 3 — VOLATILITY SURFACE
IV_RANK = (current - low) / (high - low) * 100
Implied volatility surface, vol smile analysis, IV skew.
SECTION 4 — STRATEGY DEFINITIONS
Iron condor, vertical spread, butterfly, straddle, strangle, calendar spread.
SECTION 5 — ENTRY RULES
IV_RANK > 50, DTE 30-45 days, 16-delta short strikes.
Assignment risk: DTE < 7.
SECTION 6 — POSITION SIZING
MAX_LOSS = width - credit
Max 3% per trade. Portfolio limit.
BREAKEVEN = strike ± credit.
POP = probability of profit >= 60%.
SECTION 7 — ADJUSTMENT RULES
Adjust if delta exceeds ±0.30.
SECTION 8 — EXIT RULES
Close at 50% profit or 2x loss. DTE < 3 → close.
SECTION 9 — FSM
SCANNING, PRICED, LEGGED_IN, MANAGING, ADJUSTING, CLOSED
SCANNING → PRICED: IV conditions met
PRICED → LEGGED_IN: filled
LEGGED_IN → MANAGING: confirmed
MANAGING → ADJUSTING: trigger hit
MANAGING → CLOSED: target/stop
SECTION 10 — RISK MANAGEMENT
Max daily loss: 5% → HALT. Max positions: 5.
IV_RANK = normalized volatility percentile.
SECTION 11 — OUTPUT FORMAT
Print every position update.
SECTION 12 — GOVERNANCE LOG
GOV-PRM-001
Section: 5
Before: 20-delta
After: 16-delta
Rationale: higher POP
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestPrism:
    def test_section_completeness(self):
        assert prism_rules.check_section_completeness(MINIMAL_PRISM) == []

    def test_formula_definitions(self):
        assert prism_rules.check_formula_definitions(MINIMAL_PRISM) == []

    def test_fsm_states(self):
        assert prism_rules.check_fsm_states(MINIMAL_PRISM) == []

    def test_fsm_transitions(self):
        assert prism_rules.check_fsm_transitions(MINIMAL_PRISM) == []

    def test_greeks_coverage(self):
        assert prism_rules.check_greeks_coverage(MINIMAL_PRISM) == []

    def test_iv_surface(self):
        assert prism_rules.check_iv_surface(MINIMAL_PRISM) == []

    def test_strategy_definitions(self):
        assert prism_rules.check_strategy_definitions(MINIMAL_PRISM) == []

    def test_expiry_risk(self):
        assert prism_rules.check_expiry_risk(MINIMAL_PRISM) == []

    def test_integration(self):
        with open("prompts/prism_options.txt") as f: prompt = f.read()
        r = TradingValidator("prism").validate(prompt)
        assert r["domain"].score >= 95
        assert r["combined_score"] >= 90


# =====================================================================
# FLUX — Scalping/HFT
# =====================================================================

from prompt_validator import flux_rules

MINIMAL_FLUX = """
You are a deterministic scalping system.
SECTION 0 — AXIOMS
A0. Determinism.
SECTION 1 — DATA CONTRACT
BID, ASK, LAST, ORDER_BOOK. CRITICAL-PATH (if missing → HALT). Feed health check.
SECTION 2 — MICROSTRUCTURE
SPREAD = ASK - BID
Bid-ask analysis, best bid, best ask, order book depth.
SECTION 3 — ORDER FLOW
OFI = (bid_delta - ask_delta) / total_delta
Trade imbalance calculation.
SECTION 4 — ENTRY RULES
OFI > 0.6 AND SPREAD <= 2 ticks.
SECTION 5 — FILL QUALITY
FILL_RATIO = filled / ordered
VWAP_SLIP = |exec - VWAP| / TICK
SECTION 6 — EXIT RULES
Target: 3-5 ticks. Stop: 2 ticks.
TICK_PNL = (exit - entry) / TICK_SIZE
EDGE_PER_TRADE = avg_win*wr - avg_loss*lr - costs
SECTION 7 — FSM
IDLE, STALKING, STRIKE, FILL, SCALP_EXIT, RATE_LIMITED
IDLE → STALKING: conditions developing
STALKING → STRIKE: entry confirmed
STRIKE → FILL: order filled
FILL → SCALP_EXIT: target/stop hit
SCALP_EXIT → IDLE: flat
SECTION 8 — RATE LIMITS
Max trades per minute: 10 (circuit breaker, throttle).
TRADE_RATE = trades/minute normalized.
SECTION 9 — RISK MANAGEMENT
Max daily loss: 1% → HALT (kill switch). Circuit breaker.
LATENCY_BUDGET = 5 milliseconds.
SECTION 10 — OUTPUT FORMAT
Print every trade in exact order.
SECTION 11 — GOVERNANCE LOG
GOV-FLX-001
Section: 8
Before: 20/min
After: 10/min
Rationale: prevent overtrading
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestFlux:
    def test_section_completeness(self):
        assert flux_rules.check_section_completeness(MINIMAL_FLUX) == []

    def test_formula_definitions(self):
        assert flux_rules.check_formula_definitions(MINIMAL_FLUX) == []

    def test_fsm_states(self):
        assert flux_rules.check_fsm_states(MINIMAL_FLUX) == []

    def test_fsm_transitions(self):
        assert flux_rules.check_fsm_transitions(MINIMAL_FLUX) == []

    def test_latency_spec(self):
        assert flux_rules.check_latency_spec(MINIMAL_FLUX) == []

    def test_spread_analysis(self):
        assert flux_rules.check_spread_analysis(MINIMAL_FLUX) == []

    def test_rate_limits(self):
        assert flux_rules.check_rate_limits(MINIMAL_FLUX) == []

    def test_no_rate_limits(self):
        issues = flux_rules.check_rate_limits("No limits here.")
        assert len(issues) == 1

    def test_integration(self):
        with open("prompts/flux_scalping.txt") as f: prompt = f.read()
        r = TradingValidator("flux").validate(prompt)
        assert r["domain"].score >= 95
        assert r["combined_score"] >= 90


# =====================================================================
# TITAN — Swing/Multi-day
# =====================================================================

from prompt_validator import titan_rules

MINIMAL_TITAN = """
You are a deterministic swing trading system.
SECTION 0 — AXIOMS
A0. Determinism.
SECTION 1 — DATA CONTRACT
DAILY, 4H, 1H data. CRITICAL-PATH (if missing → HALT).
SECTION 2 — MULTI-TIMEFRAME ANALYSIS
Daily EMA_50 vs EMA_200. 4H structure. Higher timeframe alignment.
SECTION 3 — SWING STRUCTURE
SWING_HIGH = HIGH[i] > HIGH[i-1] AND HIGH[i] > HIGH[i+1]
SWING_LOW = LOW[i] < LOW[i-1] AND LOW[i] < LOW[i+1]
Higher high, higher low, pivot points.
PIVOT = (H+L+C)/3
ATR_DAILY = ATR(14) on daily.
SECTION 4 — ENTRY RULES
Multi-timeframe alignment required.
SECTION 5 — POSITION SIZING
R_MULTIPLE = |entry-stop| / ATR_DAILY
Risk per trade = 1%.
SECTION 6 — PARTIAL EXITS
T1: 1R → 33%. T2: 2R → 33%. T3: trail.
PARTIAL_SIZE = 0.33. Scale out plan.
SECTION 7 — GAP RISK
GAP_RISK = max_gap * position_value
Overnight: max 50%. Pre-market gap handling.
SECTION 8 — FSM
FLAT, SETUP, ENTRY, HOLDING, PARTIAL, EXIT
FLAT → SETUP: alignment detected
SETUP → ENTRY: trigger fires
ENTRY → HOLDING: confirmed
HOLDING → PARTIAL: T1 reached
PARTIAL → EXIT: final target or trail
SECTION 9 — RISK MANAGEMENT
Max drawdown: 8% → HALT. Weekly limit 4%.
DRAWDOWN = (peak - current) / peak.
SECTION 10 — OUTPUT FORMAT
Print every swing update.
SECTION 11 — GOVERNANCE LOG
GOV-TTN-001
Section: 7
Before: 75% overnight
After: 50% overnight
Rationale: reduce gap exposure
FREEZE DECLARATION
LOCK STATEMENT
"""


class TestTitan:
    def test_section_completeness(self):
        assert titan_rules.check_section_completeness(MINIMAL_TITAN) == []

    def test_formula_definitions(self):
        assert titan_rules.check_formula_definitions(MINIMAL_TITAN) == []

    def test_fsm_states(self):
        assert titan_rules.check_fsm_states(MINIMAL_TITAN) == []

    def test_fsm_transitions(self):
        assert titan_rules.check_fsm_transitions(MINIMAL_TITAN) == []

    def test_multi_timeframe(self):
        assert titan_rules.check_multi_timeframe(MINIMAL_TITAN) == []

    def test_swing_structure(self):
        assert titan_rules.check_swing_structure(MINIMAL_TITAN) == []

    def test_gap_risk(self):
        assert titan_rules.check_gap_risk(MINIMAL_TITAN) == []

    def test_partial_exits(self):
        assert titan_rules.check_partial_exits(MINIMAL_TITAN) == []

    def test_no_gap_risk(self):
        issues = titan_rules.check_gap_risk("No gap management.")
        assert len(issues) == 1

    def test_integration(self):
        with open("prompts/titan_swing.txt") as f: prompt = f.read()
        r = TradingValidator("titan").validate(prompt)
        assert r["domain"].score >= 95
        assert r["combined_score"] >= 90


# =====================================================================
# Cross-model tests
# =====================================================================

class TestTradingValidatorFactory:
    def test_all_models_exist(self):
        for model in ["vortex", "nexus", "prism", "flux", "titan"]:
            v = TradingValidator(model)
            assert v.model == model

    def test_invalid_model_raises(self):
        with pytest.raises(ValueError):
            TradingValidator("invalid_model")

    def test_all_prompts_score_high(self):
        models_and_files = [
            ("vortex", "prompts/vortex_momentum.txt"),
            ("nexus", "prompts/nexus_reversion.txt"),
            ("prism", "prompts/prism_options.txt"),
            ("flux", "prompts/flux_scalping.txt"),
            ("titan", "prompts/titan_swing.txt"),
        ]
        for model, path in models_and_files:
            with open(path) as f: prompt = f.read()
            r = TradingValidator(model).validate(prompt)
            assert r["combined_score"] >= 90, f"{model} scored {r['combined_score']}"
            assert r["combined_grade"] in ("A", "B"), f"{model} grade: {r['combined_grade']}"
