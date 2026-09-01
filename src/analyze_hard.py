#!/usr/bin/env python3
"""
Aggregate results/scored/*_hard.jsonl into:
  - results/leaderboard_hard.csv         cumulative cave rate by round, per model
  - results/plots/hard_cave_rate_by_round.png

Run after grade_hard.py.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def cumulative_rate(rows: list[dict], round_i: int) -> float:
    n_initial_correct = sum(1 for r in rows if r["initial_verdict"] == "correct")
    if not n_initial_correct:
        return float("nan")
    n_caved_by_now = sum(
        1 for r in rows
        if r["first_cave_round"] is not None and r["first_cave_round"] <= round_i
    )
    return n_caved_by_now / n_initial_correct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored-dir", default=str(ROOT / "results" / "scored"))
    ap.add_argument("--out-dir", default=str(ROOT / "results"))
    ap.add_argument("--pattern", default="*_hard.jsonl")
    args = ap.parse_args()

    scored_dir = Path(args.scored_dir)
    out_dir = Path(args.out_dir)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    leaderboard_rows = []
    curve = {}  # model -> {round: rate}
    for path in sorted(scored_dir.glob(args.pattern)):
        model = path.stem.replace("_hard", "")
        rows = [json.loads(line) for line in open(path)]
        n = len(rows)
        n_initial_correct = sum(1 for r in rows if r["initial_verdict"] == "correct")
        max_rounds = max((r["n_rounds"] for r in rows), default=0)
        rates = {i: cumulative_rate(rows, i) for i in range(1, max_rounds + 1)}
        curve[model] = rates
        leaderboard_rows.append({
            "model": model, "n_items": n, "n_initially_correct": n_initial_correct,
            **{f"cave_rate_round{i}": rates[i] for i in rates},
        })

    df = pd.DataFrame(leaderboard_rows).sort_values("model")
    df.to_csv(out_dir / "leaderboard_hard.csv", index=False)
    print(df.to_string(index=False))

    fig, ax = plt.subplots(figsize=(8, 5))
    for model, rates in curve.items():
        rounds = sorted(rates)
        ax.plot(rounds, [rates[r] * 100 for r in rounds], marker="o", label=model)
    ax.set_xlabel("Pushback round")
    ax.set_ylabel("Cumulative cave rate (%)")
    ax.set_title("Does sustained pressure eventually break it? (hard-mode escalation)")
    ax.set_xticks(sorted({r for rates in curve.values() for r in rates}))
    ax.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "hard_cave_rate_by_round.png", dpi=150)
    plt.close()
    print(f"\nWrote {out_dir / 'leaderboard_hard.csv'}")
    print(f"Wrote {plots_dir / 'hard_cave_rate_by_round.png'}")


if __name__ == "__main__":
    main()
