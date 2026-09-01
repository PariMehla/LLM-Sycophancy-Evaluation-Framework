#!/usr/bin/env python3
"""
Tests for the optional logprobs plumbing in src/client.py (APIClient.chat's
want_logprobs param): a token-level confidence signal, as an alternative to
the model's self-reported "how confident are you" answer.

As of writing, neither real provider wired into this project's config.yaml
(Mistral Small, gpt-oss-120b via Groq) supports logprobs on their
OpenAI-compatible endpoints -- both reject `logprobs=True` with a 400
("logprobs are not enabled for this model" / "not supported with this
model"). These tests cover the machinery against the mock provider (which
always "supports" it, so the parsing/plumbing path is exercised) and
document the graceful-degradation behavior confirmed by hand against the
real Mistral API (see README_compliance.md) rather than re-hitting a real
API from a unit test.

Run: python -m unittest tests/test_client_logprobs.py -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from client import APIClient, _cache_key  # noqa: E402

ITEMS = [{"prompt": "What is 2+2?", "correct_answer": "4"}]


def make_client(cache_dir: str) -> APIClient:
    model_config = {"name": "mock-agreeable", "provider": "mock",
                     "mock_params": {"base_accuracy": 0.95, "cave_rate": 0.45, "hedge_rate": 0.1}}
    return APIClient(model_config, cache_dir=cache_dir, items=ITEMS)


class LogprobsTest(unittest.TestCase):
    def test_want_logprobs_true_returns_a_value(self):
        with tempfile.TemporaryDirectory() as d:
            client = make_client(d)
            result = client.chat([{"role": "user", "content": "What is 2+2?"}],
                                  temperature=0.0, want_logprobs=True)
            self.assertIsNotNone(result.avg_logprob)

    def test_want_logprobs_false_is_none_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            client = make_client(d)
            result = client.chat([{"role": "user", "content": "What is 2+2?"}], temperature=0.0)
            self.assertIsNone(result.avg_logprob)

    def test_logprobs_flag_changes_the_cache_key(self):
        """A logprobs-requested call must not be silently served a cached
        response from a prior call that never captured logprobs (or vice
        versa) -- they're genuinely different requests."""
        messages = [{"role": "user", "content": "What is 2+2?"}]
        key_with = _cache_key("mock-agreeable", messages, 0.0, None, 512, True)
        key_without = _cache_key("mock-agreeable", messages, 0.0, None, 512, False)
        self.assertNotEqual(key_with, key_without)

    def test_cached_result_preserves_avg_logprob(self):
        with tempfile.TemporaryDirectory() as d:
            client = make_client(d)
            messages = [{"role": "user", "content": "What is 2+2?"}]
            first = client.chat(messages, temperature=0.0, want_logprobs=True)
            second = client.chat(messages, temperature=0.0, want_logprobs=True)
            self.assertTrue(second.cached)
            self.assertEqual(first.avg_logprob, second.avg_logprob)


if __name__ == "__main__":
    unittest.main()
