"""
Pluggable model clients for the sycophancy eval harness.

Every client implements one method:

    chat(messages: list[dict]) -> str

where `messages` is an OpenAI-style list of {"role": ..., "content": ...}
dicts, and the return value is the assistant's text reply for the *next*
turn. The harness calls this twice per item (once for the initial question,
once more with the pushback message appended to history), so clients must be
stateless / accept full history each call.

Configure models in configs/models.json (see that file for the format).
Real clients read API keys from environment variables — nothing is
hardcoded. If a required key is missing, the client raises at construction
time with a clear message rather than failing confusingly mid-run.
"""
from __future__ import annotations

import hashlib
import os
import random
import time


class ModelClient:
    name: str
    params_billion: float | None = None

    def chat(self, messages: list[dict]) -> str:
        raise NotImplementedError


class OpenAICompatibleClient(ModelClient):
    """
    Works for OpenAI itself and for any OpenAI-compatible endpoint
    (Groq, Together, Fireworks, local vLLM, etc.) by overriding base_url.
    This is how you'd point at GPT-4o-mini (OpenAI) or Llama-3-70B /
    Mistral (Groq or Together) with the same client class.
    """

    def __init__(self, name, model_id, api_key_env, base_url=None, params_billion=None):
        self.name = name
        self.model_id = model_id
        self.params_billion = params_billion
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Model '{name}' requires env var {api_key_env}, which is not set. "
                f"Export it before running, or remove '{name}' from configs/models.json."
            )
        from openai import OpenAI  # lazy import so the mock path has no hard dependency
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: list[dict]) -> str:
        resp = self._client.chat.completions.create(
            model=self.model_id, messages=messages, temperature=0.0, max_tokens=512,
        )
        return resp.choices[0].message.content


class AnthropicClient(ModelClient):
    def __init__(self, name, model_id, api_key_env="ANTHROPIC_API_KEY", params_billion=None):
        self.name = name
        self.model_id = model_id
        self.params_billion = params_billion
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Model '{name}' requires env var {api_key_env}, which is not set. "
                f"Export it before running, or remove '{name}' from configs/models.json."
            )
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat(self, messages: list[dict]) -> str:
        resp = self._client.messages.create(
            model=self.model_id,
            max_tokens=512,
            temperature=0.0,
            messages=messages,
        )
        return "".join(block.text for block in resp.content if block.type == "text")


class MockClient(ModelClient):
    """
    Deterministic synthetic client used ONLY to demonstrate/test the harness
    end-to-end without any API keys. Its answers and cave/hold decisions are
    generated from a hash of (model name, item id) plus configurable bias
    knobs, NOT from a real language model. Any result produced with this
    client is a demo artifact, not a benchmark finding, and is labeled as
    such everywhere it's used in this repo.
    """

    def __init__(self, name, params_billion=None,
                 base_accuracy=0.9, cave_rate_mild=0.15, cave_rate_strong=0.35,
                 hard_penalty=0.15):
        self.name = name
        self.params_billion = params_billion
        self.base_accuracy = base_accuracy
        self.cave_rate_mild = cave_rate_mild
        self.cave_rate_strong = cave_rate_strong
        self.hard_penalty = hard_penalty
        self._pending = {}

    def _rand(self, key: str) -> float:
        h = hashlib.sha256(f"{self.name}:{key}".encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    def chat(self, messages: list[dict]) -> str:
        # Identify the item + turn from message content (harness embeds a hidden tag).
        last = messages[-1]["content"]
        item_id, turn, correct, wrong, difficulty, strength = _parse_tag(last)
        time.sleep(0.01)  # simulate latency
        if turn == 1:
            acc = self.base_accuracy - (self.hard_penalty if difficulty == "hard" else 0.0)
            is_correct = self._rand(item_id + ":t1") < acc
            answer = correct if is_correct else wrong
            self._pending[item_id] = is_correct
            return f"The answer is {answer}."
        else:
            was_correct = self._pending.get(item_id, False)
            if not was_correct:
                # already wrong; pushback claims the (still) wrong answer -> "agrees", stays wrong
                return f"You're right, the answer is {wrong}. Thanks for the correction."
            cave_rate = self.cave_rate_strong if strength == "strong" else self.cave_rate_mild
            caves = self._rand(item_id + ":t2:" + strength) < cave_rate
            if caves:
                return f"You make a good point — you're right, the correct answer is actually {wrong}."
            return f"I understand the concern, but I'm confident the answer is {correct}."


def _parse_tag(text: str):
    # Harness embeds "[[TAG turn=1 id=... correct=... wrong=... difficulty=... strength=...]]"
    import re
    m = re.search(
        r"\[\[TAG turn=(\d) id=(\S+) correct=(.*?) wrong=(.*?) difficulty=(\S+) strength=(\S+)\]\]",
        text, re.DOTALL,
    )
    if not m:
        return "unknown", 1, "", "", "easy", "mild"
    turn, item_id, correct, wrong, difficulty, strength = m.groups()
    return item_id, int(turn), correct, wrong, difficulty, strength


def load_models_config(path: str) -> list[ModelClient]:
    import json
    with open(path) as f:
        config = json.load(f)
    clients = []
    for entry in config:
        provider = entry["provider"]
        if provider == "mock":
            clients.append(MockClient(
                name=entry["name"],
                params_billion=entry.get("params_billion"),
                **entry.get("mock_params", {}),
            ))
        elif provider == "anthropic":
            clients.append(AnthropicClient(
                name=entry["name"], model_id=entry["model_id"],
                api_key_env=entry.get("api_key_env", "ANTHROPIC_API_KEY"),
                params_billion=entry.get("params_billion"),
            ))
        elif provider == "openai_compatible":
            clients.append(OpenAICompatibleClient(
                name=entry["name"], model_id=entry["model_id"],
                api_key_env=entry["api_key_env"], base_url=entry.get("base_url"),
                params_billion=entry.get("params_billion"),
            ))
        else:
            raise ValueError(f"Unknown provider: {provider}")
    return clients
