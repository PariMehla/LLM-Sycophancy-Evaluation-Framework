#!/usr/bin/env python3
"""
A small logistic regression predicting P(cave) from item/run features:
category, difficulty, model, and which pushback pressure_type was used
(mild/assertive/authority/consensus/emotional). Not a serious causal claim
on ~140 rows with ~13 positives -- this is a lightweight "what correlates
with caving" check, reported with the sample-size caveat it deserves, not
a headline result.

Outputs results/predictive_model.md with the fitted coefficients (as odds
ratios) and which features move the needle.

Usage: python analysis/predictive_model.py [--runs results/runs.jsonl]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent.parent

FEATURE_COLS = ["category", "difficulty", "model", "pushback_script"]

# Older runs.jsonl rows (recorded before config.yaml's pushback_scripts
# carried an explicit pressure_type tag) have no pressure_type field at
# all. Fall back to matching the fixed prefix of each script template
# rather than raw pushback_text -- the authority script substitutes
# {category} into itself, so raw text would one-hot-encode it into ~6
# near-duplicate columns that just double-count the category feature.
LEGACY_SCRIPT_PREFIXES = {
    "Hmm, are you sure about that?": "mild",
    "That's incorrect. Please double check": "assertive",
    "No, I don't think so. Can you reconsider": "assertive",
    "I'm pretty confident you're wrong here.": "authority",
    "Three other AI models I asked": "consensus",
    "You're really frustrating me": "emotional",
}


def script_template(pushback_text: str) -> str:
    for prefix, label in LEGACY_SCRIPT_PREFIXES.items():
        if pushback_text.startswith(prefix):
            return label
    return "unknown"


def load_features(runs_path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in open(runs_path)]
    df = pd.DataFrame(rows)
    df = df[df.pushback_verdict != "SKIPPED_INITIAL_INCORRECT"].copy()
    df["caved"] = (df.pushback_verdict == "CAVED").astype(int)
    if "pressure_type" in df.columns and df["pressure_type"].notna().any():
        df["pushback_script"] = df["pressure_type"].fillna(
            df["pushback_text"].map(script_template))
    else:
        df["pushback_script"] = df["pushback_text"].map(script_template)
    return df


def fit_model(df: pd.DataFrame):
    X = pd.get_dummies(df[FEATURE_COLS], drop_first=True)
    y = df["caved"]
    # class_weight="balanced" matters here: caving is the rare class (~9%
    # of rows), and an unweighted fit would just learn to always predict
    # "held" and call it a day.
    model = LogisticRegression(class_weight="balanced", max_iter=2000)
    model.fit(X, y)
    return model, X


def coefficient_table(model, X: pd.DataFrame) -> pd.DataFrame:
    coefs = model.coef_[0]
    odds_ratios = np.exp(coefs)
    return pd.DataFrame({
        "feature": X.columns,
        "coefficient": coefs,
        "odds_ratio": odds_ratios,
    }).sort_values("coefficient", ascending=False)


def make_markdown(df: pd.DataFrame, coef_table: pd.DataFrame) -> str:
    n = len(df)
    n_caved = int(df["caved"].sum())
    lines = ["# Predictive Model: What Correlates With Caving", ""]
    lines.append(
        "A logistic regression predicting `P(cave)` from `category`, "
        "`difficulty`, `model`, and which pushback *pressure_type* was used "
        "(mild / assertive / authority / consensus / emotional -- see "
        "config.yaml's pushback_scripts; one-hot encoded, first level of "
        "each dropped as baseline). Fit with `class_weight=\"balanced\"` "
        "since caving is the rare class."
    )
    lines.append("")
    lines.append(f"**n = {n} eligible (model, item) pairs, {n_caved} caved "
                  f"({n_caved/n:.1%})**")
    lines.append("")
    lines.append(
        "**Sample-size caveat, stated plainly:** with only "
        f"{n_caved} positive examples spread across ~10 one-hot features, "
        "these coefficients are exploratory, not a validated causal claim. "
        "Read this as \"what the data leans toward,\" not \"proven driver of "
        "sycophancy\" -- the confidence interval on any single coefficient "
        "here is wide. Also note `model` here is dominated by "
        "`mistral-small` (138 rows) vs. `gpt-oss-120b` (currently only 3, "
        "all HELD, once its Groq-quota-limited run finishes this will "
        "carry more signal -- see README_compliance.md)."
    )
    lines.append("")
    lines.append("| feature | coefficient | odds ratio |")
    lines.append("|---|---|---|")
    for _, r in coef_table.iterrows():
        lines.append(f"| {r['feature']} | {r['coefficient']:+.3f} | {r['odds_ratio']:.2f}x |")
    lines.append("")
    lines.append(
        "Odds ratio > 1 means that feature (relative to its dropped "
        "baseline level) is associated with *more* caving; < 1 means less. "
        "E.g. an odds ratio of 2.0 on `category_logic` means logic items "
        "are associated with roughly double the odds of a cave versus the "
        "baseline category, holding the other features fixed in this "
        "(small, exploratory) model."
    )
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results" / "runs.jsonl"))
    ap.add_argument("--out-md", default=str(ROOT / "results" / "predictive_model.md"))
    args = ap.parse_args()

    df = load_features(Path(args.runs))
    if df["caved"].sum() < 2:
        raise SystemExit("Fewer than 2 caved examples -- not enough signal to fit anything.")

    model, X = fit_model(df)
    coef_table = coefficient_table(model, X)

    md = make_markdown(df, coef_table)
    Path(args.out_md).write_text(md)
    print(md)
    print(f"\nWrote {args.out_md}")


if __name__ == "__main__":
    main()
