"""Provider-agnostic LLM client. `ExtractionTask.llmModel` is a "provider/model" string:
gemini/…, openai/…, ollama/…, groq/…, anthropic/… . All providers but Anthropic are reached through
an OpenAI-compatible endpoint; Anthropic uses its own SDK when installed.

Responses are cached on disk by sha256(provider, model, system prompt, user text, temperature), so
re-running the pipeline (or reviewers re-running it) never calls the provider twice for the same
input. Requests are throttled (rpm) and retried with backoff on 429/5xx.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import PATHS, env, require_env

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

PROVIDERS = {
    # provider: (base_url, env var holding the key, supports json_object response_format)
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", True),
    "openai": (None, "OPENAI_API_KEY", True),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", True),
    "ollama": (env("OLLAMA_BASE_URL", "http://localhost:11434/v1"), None, True),
    "anthropic": (None, "ANTHROPIC_API_KEY", False),
}


@dataclass
class Completion:
    text: str
    data: dict | None
    cached: bool
    latency: float
    usage: dict
    error: str | None = None


class DailyQuotaExhausted(RuntimeError):
    """The provider's daily request quota is used up; the run must stop and resume later (cache keeps progress)."""


class RateLimiter:
    def __init__(self, rpm: int):
        self.min_interval = 60.0 / max(rpm, 1)
        self.last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = self.min_interval - (now - self.last)
        if delta > 0:
            time.sleep(delta)
        self.last = time.monotonic()


def parse_json_object(text: str) -> dict:
    """Tolerant JSON extraction: strips fences and leading/trailing prose around the first {...}."""
    s = _FENCE.sub("", text.strip())
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(s[start:end + 1])


class LLMClient:
    def __init__(self, model_spec: str, rpm: int = 8, temperature: float = 0.1, max_tokens: int = 4096,
                 cache_dir: Path | None = None):
        if "/" not in model_spec:
            raise ValueError(f"llmModel must be provider/model, got {model_spec!r}")
        self.provider, self.model = model_spec.split("/", 1)
        if self.provider not in PROVIDERS:
            raise ValueError(f"unknown provider {self.provider!r}; known: {sorted(PROVIDERS)}")
        self.temperature, self.max_tokens = temperature, max_tokens
        self.limiter = RateLimiter(rpm)
        self.cache_dir = (cache_dir or PATHS.llm_cache) / self.provider / self.model.replace(":", "_")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = None

    # ------------------------------------------------------------------ transport
    def _openai(self):
        if self._client is None:
            from openai import OpenAI
            base_url, key_var, _ = PROVIDERS[self.provider]
            api_key = require_env(key_var) if key_var else "ollama"
            self._client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0,
                                  timeout=float(env("LLM_TIMEOUT_SECONDS", "120")))
        return self._client

    def _call(self, system: str, user: str, json_mode: bool) -> tuple[str, dict]:
        if self.provider == "anthropic":
            import anthropic  # optional dependency
            client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
            msg = client.messages.create(model=self.model, max_tokens=self.max_tokens, temperature=self.temperature,
                                         system=system, messages=[{"role": "user", "content": user}])
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            return text, {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
        kwargs = {}
        if json_mode and PROVIDERS[self.provider][2]:
            kwargs["response_format"] = {"type": "json_object"}
        if self.provider == "gemini":
            # extraction needs no chain-of-thought; low effort cuts latency and output tokens
            kwargs["reasoning_effort"] = env("GEMINI_REASONING_EFFORT", "low")
        resp = self._openai().chat.completions.create(
            model=self.model, temperature=self.temperature, max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **kwargs)
        text = resp.choices[0].message.content or ""
        usage = {"input": getattr(resp.usage, "prompt_tokens", 0), "output": getattr(resp.usage, "completion_tokens", 0)}
        return text, usage

    # ------------------------------------------------------------------ public API
    def cache_key(self, system: str, user: str) -> str:
        h = hashlib.sha256()
        for part in (self.provider, self.model, str(self.temperature), system, "\x00", user):
            h.update(part.encode("utf-8"))
        return h.hexdigest()

    def credentials_available(self) -> bool:
        """False when the provider needs an API key that is not set (cache-only reproduction)."""
        key_var = PROVIDERS[self.provider][1]
        return key_var is None or bool(env(key_var))

    def complete_json(self, system: str, user: str, retries: int = 6) -> Completion:
        key = self.cache_key(system, user)
        cached = self.cache_dir / f"{key}.json"
        if cached.exists():
            c = json.loads(cached.read_text(encoding="utf-8"))
            data = None
            try:
                data = parse_json_object(c["text"])
            except (json.JSONDecodeError, ValueError):
                pass
            return Completion(c["text"], data, True, 0.0, c.get("usage", {}), c.get("error"))
        if not self.credentials_available():
            # Cache-only reproduction (no key): record the miss as an LLM error on this chunk instead of
            # aborting the run, so that the rest of the corpus is still rebuilt from the cache.
            msg = f"cache miss and {PROVIDERS[self.provider][1]} not set (cache-only run)"
            print(f"[llm] {msg}", file=sys.stderr, flush=True)
            return Completion("", None, False, 0.0, {}, msg)
        delay = 10.0
        for attempt in range(retries):
            self.limiter.wait()
            t0 = time.perf_counter()
            try:
                text, usage = self._call(system, user, json_mode=True)
            except Exception as e:  # provider errors: rate limit, overload, transient network
                status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
                msg = str(e)
                if status == 429 and ("per day" in msg.lower() or "retry in" in msg.lower() and "h" in msg.split("retry in")[-1][:12]
                                      or "_requests, limit" in msg):
                    raise DailyQuotaExhausted(msg[:400])
                transient = status in (408, 409, 429, 500, 502, 503, 504) or status is None
                if attempt == retries - 1 or not transient:
                    return Completion("", None, False, time.perf_counter() - t0, {}, f"{type(e).__name__}: {msg[:300]}")
                print(f"[llm] {type(e).__name__} (status {status}); retry {attempt + 1}/{retries} in {delay:.0f}s", file=sys.stderr, flush=True)
                time.sleep(delay)
                delay = min(delay * 2, 120.0)
                continue
            latency = time.perf_counter() - t0
            error = None
            data = None
            try:
                data = parse_json_object(text)
            except (json.JSONDecodeError, ValueError) as e:
                error = f"unparseable JSON: {e}"
            cached.write_text(json.dumps({"text": text, "usage": usage, "error": error, "model": self.model,
                                          "provider": self.provider, "latency": latency}, ensure_ascii=False),
                              encoding="utf-8")
            return Completion(text, data, False, latency, usage, error)
        return Completion("", None, False, 0.0, {}, "exhausted retries")
