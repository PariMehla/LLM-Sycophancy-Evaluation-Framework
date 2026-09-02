#!/usr/bin/env python3
"""
Run the sycophancy-under-pushback eval against configured models.

For each dataset item and each model:
  Turn 1: ask the question fresh -> record initial_response
  Turn 2: append the model's own initial reply, then the pushback message
          (which asserts an incorrect answer) -> record final_response

Raw transcripts are written to results/raw/<model_name>.jsonl (one line per
item) so grading and analysis are separate, reproducible steps over saved
data rather than requiring live API calls again.

A model in configs/models.json whose API key isn't set is skipped with a
warning (not a hard failure), so you can run a partial roster.

Usage:
    python src/run_eval.py                      # all models in configs/models.json
    python src/run_eval.py --models mock-large-confident,mock-small-sycophantic
    python src/run_eval.py --config configs/models.json --dataset data/dataset.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from models import load_models_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def build_question_message(item: dict) -> str:
    tag = (f"[[TAG turn=1 id={item['id']} correct={item['correct_answer']} "
           f"wrong={item['incorrect_answer_claimed']} difficulty={item['difficulty']} "
           f"strength={item['pushback_strength']}]]")
    # The tag is invisible to a real model (it's just trailing text a real LLM
    # ignores as noise) but lets the MockClient know the ground truth for
    # this turn without a real model in the loop. Real API calls include it
    # too for simplicity; it costs a few tokens and models do not act on it.
    return f"{item['question']}\n\n{tag}"


def build_pushback_message(item: dict) -> str:
    tag = (f"[[TAG turn=2 id={item['id']} correct={item['correct_answer']} "
           f"wrong={item['incorrect_answer_claimed']} difficulty={item['difficulty']} "
           f"strength={item['pushback_strength']}]]")
    return f"{item['pushback']}\n\n{tag}"


def run_one_model(client, dataset, out_path, sleep_s=0.0):
    results = []
    for item in dataset:
        q_msg = build_question_message(item)
        t0 = time.time()
        initial_response = client.chat([{"role": "user", "content": q_msg}])
        t1 = time.time()

        pushback_msg = build_pushback_message(item)
        messages = [
            {"role": "user", "content": q_msg},
            {"role": "assistant", "content": initial_response},
            {"role": "user", "content": pushback_msg},
        ]
        final_response = client.chat(messages)
        t2 = time.time()

        results.append({
            "id": item["id"],
            "category": item["category"],
            "difficulty": item["difficulty"],
            "pushback_strength": item["pushback_strength"],
            "question": item["question"],
            "correct_answer": item["correct_answer"],
            "answer_aliases": item.get("answer_aliases", []),
            "incorrect_answer_claimed": item["incorrect_answer_claimed"],
            "pushback": item["pushback"],
            "initial_response": initial_response,
            "final_response": final_response,
            "latency_initial_s": round(t1 - t0, 3),
            "latency_final_s": round(t2 - t1, 3),
        })
        if sleep_s:
            time.sleep(sleep_s)

    with open(out_path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "models.json"))
    ap.add_argument("--dataset", default=str(ROOT / "data" / "dataset.json"))
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "raw"))
    ap.add_argument("--models", default=None,
                     help="Comma-separated model names to run; default is all in config")
    ap.add_argument("--sleep", type=float, default=0.0,
                     help="Seconds to sleep between items (rate limiting for real APIs)")
    args = ap.parse_args()

    with open(args.config) as f:
        raw_config = json.load(f)
    if args.models:
        wanted = set(args.models.split(","))
        raw_config = [c for c in raw_config if c["name"] in wanted]

    with open(args.dataset) as f:
        dataset = json.load(f)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Construct clients one at a time so a missing key for one model
    # doesn't prevent running the others.
    import tempfile
    for entry in raw_config:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump([entry], tf)
            single_config_path = tf.name
        try:
            clients = load_models_config(single_config_path)
        except RuntimeError as e:
            print(f"[skip] {entry['name']}: {e}")
            continue
        client = clients[0]
        print(f"[run] {client.name} on {len(dataset)} items...")
        out_path = out_dir / f"{client.name}.jsonl"
        try:
            run_one_model(client, dataset, out_path, sleep_s=args.sleep)
        except Exception as e:
            print(f"[error] {client.name} failed mid-run, skipping: {e}")
            continue
        print(f"[done] {client.name} -> {out_path}")


if __name__ == "__main__":
    main()
