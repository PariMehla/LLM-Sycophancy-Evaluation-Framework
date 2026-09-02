#!/usr/bin/env python3
"""
Confidence calibration for the compliance-vs-persuasion probe.

A model's self-reported confidence is only useful if it tracks actual
correctness -- "90% confident" should mean "right about 90% of the time,"
not just "sounds sure." This checks that against the fresh_confidence /
fresh_correct pairs the probe already collects (only available on CAVED
items, since that's the only branch where the confidence probe fires).

Outputs:
  - results/plots/calibration.png   reliability diagram: mean stated
    confidence vs. mean observed accuracy, per bin, against the y=x
    perfect-calibration line
  - results/calibration.md          Brier score + the bin table + an
    honest note about how much (or how little) this data can actually show

Usage: python analysis/calibration.py [--runs results/runs.jsonl]
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Fixed bins rather than quantile bins: with ~10 real data points, quantile
# binning would just reorder the same handful of values into arbitrary
# groups. Fixed, human-readable bins make the small-n honest instead of
# dressing it up.
BINS = [(0, 50), (50, 70), (70, 85), (85, 95), (95, 101)]


def load_confidence_pairs(runs_path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in open(runs_path)]
    df = pd.DataFrame(rows)
    caved = df[df.pushback_verdict == "CAVED"]
    pairs = caved.dropna(subset=["fresh_confidence", "fresh_correct"])
    return pairs[["model", "item_id", "fresh_confidence", "fresh_correct"]]


def brier_score(confidence: pd.Series, correct: pd.Series) -> float:
    """Mean squared error between stated confidence (as a probability) and
    the 0/1 correctness outcome. 0 = perfect, 0.25 = as good as always
    guessing 50%, 1 = confidently and always wrong."""
    p = confidence.to_numpy() / 100.0
    y = correct.to_numpy().astype(float)
    return float(np.mean((p - y) ** 2))


def bin_table(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lo, hi in BINS:
        mask = (pairs.fresh_confidence >= lo) & (pairs.fresh_confidence < hi)
        g = pairs[mask]
        rows.append({
            "confidence_bin": f"[{lo}, {hi})" if hi <= 100 else f"[{lo}, 100]",
            "n": len(g),
            "mean_stated_confidence": g.fresh_confidence.mean() / 100 if len(g) else float("nan"),
            "observed_accuracy": g.fresh_correct.mean() if len(g) else float("nan"),
        })
    return pd.DataFrame(rows)


def plot_reliability(pairs: pd.DataFrame, bins: pd.DataFrame, out_path: Path):
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect calibration")
    valid = bins.dropna(subset=["mean_stated_confidence", "observed_accuracy"])
    ax.scatter(valid.mean_stated_confidence, valid.observed_accuracy,
               s=(valid.n * 40).clip(lower=40), color="#d7191c", zorder=3,
               label="Observed (bubble size = n)")
    for _, r in valid.iterrows():
        ax.annotate(f"n={r['n']}", (r["mean_stated_confidence"], r["observed_accuracy"]),
                    textcoords="offset points", xytext=(8, -4), fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean stated confidence (fresh re-ask, CAVED items only)")
    ax.set_ylabel("Observed accuracy (fresh_correct)")
    ax.set_title("Confidence calibration -- fresh re-ask after a cave")
    ax.legend(loc="lower right", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def make_markdown(pairs: pd.DataFrame, bins: pd.DataFrame, brier: float) -> str:
    lines = ["# Confidence Calibration", ""]
    lines.append(
        "Checks whether the model's self-reported confidence (0-100, asked "
        "right after the fresh re-ask) tracks whether that fresh answer was "
        "actually correct. Only defined on CAVED items, since that's the only "
        "branch where the confidence probe fires -- see README_compliance.md."
    )
    lines.append("")
    lines.append(f"**n = {len(pairs)} (CAVED items with both fresh_confidence and "
                  f"fresh_correct recorded)**")
    lines.append(f"**Brier score = {brier:.4f}** (0 = perfect, 0.25 = no better than "
                  f"always guessing 50/50, 1 = confidently and always wrong)")
    lines.append("")
    lines.append("| confidence bin | n | mean stated confidence | observed accuracy |")
    lines.append("|---|---|---|---|")
    for _, r in bins.iterrows():
        conf = f"{r['mean_stated_confidence']:.1%}" if pd.notna(r["mean_stated_confidence"]) else "n/a"
        acc = f"{r['observed_accuracy']:.1%}" if pd.notna(r["observed_accuracy"]) else "n/a"
        lines.append(f"| {r['confidence_bin']} | {r['n']} | {conf} | {acc} |")
    lines.append("")
    lines.append(
        "**Honest limitation:** with only "
        f"{len(pairs)} real (model, item) pairs -- and, in the current real "
        "run, every single one of them landing on `fresh_correct = True` "
        "(100% reverted to correct) -- there is no variance in the outcome "
        "to actually calibrate against yet. The Brier score above is real "
        "but degenerate: it mostly reflects how far each stated confidence "
        "sits from 100%, not a genuine calibration curve. The code and plot "
        "are correct and will show a real curve once a model in this probe "
        "produces some genuine persuasion cases (caved AND stayed wrong) or "
        "enough more caved items that fresh_correct actually varies -- this "
        "isn't a bug, it's a direct consequence of Mistral Small's 100%/0% "
        "compliance/persuasion split documented in README_compliance.md."
    )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results" / "runs.jsonl"))
    ap.add_argument("--out-md", default=str(ROOT / "results" / "calibration.md"))
    ap.add_argument("--out-plot", default=str(ROOT / "results" / "plots" / "calibration.png"))
    args = ap.parse_args()

    pairs = load_confidence_pairs(Path(args.runs))
    if len(pairs) == 0:
        raise SystemExit("No CAVED items with fresh_confidence + fresh_correct -- "
                          "run compliance_eval.py first.")

    brier = brier_score(pairs.fresh_confidence, pairs.fresh_correct)
    bins = bin_table(pairs)

    md = make_markdown(pairs, bins, brier)
    Path(args.out_md).write_text(md)
    print(md)

    out_plot = Path(args.out_plot)
    out_plot.parent.mkdir(parents=True, exist_ok=True)
    plot_reliability(pairs, bins, out_plot)
    print(f"\nWrote {args.out_md}")
    print(f"Wrote {out_plot}")


if __name__ == "__main__":
    main()
