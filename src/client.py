"""
Unified API client for the compliance-vs-persuasion probe.

Wraps provider SDKs (OpenAI-compatible, Anthropic) plus a synthetic Mock
provider behind one interface:

    client.chat(messages, temperature=0.0, seed=None, max_tokens=512) -> ChatResult

Every call is cached to disk keyed by a hash of (model name, messages,
temperature, seed, max_tokens) in results/raw/<hash>.json, so a re-run
never re-spends money on a request already made -- always check the cache
hit rate before assuming a "re-run" actually cost anything.

Real providers get retry-with-backoff on rate limits and an optional
inter-call sleep (config.yaml's rate_limit.min_interval_seconds), applied
only on cache misses. Cost is estimated from config.yaml's
pricing_usd_per_1m_tokens; a model missing from that table logs cost as
None rather than guessing at a price.

This is a separate implementation from src/models.py's ModelClient
hierarchy (used by the original single-turn sycophancy benchmark), not a
subclass of it: that harness's clients return a bare string with a fixed
temperature and no usage data, which isn't enough for this probe's cold-
baseline sampling (variable temperature) or cost logging (needs token
counts). Keeping this separate avoids risking a regression in the other,
already-verified harness.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    cached: bool
    # Mean log-probability of the completion's own tokens, when requested
    # via chat(..., want_logprobs=True) and the provider supports it. None
    # when not requested, or when the provider rejects the logprobs param
    # (as of writing: Mistral's and Groq's OpenAI-compatible endpoints both
    # reject it with a 400 for every model wired into this project -- see
    # README_compliance.md). A token-level probability is a much harder
    # signal to game than a self-reported "how confident are you" answer,
    # which is why this exists as an alternative to the confidence probe.
    avg_logprob: float | None = None


class RateLimitError(Exception):
    """Raised by a provider implementation on a 429; caught by APIClient's retry loop."""


class TransientServerError(Exception):
    """Raised by a provider implementation on a transient 5xx (e.g. 503
    'temporarily unavailable due to high load'); caught by APIClient's
    retry loop the same way as a rate limit."""


def _cache_key(model_name, messages, temperature, seed, max_tokens, want_logprobs) -> str:
    payload = json.dumps(
        {"model": model_name, "messages": messages, "temperature": temperature,
         "seed": seed, "max_tokens": max_tokens, "want_logprobs": want_logprobs},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class APIClient:
    def __init__(self, model_config: dict, pricing: dict | None = None,
                 cache_dir: str | Path = "results/raw", min_interval_s: float = 0.0,
                 items: list[dict] | None = None):
        self.name = model_config["name"]
        self.provider = model_config["provider"]
        self.model_id = model_config.get("model_id")
        self.pricing = (pricing or {}).get(self.name)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval_s = min_interval_s
        self._last_call_ts = 0.0
        self.total_cost_usd = 0.0
        self.total_calls = 0
        self.cache_hits = 0

        if self.provider == "mock":
            # The mock needs to know each item's correct_answer to produce
            # grader-passing text -- real providers never see this, it's
            # demo/test wiring only.
            items_by_prompt = {it["prompt"]: it["correct_answer"] for it in (items or [])}
            self._impl = _MockProvider(self.name, items_by_prompt,
                                        **model_config.get("mock_params", {}))
        elif self.provider == "anthropic":
            self._impl = _AnthropicProvider(
                self.model_id, model_config.get("api_key_env", "ANTHROPIC_API_KEY"), self.name)
        elif self.provider == "openai_compatible":
            self._impl = _OpenAICompatibleProvider(
                self.model_id, model_config["api_key_env"], model_config.get("base_url"), self.name)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def chat(self, messages: list[dict], temperature: float = 0.0,
             seed: int | None = None, max_tokens: int = 512,
             want_logprobs: bool = False) -> ChatResult:
        self.total_calls += 1
        key = _cache_key(self.name, messages, temperature, seed, max_tokens, want_logprobs)
        cache_path = self.cache_dir / f"{key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            self.cache_hits += 1
            return ChatResult(text=cached["text"], prompt_tokens=cached["prompt_tokens"],
                               completion_tokens=cached["completion_tokens"],
                               cost_usd=cached["cost_usd"], cached=True,
                               avg_logprob=cached.get("avg_logprob"))

        if self.min_interval_s:
            elapsed = time.time() - self._last_call_ts
            if elapsed < self.min_interval_s:
                time.sleep(self.min_interval_s - elapsed)

        text, prompt_tokens, completion_tokens, avg_logprob = self._call_with_retry(
            messages, temperature, seed, max_tokens, want_logprobs)
        self._last_call_ts = time.time()
        cost = self._estimate_cost(prompt_tokens, completion_tokens)
        if cost:
            self.total_cost_usd += cost

        cache_path.write_text(json.dumps({
            "text": text, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "cost_usd": cost,
            "avg_logprob": avg_logprob,
            "model": self.name, "messages": messages,
            "temperature": temperature, "seed": seed, "max_tokens": max_tokens,
        }))
        return ChatResult(text=text, prompt_tokens=prompt_tokens,
                           completion_tokens=completion_tokens, cost_usd=cost, cached=False,
                           avg_logprob=avg_logprob)

    def _call_with_retry(self, messages, temperature, seed, max_tokens, want_logprobs,
                          max_retries=6):
        delay = 3.0
        for attempt in range(max_retries):
            try:
                return self._impl.call(messages, temperature, seed, max_tokens, want_logprobs)
            except (RateLimitError, TransientServerError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2

    def _estimate_cost(self, prompt_tokens, completion_tokens):
        if not self.pricing:
            return None
        return ((prompt_tokens / 1e6) * self.pricing.get("input", 0)
                + (completion_tokens / 1e6) * self.pricing.get("output", 0))


class _AnthropicProvider:
    def __init__(self, model_id, api_key_env, name):
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Model '{name}' requires env var {api_key_env}, which is not set.")
        import anthropic
        self.model_id = model_id
        # An identity-linked (personal) API key -- as opposed to one scoped
        # to a specific Workspace in the Console -- requires this header on
        # every request, naming which workspace the request acts in.
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        default_headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
        self._client = anthropic.Anthropic(api_key=api_key, default_headers=default_headers)
        self._anthropic = anthropic

    def call(self, messages, temperature, seed, max_tokens, want_logprobs=False):
        # Anthropic's Messages API has no logprobs parameter at all (unlike
        # the OpenAI-compatible chat completions spec) -- there's nothing to
        # request here, so this always returns avg_logprob=None regardless
        # of want_logprobs. See README_compliance.md's logprobs section.
        try:
            try:
                resp = self._client.messages.create(
                    model=self.model_id, max_tokens=max_tokens,
                    temperature=temperature, messages=messages,
                )
            except TypeError:
                # Some SDK builds reject the temperature kwarg outright.
                resp = self._client.messages.create(
                    model=self.model_id, max_tokens=max_tokens, messages=messages,
                )
        except self._anthropic.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except self._anthropic.InternalServerError as e:
            raise TransientServerError(str(e)) from e
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text, resp.usage.input_tokens, resp.usage.output_tokens, None


class _OpenAICompatibleProvider:
    def __init__(self, model_id, api_key_env, base_url, name):
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Model '{name}' requires env var {api_key_env}, which is not set.")
        from openai import OpenAI
        import openai
        self.model_id = model_id
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._openai = openai

    def call(self, messages, temperature, seed, max_tokens, want_logprobs=False):
        kwargs = dict(model=self.model_id, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
        if seed is not None:
            kwargs["seed"] = seed
        if want_logprobs:
            kwargs["logprobs"] = True
        try:
            resp = self._call(kwargs)
        except self._openai.UnprocessableEntityError as e:
            # Some OpenAI-compatible endpoints (e.g. Mistral's) reject the
            # "seed" field outright rather than silently ignoring it.
            if "seed" in kwargs and "seed" in str(e):
                kwargs.pop("seed")
                resp = self._call(kwargs)
            else:
                raise
        except self._openai.BadRequestError as e:
            # As of writing, Mistral's and Groq's OpenAI-compatible endpoints
            # both reject logprobs=True outright ("logprobs are not enabled
            # for this model" / "not supported with this model") rather than
            # silently ignoring it, for every model wired into this project.
            # Degrade gracefully rather than crash the whole call: retry
            # once without logprobs and just report avg_logprob=None, same
            # as if it had never been requested.
            if want_logprobs and "logprobs" in str(e).lower():
                kwargs.pop("logprobs")
                resp = self._call(kwargs)
                want_logprobs = False
            else:
                raise
        usage = resp.usage
        avg_logprob = self._extract_avg_logprob(resp) if want_logprobs else None
        return resp.choices[0].message.content, usage.prompt_tokens, usage.completion_tokens, avg_logprob

    @staticmethod
    def _extract_avg_logprob(resp):
        lp = getattr(resp.choices[0], "logprobs", None)
        content = getattr(lp, "content", None) if lp else None
        if not content:
            return None
        return sum(tok.logprob for tok in content) / len(content)

    def _call(self, kwargs):
        try:
            return self._client.chat.completions.create(**kwargs)
        except self._openai.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except self._openai.InternalServerError as e:
            raise TransientServerError(str(e)) from e


class _MockProvider:
    """
    Synthetic provider for dry runs and demos -- no API key, no cost, no
    network. Deliberately simple: correctness/caving is driven by hashing
    (model name, the conversation's ORIGINAL prompt) so every branch of a
    conversation (a cold sample, the official pushback ask, a fresh-context
    re-ask) that starts from the same question is self-consistent, without
    needing item IDs threaded through the client interface. At temperature
    0 the decision is deterministic (like real greedy decoding); at
    temperature > 0 it's randomized per call (simulating real sampling
    variance across the 5 cold-baseline draws).

    Any result produced by this provider is a demo/test artifact, not a
    benchmark finding.
    """

    def __init__(self, name, items_by_prompt, base_accuracy=0.9, cave_rate=0.3, hedge_rate=0.1):
        self.name = name
        self.items_by_prompt = items_by_prompt
        self.base_accuracy = base_accuracy
        self.cave_rate = cave_rate
        self.hedge_rate = hedge_rate

    def _prob(self, key: str, temperature: float) -> float:
        if temperature and temperature > 0:
            import random
            return random.random()
        h = hashlib.sha256(f"{self.name}:{key}".encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    @staticmethod
    def _wrong_variant(correct_answer: str) -> str:
        s = str(correct_answer)
        if s.replace(".", "", 1).replace("-", "", 1).isdigit():
            try:
                return str(int(float(s)) + 1)
            except ValueError:
                pass
        return f"not {s}"

    def call(self, messages, temperature, seed, max_tokens, want_logprobs=False):
        time.sleep(0.005)
        original_prompt = messages[0]["content"]
        last = messages[-1]["content"].lower()
        correct_answer = self.items_by_prompt.get(original_prompt, "UNKNOWN")
        # A fake but plausible logprob when requested, so code paths that
        # consume avg_logprob can be exercised in tests/demos without a
        # provider that actually supports it -- higher (closer to 0) when
        # the mock is more "sure" of what it just said.
        fake_logprob = -0.05 if want_logprobs else None

        if "scale of 0" in last or "how confident" in last:
            # Confidence probe: higher if the conversation never caved.
            caved_recently = any(
                "reconsider" in m["content"].lower() or "not fully certain" in m["content"].lower()
                for m in messages if m["role"] == "assistant"
            )
            base = 55 if caved_recently else 90
            jitter = int(self._prob(original_prompt + str(len(messages)), temperature) * 15)
            return str(base + jitter), 20, 3, fake_logprob

        if len(messages) == 1:
            # Fresh ask (cold-baseline sample, the official first ask, or a
            # fresh-context re-ask post-cave): correctness is the base rate.
            is_correct = self._prob(original_prompt, temperature) < self.base_accuracy
            answer = correct_answer if is_correct else self._wrong_variant(correct_answer)
            return f"The answer is {answer}.", 15, 8, fake_logprob if is_correct else -1.2

        # A pushback turn: decide cave / hold / hedge.
        r = self._prob(original_prompt + ":pushback", temperature)
        if r < self.hedge_rate:
            return "I'm not fully certain now -- it's possible I made an error.", 15, 12, fake_logprob
        if r < self.hedge_rate + self.cave_rate:
            wrong = self._wrong_variant(correct_answer)
            return (f"You make a good point, let me reconsider -- I was likely wrong. "
                    f"It's probably {wrong}.", 15, 14, fake_logprob)
        return (f"I'll stand by my original answer of {correct_answer}; "
                f"I don't see new evidence against it.", 15, 15, fake_logprob)
