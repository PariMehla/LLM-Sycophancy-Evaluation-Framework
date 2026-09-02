#!/usr/bin/env python3
"""
Does increasing sampling temperature make a model more susceptible to
social pressure? Reads a set of results/runs_temp_<T>.jsonl files (one per
temperature, produced by `compliance_eval.py --pushback-temperature T`,
holding the item set, eligibility, judge, and confidence-probe settings
fixed) and reports cave_rate vs. temperature, with bootstrap CIs.

Scoped to a single model deliberately: a full model x temperature grid is
16x the API calls of a single run, and this project has already hit a
real daily quota wall running the base probe once (see
README_compliance.md) -- so this starts with the one real model that has
no such quota (Mistral Small) rather than promising a grid it can't
finish.

Outputs:
  - results/temperature_sweep.md   table + a plain-language read of the trend
  - results/plots/temperature_sweep.png   cave rate vs. temperature, with
    95% CI error bars and the eligible-item-count trend on a second axis

Usage: python analysis/temperature_sweep.py --model mistral-small \
           --temps 0.0,0.3,0.7,1.0
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
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 42


def bootstrap_ci(caved: np.ndarray, n_boot: int = BOOTSTRAP_N,
                  seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    n = len(caved)
    if n == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    rates = caved[idx].mean(axis=1)
    return float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5))


def load_one_temperature(path: Path, temperature: float) -> dict:
    if not path.exists():
        return {"temperature": temperature, "n": 0, "n_skipped_initial_incorrect": 0,
                "n_caved": 0, "cave_rate": float("nan"),
                "cave_rate_ci_low": float("nan"), "cave_rate_ci_high": float("nan")}
    rows = [json.loads(line) for line in open(path)]
    df = pd.DataFrame(rows)
    n_skipped = int((df.pushback_verdict == "SKIPPED_INITIAL_INCORRECT").sum())
    elig = df[df.pushback_verdict != "SKIPPED_INITIAL_INCORRECT"]
    caved = (elig.pushback_verdict == "CAVED").to_numpy()
    ci_low, ci_high = bootstrap_ci(caved)
    return {
        "temperature": temperature,
        "n": len(elig),
        "n_skipped_initial_incorrect": n_skipped,
        "n_caved": int(caved.sum()) if len(caved) else 0,
        "cave_rate": float(caved.mean()) if len(caved) else float("nan"),
        "cave_rate_ci_low": ci_low,
        "cave_rate_ci_high": ci_high,
    }


def plot_sweep(sweep: pd.DataFrame, model: str, out_path: Path):
    fig, ax1 = plt.subplots(figsize=(8, 5.5))
    valid = sweep.dropna(subset=["cave_rate"])
    yerr = [
        (valid.cave_rate - valid.cave_rate_ci_low).to_numpy() * 100,
        (valid.cave_rate_ci_high - valid.cave_rate).to_numpy() * 100,
    ]
    ax1.errorbar(valid.temperature, valid.cave_rate * 100, yerr=yerr,
                 marker="o", markersize=8, capsize=5, color="#d7191c",
                 label="Cave rate (95% CI)")
    ax1.set_xlabel("Pushback temperature (official ask + pushback response)")
    ax1.set_ylabel("Cave rate (%)", color="#d7191c")
    ax1.tick_params(axis="y", labelcolor="#d7191c")
    ax1.set_ylim(bottom=0)

    ax2 = ax1.twinx()
    ax2.plot(sweep.temperature, sweep.n, marker="s", markersize=6,
             linestyle="--", color="#2c7fb8", label="n eligible for pushback (initial_correct)")
    ax2.set_ylabel("n items reaching the judge (initial_correct=True)", color="#2c7fb8")
    ax2.tick_params(axis="y", labelcolor="#2c7fb8")

    ax1.set_title(f"Cave rate vs. pushback temperature -- {model}")
    fig.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def make_markdown(sweep: pd.DataFrame, model: str) -> str:
    lines = [f"# Temperature Sweep: {model}", ""]
    lines.append(
        "Does turning up sampling temperature on the official ask + "
        "pushback response make the model more susceptible to social "
        "pressure? Item set, cold-baseline eligibility, judge, and "
        "confidence-probe settings are held fixed across all rows -- only "
        "the pushback-flow temperature varies -- so any trend here isn't "
        "confounded by a different set of items being tested at each "
        "temperature."
    )
    lines.append("")
    lines.append("| temperature | n eligible (initial_correct) | n skipped "
                  "(initial_correct=False) | n caved | cave rate (95% CI) |")
    lines.append("|---|---|---|---|---|")
    for _, r in sweep.iterrows():
        ci = f"[{r['cave_rate_ci_low']:.1%}, {r['cave_rate_ci_high']:.1%}]" \
            if pd.notna(r["cave_rate_ci_low"]) else "n/a"
        rate = f"{r['cave_rate']:.1%}" if pd.notna(r["cave_rate"]) else "n/a"
        lines.append(f"| {r['temperature']} | {r['n']} | {r['n_skipped_initial_incorrect']} | "
                      f"{r['n_caved']} | {rate} {ci} |")
    lines.append("")

    valid = sweep.dropna(subset=["cave_rate"])
    if len(valid) >= 2:
        lo, hi = valid.iloc[0], valid.iloc[-1]
        direction = "rises" if hi.cave_rate > lo.cave_rate else \
            "falls" if hi.cave_rate < lo.cave_rate else "stays flat"
        lines.append(
            f"**Read:** cave rate {direction} from {lo.cave_rate:.1%} at "
            f"temperature {lo.temperature} to {hi.cave_rate:.1%} at "
            f"temperature {hi.temperature}. Also watch the `n skipped` "
            f"column: at higher temperature the *official ask itself* "
            f"becomes less reliably correct (more sampling noise on the "
            f"same question the cold baseline said it reliably knows at "
            f"temperature 0.7), which shrinks the pool of items that even "
            f"reach the pushback/judge step -- a real side effect of "
            f"turning up temperature, not just a change in cave rate among "
            f"a fixed set of items."
        )
    lines.append("")
    lines.append(
        "**Scope note:** this sweep covers Mistral Small only. A full "
        "model x temperature grid was considered and deliberately scoped "
        "down -- it would be 16x the API calls of a single run, and this "
        "project has already hit a real daily quota wall (Groq, "
        "gpt-oss-120b) running the base probe just once. Read this as "
        "\"what temperature does to one real model's cave rate,\" not yet "
        "\"whether this generalizes across models.\""
    )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mistral-small")
    ap.add_argument("--temps", default="0.0,0.3,0.7,1.0")
    ap.add_argument("--runs-dir", default=str(ROOT / "results"))
    ap.add_argument("--out-md", default=str(ROOT / "results" / "temperature_sweep.md"))
    ap.add_argument("--out-plot", default=str(ROOT / "results" / "plots" / "temperature_sweep.png"))
    args = ap.parse_args()

    temps = [float(t) for t in args.temps.split(",")]
    runs_dir = Path(args.runs_dir)
    rows = [load_one_temperature(runs_dir / f"runs_temp_{t}.jsonl", t) for t in temps]
    sweep = pd.DataFrame(rows).sort_values("temperature").reset_index(drop=True)

    md = make_markdown(sweep, args.model)
    Path(args.out_md).write_text(md)
    print(md)

    out_plot = Path(args.out_plot)
    out_plot.parent.mkdir(parents=True, exist_ok=True)
    plot_sweep(sweep, args.model, out_plot)
    print(f"\nWrote {args.out_md}")
    print(f"Wrote {out_plot}")


if __name__ == "__main__":
    main()
