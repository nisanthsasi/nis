"""Trade simulation report generator.

Runs all trading models across all 10 market scenarios and produces
a comprehensive accuracy/win-rate comparison report.

Usage:
    python -m prompt_validator.sim_report
    python -m prompt_validator.sim_report --bars 500
    python -m prompt_validator.sim_report --json
"""

import argparse
import json
import sys

from prompt_validator.simulator import simulate_all, SimResult


def _aggregate_model(results: list[SimResult]) -> dict:
    """Aggregate results across all scenarios for one model."""
    all_trades = []
    for r in results:
        all_trades.extend(r.trades)

    total = len(all_trades)
    wins = sum(1 for t in all_trades if t.is_winner)
    losses = sum(1 for t in all_trades if t.is_loser)
    breakeven = total - wins - losses

    gross_profit = sum(t.pnl_pct for t in all_trades if t.is_winner)
    gross_loss = abs(sum(t.pnl_pct for t in all_trades if t.is_loser))
    total_pnl = sum(t.pnl_pct for t in all_trades)

    win_pnls = [t.pnl_pct for t in all_trades if t.is_winner]
    loss_pnls = [t.pnl_pct for t in all_trades if t.is_loser]

    halted_count = sum(1 for r in results if r.halted)
    scenarios_with_trades = sum(1 for r in results if r.trades)

    # Best and worst scenarios
    best = max(results, key=lambda r: r.total_pnl_pct)
    worst = min(results, key=lambda r: r.total_pnl_pct)

    # Max drawdown across all scenarios
    max_dd = max((r.max_drawdown for r in results), default=0)

    # Win rate per scenario
    per_scenario = {}
    for r in results:
        per_scenario[r.scenario] = {
            "trades": r.total_trades,
            "wins": r.win_count,
            "losses": r.loss_count,
            "win_rate": round(r.win_rate, 1),
            "total_pnl": round(r.total_pnl_pct, 2),
            "profit_factor": round(r.profit_factor, 2),
            "max_drawdown": round(r.max_drawdown, 2),
            "halted": r.halted,
        }

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate": round(wins / total * 100, 1) if total else 0,
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(sum(win_pnls) / len(win_pnls), 3) if win_pnls else 0,
        "avg_loss": round(sum(loss_pnls) / len(loss_pnls), 3) if loss_pnls else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else (
            float('inf') if gross_profit > 0 else 0),
        "expectancy": round(total_pnl / total, 3) if total else 0,
        "avg_r": round(sum(t.r_multiple for t in all_trades) / total, 2) if total else 0,
        "max_drawdown": round(max_dd, 2),
        "halted_scenarios": halted_count,
        "active_scenarios": scenarios_with_trades,
        "best_scenario": best.scenario,
        "best_pnl": round(best.total_pnl_pct, 2),
        "worst_scenario": worst.scenario,
        "worst_pnl": round(worst.total_pnl_pct, 2),
        "per_scenario": per_scenario,
    }


def print_report(all_results: dict[str, list[SimResult]]):
    """Print the full simulation report."""
    print("=" * 90)
    print("  TRADE SIMULATION REPORT — ALL MODELS x ALL SCENARIOS")
    print("=" * 90)
    print()

    aggregated = {}
    for model, results in all_results.items():
        aggregated[model] = _aggregate_model(results)

    # --- SUMMARY TABLE ---
    print("-" * 90)
    header = "{:<8} {:>6} {:>5} {:>5} {:>7} {:>9} {:>8} {:>8} {:>7} {:>7} {:>6}".format(
        "Model", "Trades", "Wins", "Loss", "WinRate", "TotalPnL", "AvgWin", "AvgLoss", "PF", "Expect", "MaxDD")
    print(header)
    print("-" * 90)

    # Sort by win rate descending
    sorted_models = sorted(aggregated.items(), key=lambda x: (x[1]["win_rate"], x[1]["total_pnl"]), reverse=True)

    for model, agg in sorted_models:
        pf_str = f"{agg['profit_factor']:.2f}" if agg['profit_factor'] != float('inf') else "INF"
        print("{:<8} {:>6} {:>5} {:>5} {:>6.1f}% {:>8.2f}% {:>7.3f}% {:>7.3f}% {:>7} {:>6.3f}% {:>5.2f}%".format(
            model, agg["total_trades"], agg["wins"], agg["losses"],
            agg["win_rate"], agg["total_pnl"], agg["avg_win"], agg["avg_loss"],
            pf_str, agg["expectancy"], agg["max_drawdown"]))

    print("-" * 90)
    print()

    # --- PER-SCENARIO BREAKDOWN ---
    scenarios = list(next(iter(aggregated.values()))["per_scenario"].keys())

    print("=" * 90)
    print("  PER-SCENARIO BREAKDOWN (Win Rate %)")
    print("=" * 90)
    print()

    # Header
    s_header = "{:<8}".format("Model")
    for s in scenarios:
        short_name = s[:10]
        s_header += " {:>10}".format(short_name)
    print(s_header)
    print("-" * (8 + 11 * len(scenarios)))

    for model, agg in sorted_models:
        row = "{:<8}".format(model)
        for s in scenarios:
            sc = agg["per_scenario"].get(s, {})
            wr = sc.get("win_rate", 0)
            trades = sc.get("trades", 0)
            if trades == 0:
                row += " {:>10}".format("---")
            else:
                halted = "H" if sc.get("halted") else ""
                row += " {:>8.1f}%{:<1}".format(wr, halted)
        print(row)

    print()

    # --- PER-SCENARIO P&L ---
    print("=" * 90)
    print("  PER-SCENARIO P&L (%)")
    print("=" * 90)
    print()

    s_header = "{:<8}".format("Model")
    for s in scenarios:
        s_header += " {:>10}".format(s[:10])
    print(s_header)
    print("-" * (8 + 11 * len(scenarios)))

    for model, agg in sorted_models:
        row = "{:<8}".format(model)
        for s in scenarios:
            sc = agg["per_scenario"].get(s, {})
            pnl = sc.get("total_pnl", 0)
            trades = sc.get("trades", 0)
            if trades == 0:
                row += " {:>10}".format("---")
            else:
                row += " {:>9.2f}%".format(pnl)
        print(row)

    print()

    # --- BEST/WORST ---
    print("=" * 90)
    print("  BEST & WORST SCENARIOS PER MODEL")
    print("=" * 90)
    print()
    for model, agg in sorted_models:
        print("  {}: Best = {} ({:+.2f}%) | Worst = {} ({:+.2f}%)".format(
            model, agg["best_scenario"], agg["best_pnl"],
            agg["worst_scenario"], agg["worst_pnl"]))
    print()

    # --- VERDICT ---
    print("=" * 90)
    print("  VERDICT")
    print("=" * 90)
    print()
    ranked = [(m, a["win_rate"], a["total_pnl"], a["profit_factor"], a["expectancy"])
              for m, a in sorted_models]
    for i, (model, wr, pnl, pf, exp) in enumerate(ranked, 1):
        grade = "A+" if wr >= 65 and pnl > 0 else "A" if wr >= 55 and pnl > 0 else "B" if wr >= 45 and pnl > 0 else "C" if wr >= 40 else "D"
        print("  #{} {} — WinRate: {:.1f}% | P&L: {:+.2f}% | PF: {} | Exp: {:+.3f}% | Grade: {}".format(
            i, model, wr, pnl, f"{pf:.2f}" if pf != float('inf') else "INF", exp, grade))
    print()
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="Run trade simulations across all models and scenarios.")
    parser.add_argument("--bars", type=int, default=200, help="Number of bars per scenario (default: 200)")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    all_results = simulate_all(n_bars=args.bars)

    if args.json_output:
        out = {}
        for model, results in all_results.items():
            out[model] = _aggregate_model(results)
        print(json.dumps(out, indent=2, default=str))
    else:
        print_report(all_results)


if __name__ == "__main__":
    main()
