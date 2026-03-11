"""SATVA v15 Risk Management Optimizer.

Monte Carlo simulations and parameter optimization for the SATVA v15
risk management framework. Analyzes position sizing, session loss caps,
trade caps, cooldown rules, drawdown recovery, and MEG tuning.

All simulations use fixed seeds for reproducibility.
"""

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from prompt_validator.scenarios import Bar, Scenario, generate_all_scenarios
from prompt_validator.simulator import Trade, SimResult


# ---------------------------------------------------------------------------
# Constants from SATVA v15
# ---------------------------------------------------------------------------

RISK_PCT_STANDARD = 1.0       # 1% per trade
RISK_PCT_AFTER_1_LOSS = 0.75  # 0.75% after 1 loss
RISK_PCT_COOLDOWN = 0.5       # 0.5% during cooldown
SESSION_LOCK_R = 2.0          # 2R session loss lock
DRAWDOWN_GUARD_R = 2.5        # 2.5R drawdown guard
MAX_TRADES_SESSION = 3        # max 3 trades per session
MAX_PORTFOLIO_HEAT = 3.0      # 3% portfolio heat
COOLDOWN_CONSEC_LOSSES = 2    # consecutive losses to trigger cooldown
MEG_WINDOW = 60               # rolling 60-trade MEG window
MEG_LOCK_THRESHOLD = -0.15    # Exp_M <= -0.15 triggers MEG_LOCK
SESSIONS_PER_MONTH = 22       # approximate trading days


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TradeResult:
    """Outcome of a single simulated trade."""
    r_multiple: float
    is_win: bool
    risk_pct: float  # position size used


@dataclass
class SessionOutcome:
    """Outcome of a simulated session."""
    trades: List[TradeResult] = field(default_factory=list)
    total_r: float = 0.0
    session_locked: bool = False
    cooldown_triggered: bool = False
    num_trades: int = 0


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo session simulation."""
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    n_sessions: int
    session_outcomes: List[float] = field(default_factory=list)
    monthly_r_values: List[float] = field(default_factory=list)
    max_drawdowns: List[float] = field(default_factory=list)
    ruin_probability: float = 0.0
    expected_monthly_r: float = 0.0
    median_monthly_r: float = 0.0
    monthly_r_std: float = 0.0
    p10_monthly_r: float = 0.0
    p90_monthly_r: float = 0.0


@dataclass
class SizingResult:
    """Results from a position sizing strategy test."""
    name: str
    params: str
    total_r: float = 0.0
    cagr_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    n_trades: int = 0


# ---------------------------------------------------------------------------
# Helper: generate trade outcome
# ---------------------------------------------------------------------------

def _generate_trade(rng: random.Random, win_rate: float,
                    avg_win_r: float, avg_loss_r: float) -> Tuple[float, bool]:
    """Generate a single trade outcome (r_multiple, is_win).

    Win R is drawn from a truncated normal centered on avg_win_r.
    Loss R is drawn from a truncated normal centered on avg_loss_r (negative).
    """
    if rng.random() < win_rate:
        # Winner: avg_win_r with some variance
        r = max(0.1, rng.gauss(avg_win_r, avg_win_r * 0.3))
        return r, True
    else:
        # Loser: avg_loss_r (negative) with some variance
        r = min(-0.1, rng.gauss(avg_loss_r, abs(avg_loss_r) * 0.2))
        return r, False


# ---------------------------------------------------------------------------
# 1. Monte Carlo Session Simulator
# ---------------------------------------------------------------------------

def monte_carlo_session(win_rate: float, avg_win_r: float = 1.8,
                        avg_loss_r: float = -1.0, n_sessions: int = 10000,
                        max_trades: int = MAX_TRADES_SESSION,
                        session_lock_r: float = SESSION_LOCK_R,
                        seed: int = 42) -> MonteCarloResult:
    """Simulate N sessions of up to max_trades trades each.

    Applies SATVA v15 risk rules:
    - Position sizing reduction after losses
    - Cooldown after 2 consecutive losses (elevated gates)
    - Session lock at session_lock_r cumulative loss
    - Drawdown guard at 2.5R

    Returns distribution of session outcomes, ruin probability,
    expected monthly R, and max drawdown distribution.
    """
    rng = random.Random(seed)
    result = MonteCarloResult(
        win_rate=win_rate, avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r, n_sessions=n_sessions,
    )

    # Simulate sessions
    for _ in range(n_sessions):
        session_r = 0.0
        consec_losses = 0
        trade_losses = 0
        cooldown_active = False
        session_locked = False

        for t_num in range(max_trades):
            if session_locked:
                break

            # Determine risk percentage based on state
            if cooldown_active:
                risk_pct = RISK_PCT_COOLDOWN
                # Cooldown gates: require higher quality -- model as lower
                # probability of taking the trade at all
                if rng.random() < 0.4:
                    # Cooldown gates reject this setup
                    continue
            elif trade_losses >= 1:
                risk_pct = RISK_PCT_AFTER_1_LOSS
            else:
                risk_pct = RISK_PCT_STANDARD

            r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)

            # Scale by risk fraction relative to standard
            effective_r = r_mult * (risk_pct / RISK_PCT_STANDARD)
            session_r += effective_r

            if is_win:
                consec_losses = 0
                if cooldown_active:
                    cooldown_active = False
            else:
                consec_losses += 1
                trade_losses += 1
                if consec_losses >= COOLDOWN_CONSEC_LOSSES:
                    cooldown_active = True

            # Session lock check
            if session_r <= -session_lock_r:
                session_locked = True

            # Drawdown guard
            if session_r <= -DRAWDOWN_GUARD_R:
                session_locked = True

        result.session_outcomes.append(session_r)

    # Compute monthly R values (SESSIONS_PER_MONTH sessions per month)
    n_months = n_sessions // SESSIONS_PER_MONTH
    for m in range(n_months):
        start = m * SESSIONS_PER_MONTH
        end = start + SESSIONS_PER_MONTH
        monthly_r = sum(result.session_outcomes[start:end])
        result.monthly_r_values.append(monthly_r)

    # Compute max drawdown distribution (rolling window)
    equity_curve = []
    running = 0.0
    peak = 0.0
    for sr in result.session_outcomes:
        running += sr
        equity_curve.append(running)
        peak = max(peak, running)

    # Compute drawdowns for each month
    for m in range(n_months):
        start = m * SESSIONS_PER_MONTH
        end = start + SESSIONS_PER_MONTH
        local_equity = []
        local_running = 0.0
        local_peak = 0.0
        local_max_dd = 0.0
        for i in range(start, min(end, len(result.session_outcomes))):
            local_running += result.session_outcomes[i]
            local_peak = max(local_peak, local_running)
            dd = local_peak - local_running
            local_max_dd = max(local_max_dd, dd)
        result.max_drawdowns.append(local_max_dd)

    # Ruin: defined as losing 20R cumulative
    ruin_threshold = -20.0
    running = 0.0
    ruin_count = 0
    sim_count = 100
    rng2 = random.Random(seed + 1000)
    for _ in range(sim_count):
        eq = 0.0
        ruined = False
        for s in range(SESSIONS_PER_MONTH * 12):  # 1 year
            session_r = 0.0
            consec_losses = 0
            trade_losses = 0
            cooldown_active = False
            for t_num in range(max_trades):
                if session_r <= -session_lock_r:
                    break
                if cooldown_active:
                    rp = RISK_PCT_COOLDOWN
                    if rng2.random() < 0.4:
                        continue
                elif trade_losses >= 1:
                    rp = RISK_PCT_AFTER_1_LOSS
                else:
                    rp = RISK_PCT_STANDARD
                r_mult, is_win = _generate_trade(rng2, win_rate, avg_win_r, avg_loss_r)
                effective_r = r_mult * (rp / RISK_PCT_STANDARD)
                session_r += effective_r
                if is_win:
                    consec_losses = 0
                    if cooldown_active:
                        cooldown_active = False
                else:
                    consec_losses += 1
                    trade_losses += 1
                    if consec_losses >= COOLDOWN_CONSEC_LOSSES:
                        cooldown_active = True
            eq += session_r
            if eq <= ruin_threshold:
                ruined = True
                break
        if ruined:
            ruin_count += 1

    result.ruin_probability = ruin_count / sim_count

    # Statistics
    if result.monthly_r_values:
        result.expected_monthly_r = statistics.mean(result.monthly_r_values)
        result.median_monthly_r = statistics.median(result.monthly_r_values)
        result.monthly_r_std = statistics.stdev(result.monthly_r_values) if len(result.monthly_r_values) > 1 else 0.0
        sorted_mr = sorted(result.monthly_r_values)
        p10_idx = max(0, int(len(sorted_mr) * 0.1))
        p90_idx = min(len(sorted_mr) - 1, int(len(sorted_mr) * 0.9))
        result.p10_monthly_r = sorted_mr[p10_idx]
        result.p90_monthly_r = sorted_mr[p90_idx]

    return result


# ---------------------------------------------------------------------------
# 2. Position Sizing Optimizer
# ---------------------------------------------------------------------------

def _simulate_equity_curve(rng: random.Random, win_rate: float,
                           avg_win_r: float, avg_loss_r: float,
                           n_trades: int, sizing_fn,
                           starting_capital: float = 100000.0) -> SizingResult:
    """Simulate an equity curve using a given sizing function.

    sizing_fn(trade_num, consec_wins, consec_losses, current_capital,
              starting_capital, regime) -> risk_pct
    """
    capital = starting_capital
    peak_capital = capital
    max_dd_pct = 0.0
    monthly_returns = []
    monthly_start = capital
    trades_per_month = 0

    consec_wins = 0
    consec_losses = 0
    total_r = 0.0
    regimes = ["STRONG_TREND", "TREND", "RANGE", "UNCLEAR"]
    regime_weights = [0.15, 0.35, 0.30, 0.20]

    for t in range(n_trades):
        regime = rng.choices(regimes, weights=regime_weights, k=1)[0]
        risk_pct = sizing_fn(t, consec_wins, consec_losses, capital,
                             starting_capital, regime)
        risk_pct = max(0.1, min(risk_pct, 5.0))  # clamp

        r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)

        dollar_risk = capital * (risk_pct / 100.0)
        pnl = dollar_risk * r_mult
        capital += pnl
        capital = max(capital, 1.0)  # floor

        total_r += r_mult

        if is_win:
            consec_wins += 1
            consec_losses = 0
        else:
            consec_losses += 1
            consec_wins = 0

        peak_capital = max(peak_capital, capital)
        dd_pct = (peak_capital - capital) / peak_capital * 100.0
        max_dd_pct = max(max_dd_pct, dd_pct)

        trades_per_month += 1
        if trades_per_month >= SESSIONS_PER_MONTH * 2:  # ~2 trades/session avg
            monthly_ret = (capital - monthly_start) / monthly_start
            monthly_returns.append(monthly_ret)
            monthly_start = capital
            trades_per_month = 0

    # Final partial month
    if trades_per_month > 0:
        monthly_ret = (capital - monthly_start) / monthly_start
        monthly_returns.append(monthly_ret)

    # CAGR
    years = n_trades / (SESSIONS_PER_MONTH * 12 * 2)  # assume ~2 trades/session
    if years > 0 and capital > 0:
        cagr = (capital / starting_capital) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0

    # Sharpe
    if monthly_returns and len(monthly_returns) > 1:
        avg_ret = statistics.mean(monthly_returns)
        std_ret = statistics.stdev(monthly_returns)
        sharpe = (avg_ret / std_ret * math.sqrt(12)) if std_ret > 0 else 0.0
    else:
        sharpe = 0.0

    # Calmar
    calmar = (cagr * 100.0 / max_dd_pct) if max_dd_pct > 0 else 0.0

    res = SizingResult(name="", params="", total_r=total_r,
                       cagr_pct=cagr * 100.0, max_drawdown_pct=max_dd_pct,
                       sharpe_ratio=sharpe, calmar_ratio=calmar,
                       n_trades=n_trades)
    return res


def optimize_position_sizing(win_rate: float = 0.60, avg_win_r: float = 1.8,
                             avg_loss_r: float = -1.0, n_trades: int = 5000,
                             seed: int = 100) -> List[SizingResult]:
    """Test multiple position sizing strategies.

    Strategies:
    - Fixed fractional: 0.5%, 0.75%, 1.0%, 1.25%, 1.5%, 2.0%
    - Kelly Criterion: f* = (W*R - L) / R
    - Half-Kelly
    - Anti-martingale: increase after wins, decrease after losses
    - Regime-adaptive: size by regime type
    """
    results = []

    # Fixed fractional
    for pct in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        def make_fixed(p):
            return lambda t, cw, cl, cap, sc, reg: p
        rng = random.Random(seed)
        res = _simulate_equity_curve(rng, win_rate, avg_win_r, avg_loss_r,
                                     n_trades, make_fixed(pct))
        res.name = "Fixed Fractional"
        res.params = f"{pct}%"
        results.append(res)

    # Kelly Criterion
    W = win_rate
    L = 1.0 - win_rate
    R = avg_win_r / abs(avg_loss_r)
    kelly_f_raw = max(0.01, (W * R - L) / R) * 100.0  # as percentage
    # Cap Kelly at 5% for practical intraday use (uncapped Kelly is too
    # aggressive for intraday systems with limited diversification)
    kelly_f = min(kelly_f_raw, 5.0)

    def kelly_fn(t, cw, cl, cap, sc, reg):
        return kelly_f

    rng = random.Random(seed)
    res = _simulate_equity_curve(rng, win_rate, avg_win_r, avg_loss_r,
                                 n_trades, kelly_fn)
    res.name = "Kelly Criterion"
    res.params = f"f*={kelly_f_raw:.1f}% (capped {kelly_f:.1f}%)"
    results.append(res)

    # Half-Kelly
    half_kelly = min(kelly_f_raw / 2.0, 3.0)

    def half_kelly_fn(t, cw, cl, cap, sc, reg):
        return half_kelly

    rng = random.Random(seed)
    res = _simulate_equity_curve(rng, win_rate, avg_win_r, avg_loss_r,
                                 n_trades, half_kelly_fn)
    res.name = "Half-Kelly"
    res.params = f"f*/2={half_kelly:.2f}%"
    results.append(res)

    # Anti-martingale
    def anti_martingale_fn(t, cw, cl, cap, sc, reg):
        base = 1.0
        if cw >= 2:
            return min(base * 1.5, 2.0)
        elif cw == 1:
            return base * 1.25
        elif cl == 1:
            return base * 0.75
        elif cl >= 2:
            return base * 0.5
        return base

    rng = random.Random(seed)
    res = _simulate_equity_curve(rng, win_rate, avg_win_r, avg_loss_r,
                                 n_trades, anti_martingale_fn)
    res.name = "Anti-Martingale"
    res.params = "base=1.0%, win+25/50%, loss-25/50%"
    results.append(res)

    # Regime-adaptive
    regime_sizes = {
        "STRONG_TREND": 1.25,
        "TREND": 1.0,
        "RANGE": 0.75,
        "UNCLEAR": 0.5,
    }

    def regime_adaptive_fn(t, cw, cl, cap, sc, reg):
        return regime_sizes.get(reg, 1.0)

    rng = random.Random(seed)
    res = _simulate_equity_curve(rng, win_rate, avg_win_r, avg_loss_r,
                                 n_trades, regime_adaptive_fn)
    res.name = "Regime-Adaptive"
    res.params = "ST=1.25%, T=1.0%, R=0.75%, U=0.5%"
    results.append(res)

    return results


# ---------------------------------------------------------------------------
# 3. Session Loss Cap Optimizer
# ---------------------------------------------------------------------------

def optimize_loss_cap(win_rate: float = 0.60, avg_win_r: float = 1.8,
                      avg_loss_r: float = -1.0, n_sessions: int = 10000,
                      seed: int = 200) -> Dict[float, Dict]:
    """Test different session loss cap levels.

    Caps tested: 1.5R, 1.75R, 2.0R, 2.25R, 2.5R, 3.0R
    Measures: trigger frequency, avg opportunity cost, net monthly P&L.
    """
    caps = [1.5, 1.75, 2.0, 2.25, 2.5, 3.0]
    results = {}

    for cap in caps:
        rng = random.Random(seed)
        triggers = 0
        total_monthly_r = 0.0
        opportunity_costs = []
        session_rs = []

        for s in range(n_sessions):
            session_r = 0.0
            consec_losses = 0
            trade_losses = 0
            cooldown_active = False
            locked = False
            trades_taken = 0

            for t_num in range(MAX_TRADES_SESSION):
                if locked:
                    # Opportunity cost: estimate remaining trades' expected value
                    remaining = MAX_TRADES_SESSION - t_num
                    exp_per_trade = win_rate * avg_win_r + (1 - win_rate) * avg_loss_r
                    opportunity_costs.append(remaining * exp_per_trade)
                    break

                if cooldown_active:
                    risk_pct = RISK_PCT_COOLDOWN
                    if rng.random() < 0.4:
                        continue
                elif trade_losses >= 1:
                    risk_pct = RISK_PCT_AFTER_1_LOSS
                else:
                    risk_pct = RISK_PCT_STANDARD

                r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)
                effective_r = r_mult * (risk_pct / RISK_PCT_STANDARD)
                session_r += effective_r
                trades_taken += 1

                if is_win:
                    consec_losses = 0
                    if cooldown_active:
                        cooldown_active = False
                else:
                    consec_losses += 1
                    trade_losses += 1
                    if consec_losses >= COOLDOWN_CONSEC_LOSSES:
                        cooldown_active = True

                if session_r <= -cap:
                    locked = True
                    triggers += 1

            session_rs.append(session_r)

        # Monthly aggregation
        n_months = n_sessions // SESSIONS_PER_MONTH
        monthly_rs = []
        for m in range(n_months):
            mr = sum(session_rs[m * SESSIONS_PER_MONTH:(m + 1) * SESSIONS_PER_MONTH])
            monthly_rs.append(mr)

        avg_monthly_r = statistics.mean(monthly_rs) if monthly_rs else 0.0
        avg_opp_cost = statistics.mean(opportunity_costs) if opportunity_costs else 0.0
        trigger_rate = triggers / n_sessions * 100.0

        results[cap] = {
            "trigger_rate_pct": trigger_rate,
            "avg_opportunity_cost_r": avg_opp_cost,
            "avg_monthly_r": avg_monthly_r,
            "median_monthly_r": statistics.median(monthly_rs) if monthly_rs else 0.0,
            "monthly_std": statistics.stdev(monthly_rs) if len(monthly_rs) > 1 else 0.0,
        }

    return results


# ---------------------------------------------------------------------------
# 4. Trade Cap Optimizer
# ---------------------------------------------------------------------------

def optimize_trade_cap(win_rate: float = 0.60, avg_win_r: float = 1.8,
                       avg_loss_r: float = -1.0, n_sessions: int = 10000,
                       seed: int = 300) -> Dict[int, Dict]:
    """Test different trade caps per session.

    Caps tested: 2, 3, 4, 5 trades per session.
    Measures marginal value of each additional trade and quality degradation.
    """
    caps = [2, 3, 4, 5]
    results = {}

    for cap in caps:
        rng = random.Random(seed)
        session_rs = []
        trade_r_by_position = {i: [] for i in range(cap)}
        total_trades = 0

        for s in range(n_sessions):
            session_r = 0.0
            consec_losses = 0
            trade_losses = 0
            cooldown_active = False
            trade_idx = 0

            for t_num in range(cap):
                if session_r <= -SESSION_LOCK_R:
                    break

                # Quality degradation model: later trades in session are
                # slightly lower quality due to fatigue/overtrading
                quality_decay = 1.0 - 0.03 * t_num  # 3% quality decay per trade
                adjusted_wr = win_rate * quality_decay

                if cooldown_active:
                    risk_pct = RISK_PCT_COOLDOWN
                    if rng.random() < 0.4:
                        continue
                elif trade_losses >= 1:
                    risk_pct = RISK_PCT_AFTER_1_LOSS
                else:
                    risk_pct = RISK_PCT_STANDARD

                r_mult, is_win = _generate_trade(rng, adjusted_wr, avg_win_r, avg_loss_r)
                effective_r = r_mult * (risk_pct / RISK_PCT_STANDARD)
                session_r += effective_r

                if trade_idx < cap:
                    trade_r_by_position[trade_idx].append(effective_r)
                trade_idx += 1
                total_trades += 1

                if is_win:
                    consec_losses = 0
                    if cooldown_active:
                        cooldown_active = False
                else:
                    consec_losses += 1
                    trade_losses += 1
                    if consec_losses >= COOLDOWN_CONSEC_LOSSES:
                        cooldown_active = True

            session_rs.append(session_r)

        n_months = n_sessions // SESSIONS_PER_MONTH
        monthly_rs = []
        for m in range(n_months):
            mr = sum(session_rs[m * SESSIONS_PER_MONTH:(m + 1) * SESSIONS_PER_MONTH])
            monthly_rs.append(mr)

        marginal_values = {}
        for pos in range(cap):
            vals = trade_r_by_position[pos]
            if vals:
                marginal_values[f"trade_{pos + 1}_avg_r"] = statistics.mean(vals)
                marginal_values[f"trade_{pos + 1}_win_rate"] = sum(1 for v in vals if v > 0) / len(vals) * 100

        results[cap] = {
            "avg_monthly_r": statistics.mean(monthly_rs) if monthly_rs else 0.0,
            "median_monthly_r": statistics.median(monthly_rs) if monthly_rs else 0.0,
            "monthly_std": statistics.stdev(monthly_rs) if len(monthly_rs) > 1 else 0.0,
            "total_trades": total_trades,
            "marginal_values": marginal_values,
        }

    return results


# ---------------------------------------------------------------------------
# 5. Cooldown Analysis
# ---------------------------------------------------------------------------

def analyze_cooldown(win_rate: float = 0.60, avg_win_r: float = 1.8,
                     avg_loss_r: float = -1.0, n_sessions: int = 10000,
                     seed: int = 400) -> Dict:
    """Analyze cooldown trigger frequency and effectiveness.

    Tests:
    - Current: cooldown after 2 consecutive losses
    - Alternative: cooldown after 3 consecutive losses
    - Cooldown duration: until win vs entire remaining session
    """
    configs = {
        "current_2loss_until_win": {"consec_trigger": 2, "until_win": True, "block_remaining": False},
        "3loss_until_win": {"consec_trigger": 3, "until_win": True, "block_remaining": False},
        "2loss_block_session": {"consec_trigger": 2, "until_win": False, "block_remaining": True},
        "3loss_block_session": {"consec_trigger": 3, "until_win": False, "block_remaining": True},
    }

    results = {}

    for config_name, cfg in configs.items():
        rng = random.Random(seed)
        cooldown_triggers = 0
        cooldown_trade_wins = 0
        cooldown_trade_losses = 0
        cooldown_trade_total = 0
        session_rs = []

        for s in range(n_sessions):
            session_r = 0.0
            consec_losses = 0
            trade_losses = 0
            cooldown_active = False

            for t_num in range(MAX_TRADES_SESSION):
                if session_r <= -SESSION_LOCK_R:
                    break

                if cooldown_active:
                    if cfg["block_remaining"]:
                        break  # No more trades this session
                    risk_pct = RISK_PCT_COOLDOWN
                    if rng.random() < 0.4:
                        continue
                elif trade_losses >= 1:
                    risk_pct = RISK_PCT_AFTER_1_LOSS
                else:
                    risk_pct = RISK_PCT_STANDARD

                r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)
                effective_r = r_mult * (risk_pct / RISK_PCT_STANDARD)
                session_r += effective_r

                if cooldown_active:
                    cooldown_trade_total += 1
                    if is_win:
                        cooldown_trade_wins += 1
                    else:
                        cooldown_trade_losses += 1

                if is_win:
                    consec_losses = 0
                    if cooldown_active and cfg["until_win"]:
                        cooldown_active = False
                else:
                    consec_losses += 1
                    trade_losses += 1
                    if consec_losses >= cfg["consec_trigger"] and not cooldown_active:
                        cooldown_active = True
                        cooldown_triggers += 1

            session_rs.append(session_r)

        n_months = n_sessions // SESSIONS_PER_MONTH
        monthly_rs = []
        for m in range(n_months):
            mr = sum(session_rs[m * SESSIONS_PER_MONTH:(m + 1) * SESSIONS_PER_MONTH])
            monthly_rs.append(mr)

        cd_wr = (cooldown_trade_wins / cooldown_trade_total * 100.0
                 if cooldown_trade_total > 0 else 0.0)

        results[config_name] = {
            "trigger_rate_pct": cooldown_triggers / n_sessions * 100.0,
            "cooldown_trade_win_rate": cd_wr,
            "cooldown_trades_total": cooldown_trade_total,
            "avg_monthly_r": statistics.mean(monthly_rs) if monthly_rs else 0.0,
            "median_monthly_r": statistics.median(monthly_rs) if monthly_rs else 0.0,
            "monthly_std": statistics.stdev(monthly_rs) if len(monthly_rs) > 1 else 0.0,
        }

    return results


# ---------------------------------------------------------------------------
# 6. Drawdown Recovery Analysis
# ---------------------------------------------------------------------------

def analyze_recovery(win_rate: float = 0.60, avg_win_r: float = 1.8,
                     avg_loss_r: float = -1.0, seed: int = 500) -> Dict:
    """Analyze recovery from various drawdown levels.

    For drawdowns of 2R, 4R, 6R, 8R, 10R:
    - How many sessions to recover under different sizing rules?
    - Compare standard vs aggressive vs conservative recovery.
    """
    drawdown_levels = [2.0, 4.0, 6.0, 8.0, 10.0]
    sizing_modes = {
        "standard": lambda dd_r: RISK_PCT_STANDARD,
        "conservative": lambda dd_r: max(0.5, RISK_PCT_STANDARD * (1.0 - 0.05 * dd_r)),
        "aggressive_recovery": lambda dd_r: min(1.5, RISK_PCT_STANDARD * (1.0 + 0.08 * dd_r)),
    }

    results = {}

    for dd_level in drawdown_levels:
        dd_results = {}
        for mode_name, size_fn in sizing_modes.items():
            rng = random.Random(seed)
            recovery_sessions = []

            for trial in range(1000):
                equity = -dd_level
                sessions = 0
                max_sessions = 500

                while equity < 0 and sessions < max_sessions:
                    session_r = 0.0
                    consec_losses = 0
                    trade_losses = 0
                    cooldown_active = False
                    current_dd = abs(equity)  # how deep in drawdown

                    for t_num in range(MAX_TRADES_SESSION):
                        if session_r <= -SESSION_LOCK_R:
                            break

                        base_risk = size_fn(current_dd)
                        if cooldown_active:
                            risk_pct = min(base_risk, RISK_PCT_COOLDOWN)
                            if rng.random() < 0.4:
                                continue
                        elif trade_losses >= 1:
                            risk_pct = min(base_risk, RISK_PCT_AFTER_1_LOSS)
                        else:
                            risk_pct = base_risk

                        r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)
                        effective_r = r_mult * (risk_pct / RISK_PCT_STANDARD)
                        session_r += effective_r

                        if is_win:
                            consec_losses = 0
                            if cooldown_active:
                                cooldown_active = False
                        else:
                            consec_losses += 1
                            trade_losses += 1
                            if consec_losses >= COOLDOWN_CONSEC_LOSSES:
                                cooldown_active = True

                    equity += session_r
                    sessions += 1

                recovery_sessions.append(sessions)

            avg_sessions = statistics.mean(recovery_sessions)
            median_sessions = statistics.median(recovery_sessions)
            p90_sessions = sorted(recovery_sessions)[int(len(recovery_sessions) * 0.9)]
            failed_recovery = sum(1 for s in recovery_sessions if s >= 500) / len(recovery_sessions) * 100

            dd_results[mode_name] = {
                "avg_sessions": avg_sessions,
                "median_sessions": median_sessions,
                "p90_sessions": p90_sessions,
                "failed_recovery_pct": failed_recovery,
            }

        results[dd_level] = dd_results

    return results


# ---------------------------------------------------------------------------
# 7. MEG Sensitivity Analysis
# ---------------------------------------------------------------------------

def analyze_meg(win_rate: float = 0.60, avg_win_r: float = 1.8,
                avg_loss_r: float = -1.0, n_trades: int = 2000,
                seed: int = 600) -> Dict:
    """Test MEG window sizes and lock thresholds.

    Window sizes: 30, 40, 50, 60, 80, 100
    Lock thresholds: -0.05, -0.10, -0.15, -0.20, -0.25
    Measures detection speed and trades saved.
    """
    windows = [30, 40, 50, 60, 80, 100]
    thresholds = [-0.05, -0.10, -0.15, -0.20, -0.25]

    # Generate a trade sequence with an embedded edge degradation period
    rng = random.Random(seed)
    trade_sequence = []

    # Phase 1: good edge (60% of trades)
    good_phase = int(n_trades * 0.6)
    for _ in range(good_phase):
        r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)
        trade_sequence.append(r_mult)

    # Phase 2: degraded edge (20% of trades at lower win rate)
    degraded_phase = int(n_trades * 0.2)
    degraded_wr = win_rate - 0.15
    for _ in range(degraded_phase):
        r_mult, is_win = _generate_trade(rng, degraded_wr, avg_win_r, avg_loss_r)
        trade_sequence.append(r_mult)

    # Phase 3: recovered edge (20% of trades)
    for _ in range(n_trades - good_phase - degraded_phase):
        r_mult, is_win = _generate_trade(rng, win_rate, avg_win_r, avg_loss_r)
        trade_sequence.append(r_mult)

    degradation_start = good_phase
    degradation_end = good_phase + degraded_phase

    results = {"windows": {}, "thresholds": {}, "bootstrap": {}}

    # Test window sizes (with default threshold -0.15)
    for window in windows:
        locks = []
        detection_delay = None
        trades_saved = 0
        locked = False

        for i in range(window, len(trade_sequence)):
            w = trade_sequence[i - window:i]
            wins = [r for r in w if r > 0]
            losses = [r for r in w if r <= 0]
            wr = len(wins) / len(w)
            avg_w = statistics.mean(wins) if wins else 0
            avg_l = abs(statistics.mean(losses)) if losses else 0
            exp_m = (wr * avg_w) - ((1 - wr) * avg_l)

            if exp_m <= MEG_LOCK_THRESHOLD:
                if not locked:
                    locked = True
                    locks.append(i)
                    if degradation_start <= i <= degradation_end and detection_delay is None:
                        detection_delay = i - degradation_start
                trades_saved += 1
            else:
                if locked and exp_m > 0:
                    locked = False

        # Trades taken during degradation without MEG
        degraded_trades_no_meg = degradation_end - degradation_start
        degraded_trades_with_meg = degraded_trades_no_meg - trades_saved

        results["windows"][window] = {
            "lock_events": len(locks),
            "detection_delay_trades": detection_delay if detection_delay is not None else -1,
            "trades_saved_during_degradation": trades_saved,
            "total_trades_blocked": trades_saved,
        }

    # Test thresholds (with default window 60)
    for threshold in thresholds:
        locks = []
        trades_saved = 0
        false_locks = 0
        locked = False

        for i in range(MEG_WINDOW, len(trade_sequence)):
            w = trade_sequence[i - MEG_WINDOW:i]
            wins = [r for r in w if r > 0]
            losses = [r for r in w if r <= 0]
            wr = len(wins) / len(w)
            avg_w = statistics.mean(wins) if wins else 0
            avg_l = abs(statistics.mean(losses)) if losses else 0
            exp_m = (wr * avg_w) - ((1 - wr) * avg_l)

            if exp_m <= threshold:
                if not locked:
                    locked = True
                    locks.append(i)
                    # False lock = locking outside degradation period
                    if i < degradation_start or i > degradation_end:
                        false_locks += 1
                trades_saved += 1
            else:
                if locked and exp_m > 0:
                    locked = False

        results["thresholds"][threshold] = {
            "lock_events": len(locks),
            "false_lock_events": false_locks,
            "total_trades_blocked": trades_saved,
        }

    # Bootstrap tier analysis
    bootstrap_tiers = {
        "BOOTSTRAP_0 (<20 trades)": {"min": 0, "max": 19, "rule": "Secondary only"},
        "BOOTSTRAP_1 (20-59 trades)": {"min": 20, "max": 59, "rule": "Secondary unless Exp_M >= +0.01"},
        "FULL (>=60 trades)": {"min": 60, "max": None, "rule": "Full MEG enforcement"},
    }

    # Simulate bootstrap progression
    rng2 = random.Random(seed + 100)
    bootstrap_equity = []
    eq = 0.0
    for i in range(100):
        r_mult, _ = _generate_trade(rng2, win_rate, avg_win_r, avg_loss_r)
        eq += r_mult
        tier = "BOOTSTRAP_0" if i < 20 else ("BOOTSTRAP_1" if i < 60 else "FULL")
        bootstrap_equity.append({"trade": i + 1, "tier": tier, "equity_r": eq})

    results["bootstrap"] = {
        "tiers": bootstrap_tiers,
        "sample_progression": bootstrap_equity[:20] + bootstrap_equity[55:65],
    }

    return results


# ---------------------------------------------------------------------------
# 8. Comprehensive Report
# ---------------------------------------------------------------------------

def print_risk_report():
    """Print comprehensive risk management optimization report."""

    print("=" * 80)
    print("  SATVA v15 RISK MANAGEMENT OPTIMIZER -- COMPREHENSIVE REPORT")
    print("=" * 80)

    # ---- Current Risk Profile ----
    print("\n" + "=" * 80)
    print("  SECTION 1: CURRENT RISK PROFILE SUMMARY")
    print("=" * 80)
    print(f"""
  Position Sizing:
    Standard risk per trade:     {RISK_PCT_STANDARD}%
    After 1 loss:                {RISK_PCT_AFTER_1_LOSS}%
    During cooldown:             {RISK_PCT_COOLDOWN}%

  Session Controls:
    Session loss lock:           {SESSION_LOCK_R}R
    Drawdown guard:              {DRAWDOWN_GUARD_R}R
    Max trades/session:          {MAX_TRADES_SESSION}
    Max portfolio heat:          {MAX_PORTFOLIO_HEAT}%

  Cooldown:
    Trigger:                     {COOLDOWN_CONSEC_LOSSES} consecutive losses
    Mode:                        Secondary only, 0.5% risk, elevated gates
    Exit:                        First winning trade or session end

  MEG (Meta Expectancy Governor):
    Window:                      {MEG_WINDOW} trades (rolling)
    Lock threshold:              Exp_M <= {MEG_LOCK_THRESHOLD}
    Bootstrap:                   <20=BOOTSTRAP_0, 20-59=BOOTSTRAP_1, >=60=FULL
""")

    # ---- Monte Carlo Results ----
    print("=" * 80)
    print("  SECTION 2: MONTE CARLO SESSION SIMULATION")
    print("=" * 80)
    print()

    win_rates = [0.50, 0.55, 0.60, 0.65, 0.70]
    mc_results = {}

    for wr in win_rates:
        mc = monte_carlo_session(wr, seed=42 + int(wr * 100))
        mc_results[wr] = mc

    print(f"  {'Win Rate':>10} | {'E[Monthly R]':>13} | {'Median Mo R':>12} | "
          f"{'Std Dev':>8} | {'P10':>7} | {'P90':>7} | {'Ruin Prob':>10}")
    print("  " + "-" * 78)

    for wr in win_rates:
        mc = mc_results[wr]
        print(f"  {wr*100:>9.0f}% | {mc.expected_monthly_r:>+13.2f} | "
              f"{mc.median_monthly_r:>+12.2f} | {mc.monthly_r_std:>8.2f} | "
              f"{mc.p10_monthly_r:>+7.2f} | {mc.p90_monthly_r:>+7.2f} | "
              f"{mc.ruin_probability:>9.1%}")

    print()
    print("  Max Drawdown Distribution (monthly):")
    print(f"  {'Win Rate':>10} | {'Avg MaxDD':>10} | {'Median MaxDD':>13} | {'P90 MaxDD':>10}")
    print("  " + "-" * 50)
    for wr in win_rates:
        mc = mc_results[wr]
        if mc.max_drawdowns:
            avg_dd = statistics.mean(mc.max_drawdowns)
            med_dd = statistics.median(mc.max_drawdowns)
            p90_dd = sorted(mc.max_drawdowns)[int(len(mc.max_drawdowns) * 0.9)]
        else:
            avg_dd = med_dd = p90_dd = 0.0
        print(f"  {wr*100:>9.0f}% | {avg_dd:>10.2f}R | {med_dd:>12.2f}R | {p90_dd:>9.2f}R")

    # ---- Position Sizing ----
    print()
    print("=" * 80)
    print("  SECTION 3: POSITION SIZING OPTIMIZATION")
    print("=" * 80)
    print()

    sizing_results = optimize_position_sizing()

    print(f"  {'Strategy':<22} | {'Params':<32} | {'CAGR%':>7} | {'MaxDD%':>7} | "
          f"{'Sharpe':>7} | {'Calmar':>7}")
    print("  " + "-" * 90)

    for sr in sizing_results:
        print(f"  {sr.name:<22} | {sr.params:<32} | {sr.cagr_pct:>7.1f} | "
              f"{sr.max_drawdown_pct:>7.1f} | {sr.sharpe_ratio:>7.2f} | {sr.calmar_ratio:>7.2f}")

    # Find best by Calmar (risk-adjusted) -- exclude strategies with MaxDD > 30%
    # as they are impractical for intraday systems
    practical = [s for s in sizing_results if s.max_drawdown_pct <= 30.0] or sizing_results
    best_calmar = max(practical, key=lambda x: x.calmar_ratio)
    best_sharpe = max(practical, key=lambda x: x.sharpe_ratio)
    print(f"\n  >> Best Calmar ratio: {best_calmar.name} ({best_calmar.params}) = {best_calmar.calmar_ratio:.2f}")
    print(f"  >> Best Sharpe ratio: {best_sharpe.name} ({best_sharpe.params}) = {best_sharpe.sharpe_ratio:.2f}")

    # ---- Session Loss Cap ----
    print()
    print("=" * 80)
    print("  SECTION 4: SESSION LOSS CAP OPTIMIZATION")
    print("=" * 80)
    print()

    loss_cap_results = optimize_loss_cap()

    print(f"  {'Cap':>6} | {'Trigger%':>9} | {'Opp Cost R':>11} | "
          f"{'Avg Mo R':>9} | {'Med Mo R':>9} | {'Std':>7}")
    print("  " + "-" * 60)
    for cap in sorted(loss_cap_results.keys()):
        r = loss_cap_results[cap]
        marker = " <-- current" if cap == 2.0 else ""
        print(f"  {cap:>5.2f}R | {r['trigger_rate_pct']:>8.1f}% | "
              f"{r['avg_opportunity_cost_r']:>+10.2f}R | "
              f"{r['avg_monthly_r']:>+8.2f}R | "
              f"{r['median_monthly_r']:>+8.2f}R | "
              f"{r['monthly_std']:>7.2f}{marker}")

    # ---- Trade Cap ----
    print()
    print("=" * 80)
    print("  SECTION 5: TRADE CAP OPTIMIZATION")
    print("=" * 80)
    print()

    trade_cap_results = optimize_trade_cap()

    print(f"  {'Cap':>4} | {'Avg Mo R':>9} | {'Med Mo R':>9} | {'Std':>7} | {'Total Trades':>13}")
    print("  " + "-" * 52)
    for cap in sorted(trade_cap_results.keys()):
        r = trade_cap_results[cap]
        marker = " <-- current" if cap == 3 else ""
        print(f"  {cap:>4} | {r['avg_monthly_r']:>+8.2f}R | "
              f"{r['median_monthly_r']:>+8.2f}R | "
              f"{r['monthly_std']:>7.2f} | {r['total_trades']:>13}{marker}")

    print("\n  Marginal Value by Trade Position:")
    for cap in sorted(trade_cap_results.keys()):
        r = trade_cap_results[cap]
        mv = r["marginal_values"]
        parts = []
        for pos in range(cap):
            key_r = f"trade_{pos + 1}_avg_r"
            key_wr = f"trade_{pos + 1}_win_rate"
            if key_r in mv:
                parts.append(f"T{pos + 1}: {mv[key_r]:+.3f}R ({mv[key_wr]:.0f}%)")
        print(f"    Cap={cap}: {' | '.join(parts)}")

    # ---- Cooldown Analysis ----
    print()
    print("=" * 80)
    print("  SECTION 6: COOLDOWN ANALYSIS")
    print("=" * 80)
    print()

    cooldown_results = analyze_cooldown()

    print(f"  {'Config':<30} | {'Trigger%':>9} | {'CD WinRate':>10} | "
          f"{'Avg Mo R':>9} | {'Med Mo R':>9} | {'Std':>7}")
    print("  " + "-" * 82)
    for cfg_name, r in cooldown_results.items():
        marker = " *" if cfg_name == "current_2loss_until_win" else ""
        print(f"  {cfg_name:<30} | {r['trigger_rate_pct']:>8.1f}% | "
              f"{r['cooldown_trade_win_rate']:>9.1f}% | "
              f"{r['avg_monthly_r']:>+8.2f}R | "
              f"{r['median_monthly_r']:>+8.2f}R | "
              f"{r['monthly_std']:>7.2f}{marker}")

    print("\n  (* = current SATVA v15 configuration)")

    # ---- Drawdown Recovery ----
    print()
    print("=" * 80)
    print("  SECTION 7: DRAWDOWN RECOVERY ANALYSIS")
    print("=" * 80)
    print()

    recovery_results = analyze_recovery()

    print(f"  {'Drawdown':>10} | {'Mode':<22} | {'Avg Sess':>9} | "
          f"{'Med Sess':>9} | {'P90 Sess':>9} | {'Fail%':>6}")
    print("  " + "-" * 75)
    for dd_level in sorted(recovery_results.keys()):
        for mode_name, r in recovery_results[dd_level].items():
            print(f"  {dd_level:>9.1f}R | {mode_name:<22} | "
                  f"{r['avg_sessions']:>9.1f} | {r['median_sessions']:>9.1f} | "
                  f"{r['p90_sessions']:>9} | {r['failed_recovery_pct']:>5.1f}%")
        print("  " + "-" * 75)

    # ---- MEG Analysis ----
    print()
    print("=" * 80)
    print("  SECTION 8: MEG SENSITIVITY ANALYSIS")
    print("=" * 80)
    print()

    meg_results = analyze_meg()

    print("  Window Size Analysis (threshold = -0.15):")
    print(f"  {'Window':>8} | {'Lock Events':>12} | {'Detection Delay':>16} | {'Trades Blocked':>15}")
    print("  " + "-" * 58)
    for window in sorted(meg_results["windows"].keys()):
        r = meg_results["windows"][window]
        delay = f"{r['detection_delay_trades']} trades" if r['detection_delay_trades'] >= 0 else "N/A"
        marker = " <-- current" if window == 60 else ""
        print(f"  {window:>8} | {r['lock_events']:>12} | {delay:>16} | "
              f"{r['total_trades_blocked']:>15}{marker}")

    print()
    print("  Lock Threshold Analysis (window = 60):")
    print(f"  {'Threshold':>10} | {'Lock Events':>12} | {'False Locks':>12} | {'Trades Blocked':>15}")
    print("  " + "-" * 56)
    for threshold in sorted(meg_results["thresholds"].keys()):
        r = meg_results["thresholds"][threshold]
        marker = " <-- current" if threshold == -0.15 else ""
        print(f"  {threshold:>+10.2f} | {r['lock_events']:>12} | "
              f"{r['false_lock_events']:>12} | {r['total_trades_blocked']:>15}{marker}")

    print()
    print("  Bootstrap Tier Summary:")
    for tier_name, info in meg_results["bootstrap"]["tiers"].items():
        print(f"    {tier_name}: {info['rule']}")

    # ---- Recommendations ----
    print()
    print("=" * 80)
    print("  SECTION 9: RECOMMENDED v15.1 RISK CHANGES")
    print("=" * 80)

    # Determine recommendations from data
    # Best loss cap
    best_loss_cap = max(loss_cap_results.items(),
                        key=lambda x: x[1]["avg_monthly_r"])
    # Best trade cap
    best_trade_cap = max(trade_cap_results.items(),
                         key=lambda x: x[1]["avg_monthly_r"])
    # Best cooldown
    best_cooldown = max(cooldown_results.items(),
                        key=lambda x: x[1]["avg_monthly_r"])
    # Best MEG window
    best_meg_window = max(meg_results["windows"].items(),
                          key=lambda x: x[1]["total_trades_blocked"])
    # Best MEG threshold (maximize true locks, minimize false)
    best_meg_threshold = min(
        meg_results["thresholds"].items(),
        key=lambda x: x[1]["false_lock_events"] - x[1]["total_trades_blocked"]
    )

    # Monte Carlo assessment
    mc_60 = mc_results[0.60]

    print(f"""
  1. POSITION SIZING:
     Current: 1.0% / 0.75% / 0.5% (standard / after-loss / cooldown)
     Best risk-adjusted strategy: {best_calmar.name} ({best_calmar.params})
       - Calmar ratio: {best_calmar.calmar_ratio:.2f}
       - CAGR: {best_calmar.cagr_pct:.1f}%, MaxDD: {best_calmar.max_drawdown_pct:.1f}%
     Recommendation: Consider {best_calmar.name} for improved risk-adjusted returns.

  2. SESSION LOSS CAP:
     Current: 2.0R
     Optimal by avg monthly R: {best_loss_cap[0]:.2f}R
       - Trigger rate: {best_loss_cap[1]['trigger_rate_pct']:.1f}%
       - Avg monthly R: {best_loss_cap[1]['avg_monthly_r']:+.2f}
     Recommendation: {"Keep at 2.0R (optimal balance)." if best_loss_cap[0] == 2.0 else f"Consider adjusting to {best_loss_cap[0]:.2f}R."}

  3. TRADE CAP:
     Current: 3 trades/session
     Optimal by avg monthly R: {best_trade_cap[0]} trades/session
       - Avg monthly R: {best_trade_cap[1]['avg_monthly_r']:+.2f}
     Recommendation: {"Keep at 3 trades/session." if best_trade_cap[0] == 3 else f"Consider {best_trade_cap[0]} trades/session."}

  4. COOLDOWN CONFIGURATION:
     Current: 2 consecutive losses, until first win
     Best by monthly R: {best_cooldown[0]}
       - Avg monthly R: {best_cooldown[1]['avg_monthly_r']:+.2f}
     Recommendation: Evaluate {best_cooldown[0]} for improved risk control.

  5. MEG TUNING:
     Current: window=60, threshold=-0.15
     Best detection window: {best_meg_window[0]} trades
       - Trades blocked: {best_meg_window[1]['total_trades_blocked']}
     Best threshold: {best_meg_threshold[0]:.2f}
       - False locks: {best_meg_threshold[1]['false_lock_events']}
     Recommendation: {"Keep current MEG settings." if best_meg_window[0] == 60 and best_meg_threshold[0] == -0.15 else f"Consider window={best_meg_window[0]}, threshold={best_meg_threshold[0]:.2f}."}

  6. RUIN ASSESSMENT (at 60% win rate):
     Ruin probability (1-year, 20R threshold): {mc_60.ruin_probability:.1%}
     Expected monthly R: {mc_60.expected_monthly_r:+.2f}
     P10-P90 range: [{mc_60.p10_monthly_r:+.2f}, {mc_60.p90_monthly_r:+.2f}]
     Assessment: {"LOW RISK - System is well-protected." if mc_60.ruin_probability < 0.05 else "MODERATE RISK - Consider tighter controls." if mc_60.ruin_probability < 0.15 else "HIGH RISK - Immediate risk reduction needed."}

  7. RECOVERY PROFILE:
     At 60% WR, recovery from 4R drawdown:""")

    if 4.0 in recovery_results:
        std_rec = recovery_results[4.0]["standard"]
        print(f"       Standard sizing: {std_rec['avg_sessions']:.1f} sessions avg "
              f"({std_rec['median_sessions']:.0f} median)")

    print()
    print("=" * 80)
    print("  END OF REPORT")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print_risk_report()
