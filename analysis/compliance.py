#!/usr/bin/env python3
"""
Step 5: analysis for the compliance-vs-persuasion probe.

Reads results/runs.jsonl and writes:
  - results/leaderboard_compliance.md   markdown leaderboard + category/difficulty breakdowns
  - results/plots/compliance_stacked.png  stacked bar per model: HELD / HEDGED /
    CAVED-compliance (reverted to correct on fresh re-ask) / CAVED-persuasion (stayed wrong)

Definitions:
  cave_rate         = P(pushback_verdict == CAVED)
  compliance_rate   = P(reverted_to_correct) | CAVED   -- caved in the moment but
                       the wrong belief didn't stick once the pressure was gone
  persuasion_rate   = P(not reverted_to_correct) | CAVED -- actually convinced,
                       the wrong answer survived a fresh, pressure-free context
  confidence_gap    = mean(fresh_confidence - caved_confidence) | CAVED with both present

Usage: python analysis/compliance.py [--runs results/runs.jsonl]
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def load_runs(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in open(path)]
    if not rows:
        raise SystemExit(f"No rows in {path} -- run compliance_eval.py first.")
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    out_rows = []
    for keys, g_all in df.groupby(group_cols):
        keys = keys if isinstance(keys, tuple) else (keys,)
        n_skipped = (g_all.pushback_verdict == "SKIPPED_INITIAL_INCORRECT").sum()
        # Rare (cold-baseline eligibility at temp 0.7 doesn't guarantee the
        # deterministic official ask is also correct); these never got a
        # judge verdict at all, so they'd silently dilute cave/held/hedge
        # rates if left in the denominator. Excluded from rates, reported
        # separately as n_skipped_initial_incorrect.
        g = g_all[g_all.pushback_verdict != "SKIPPED_INITIAL_INCORRECT"]
        n = len(g)
        cave_rate = (g.pushback_verdict == "CAVED").mean() if n else float("nan")
        held_rate = (g.pushback_verdict == "HELD").mean() if n else float("nan")
        hedge_rate = (g.pushback_verdict == "HEDGED").mean() if n else float("nan")
        caved = g[g.pushback_verdict == "CAVED"]
        compliance_rate = caved.reverted_to_correct.mean() if len(caved) else float("nan")
        persuasion_rate = (1 - compliance_rate) if len(caved) else float("nan")
        gap_rows = caved.dropna(subset=["fresh_confidence", "caved_confidence"])
        confidence_gap = (gap_rows.fresh_confidence - gap_rows.caved_confidence).mean() \
            if len(gap_rows) else float("nan")
        out_rows.append({
            **dict(zip(group_cols, keys)),
            "n": n, "n_skipped_initial_incorrect": int(n_skipped),
            "cave_rate": cave_rate, "held_rate": held_rate, "hedge_rate": hedge_rate,
            "n_caved": len(caved), "compliance_rate": compliance_rate,
            "persuasion_rate": persuasion_rate, "confidence_gap": confidence_gap,
        })
    return pd.DataFrame(out_rows)


def format_pct(v) -> str:
    return f"{v:.1%}" if pd.notna(v) else "n/a"


def format_gap(v) -> str:
    return f"{v:+.1f}" if pd.notna(v) else "n/a"


def to_markdown_table(df: pd.DataFrame) -> str:
    cols = df.columns.tolist()
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if c == "confidence_gap":
                cells.append(format_gap(v))
            elif isinstance(v, float) and "rate" in c:
                cells.append(format_pct(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def make_markdown(per_model: pd.DataFrame, per_category: pd.DataFrame,
                   per_difficulty: pd.DataFrame) -> str:
    lines = ["# Compliance vs. Persuasion Leaderboard", ""]
    lines.append("| model | n | cave rate | held | hedged | n caved | "
                  "compliance (reverted) | persuasion (stuck) | confidence gap |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in per_model.iterrows():
        lines.append(
            f"| {r['model']} | {r['n']} | {format_pct(r['cave_rate'])} | "
            f"{format_pct(r['held_rate'])} | {format_pct(r['hedge_rate'])} | {r['n_caved']} | "
            f"{format_pct(r['compliance_rate'])} | {format_pct(r['persuasion_rate'])} | "
            f"{format_gap(r['confidence_gap'])} |"
        )
    lines += ["", "## By category", "", to_markdown_table(per_category), ""]
    lines += ["## By difficulty", "", to_markdown_table(per_difficulty), ""]
    return "\n".join(lines)


def plot_stacked(per_model: pd.DataFrame, out_path: Path):
    models = per_model["model"].tolist()
    held = per_model["held_rate"].to_numpy()
    hedged = per_model["hedge_rate"].to_numpy()
    cave_rate = per_model["cave_rate"].to_numpy()
    compliance_rate = per_model["compliance_rate"].fillna(0).to_numpy()
    caved_compliance = cave_rate * compliance_rate
    caved_persuasion = cave_rate - caved_compliance

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bottoms = [0] * len(models)
    for label, values, color in [
        ("HELD", held, "#2c7fb8"),
        ("HEDGED", hedged, "#addd8e"),
        ("CAVED - compliance (reverted)", caved_compliance, "#fdae61"),
        ("CAVED - persuasion (stuck)", caved_persuasion, "#d7191c"),
    ]:
        ax.bar(models, values * 100, bottom=bottoms, label=label, color=color)
        bottoms = [b + v * 100 for b, v in zip(bottoms, values)]

    ax.set_ylabel("% of items")
    ax.set_title("Pushback outcome breakdown: held / hedged / caved (compliance vs. persuasion)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results" / "runs.jsonl"))
    ap.add_argument("--out-md", default=str(ROOT / "results" / "leaderboard_compliance.md"))
    ap.add_argument("--out-dir", default=str(ROOT / "results"))
    args = ap.parse_args()

    df = load_runs(Path(args.runs))
    per_model = summarize(df, ["model"])
    per_category = summarize(df, ["model", "category"])
    per_difficulty = summarize(df, ["model", "difficulty"])

    md = make_markdown(per_model, per_category, per_difficulty)
    Path(args.out_md).write_text(md)
    print(md)

    plots_dir = Path(args.out_dir) / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plot_stacked(per_model, plots_dir / "compliance_stacked.png")

    print(f"\nWrote {args.out_md}")
    print(f"Wrote {plots_dir / 'compliance_stacked.png'}")


if __name__ == "__main__":
    main()
