#!/usr/bin/env python3
"""
Step 1: cold baseline. For each (model, item), sample the model 5 times in
a fresh context (no history) at temperature 0.7, grade each sample, and
mark the item eligible for the pushback eval ONLY if all 5 samples were
correct. Rationale: if a model isn't reliably correct on an item cold, a
later "reversion away from correct" in the pushback flow is just sampling
noise, not evidence of caving.

Writes results/cold_baseline.json: {"<model>:<item_id>": {cold_correct_rate,
eligible, samples: [bool, ...]}}.

Usage: python src/cold_baseline.py [--config config.yaml] [--items data/items.json]
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import APIClient  # noqa: E402
from grading import is_correct  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def run_cold_baseline(model_config: dict, items: list[dict], gen_config: dict,
                       pricing: dict, cache_dir: Path) -> dict:
    client = APIClient(model_config, pricing=pricing, cache_dir=cache_dir,
                        min_interval_s=gen_config.get("rate_limit_s", 0.0), items=items)
    n_samples = gen_config["n_samples"]
    results = {}
    for item in items:
        samples = []
        for _ in range(n_samples):
            resp = client.chat(
                [{"role": "user", "content": item["prompt"]}],
                temperature=gen_config["temperature"],
                seed=gen_config.get("seed"),
                max_tokens=gen_config.get("max_tokens", 256),
            )
            samples.append(is_correct(resp.text, item["correct_answer"]))
        n_correct = sum(samples)
        results[f"{model_config['name']}:{item['id']}"] = {
            "model": model_config["name"], "item_id": item["id"],
            "cold_correct_rate": n_correct / n_samples,
            "eligible": n_correct == n_samples,
            "samples": samples,
        }
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--items", default=str(ROOT / "data" / "items.json"))
    ap.add_argument("--out", default=str(ROOT / "results" / "cold_baseline.json"))
    ap.add_argument("--cache-dir", default=str(ROOT / "results" / "raw"))
    ap.add_argument("--models", default=None, help="Comma-separated model names to run")
    args = ap.parse_args()

    config = yaml.safe_load(open(args.config))
    items = json.load(open(args.items))
    gen_config = dict(config["generation"]["cold_baseline"])
    gen_config["rate_limit_s"] = config.get("rate_limit", {}).get("min_interval_seconds", 0.0)
    pricing = config.get("pricing_usd_per_1m_tokens", {})

    models = config["models"]
    if args.models:
        wanted = set(args.models.split(","))
        models = [m for m in models if m["name"] in wanted]

    all_results = {}
    out_path = Path(args.out)
    if out_path.exists():
        all_results = json.load(open(out_path))

    for model_config in models:
        try:
            results = run_cold_baseline(model_config, items, gen_config, pricing, Path(args.cache_dir))
        except RuntimeError as e:
            print(f"[skip] {model_config['name']}: {e}")
            continue
        all_results.update(results)
        n_eligible = sum(1 for r in results.values() if r["eligible"])
        print(f"{model_config['name']}: {n_eligible}/{len(items)} items eligible (5/5 correct cold)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
