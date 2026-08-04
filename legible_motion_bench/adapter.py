"""Talking to a model, and recording exactly which one answered.

Two backends cover everything used here: an OpenAI compatible chat endpoint,
which serves both the hosted models and a local Ollama, and the Gemini
generateContent endpoint. Both go through the standard library, because a
benchmark that a reviewer has to install an HTTP client to read is worse
than one that spells out its request.

Keys are read from the environment and never from a file. The runtime
config names the environment variable; it does not hold the key, which is
why the config with real entries is untracked and only an example is
committed.

Every alias must agree with the committed manifest before a request is
made. That check exists because the alias is what ends up in a table
column, and an alias that quietly pointed at a different checkpoint would
put the wrong model's name above the right model's numbers.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "configs" / "model_manifest.json"
DEFAULT_TIMEOUT = 180

# The standard library sends "Python-urllib/x.y" by default, which at
# least one provider's front end rejects outright with a 403 before the
# request reaches the API. This says what the client actually is, which is
# what a user agent is for.
USER_AGENT = "legible-motion-bench/0.0.1"


class AdapterError(RuntimeError):
    """Raised when a model cannot be reached or is configured inconsistently."""


@dataclass(frozen=True)
class ScriptedModel:
    """A model whose replies are fixed in advance, for tests.

    Nothing in the runner knows the difference, which is the point: the
    resume guard, the record format and the extraction path are all
    exercised without a network or a quota.
    """

    alias: str
    api_model: str
    replies: dict = field(default_factory=dict)
    default: str = ""
    calls: list = field(default_factory=list)

    def complete(self, prompt: str, scenario_id: str) -> str:
        self.calls.append(scenario_id)
        return self.replies.get(scenario_id, self.default)


@dataclass(frozen=True)
class RemoteModel:
    alias: str
    api_model: str
    backend: str
    base_url: str
    api_key_env: str | None = None
    temperature: float | None = 0.0
    max_tokens: int = 2000
    timeout: int = DEFAULT_TIMEOUT
    retries: int = 6

    def _key(self) -> str:
        if not self.api_key_env:
            return ""
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise AdapterError(
                f"model {self.alias!r} needs {self.api_key_env} in the "
                f"environment and it is not set"
            )
        return key

    def complete(self, prompt: str, scenario_id: str) -> str:
        if self.backend == "openai_chat":
            return self._openai_chat(prompt)
        if self.backend == "gemini":
            return self._gemini(prompt)
        raise AdapterError(f"unknown backend {self.backend!r} for {self.alias!r}")

    def _post(self, url: str, payload: dict, headers: dict) -> dict:
        headers = {"User-Agent": USER_AGENT, **headers}
        body = json.dumps(payload).encode("utf-8")
        for attempt in range(self.retries + 1):
            request = urllib.request.Request(
                url, data=body, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                # A 429 is the provider saying "not yet", not "no". Waiting
                # and asking again is not a retry of a bad answer, because
                # no answer was produced; the model never saw the prompt.
                # Retrying a reply we did not like would be a different
                # thing entirely and nothing here does it.
                if exc.code == 429 and attempt < self.retries:
                    time.sleep(self._retry_after(exc, attempt))
                    continue
                raise AdapterError(
                    f"{self.alias}: HTTP {exc.code} from {url}: {detail}"
                ) from exc
            except urllib.error.URLError as exc:
                raise AdapterError(
                    f"{self.alias}: could not reach {url}: {exc}"
                ) from exc
        raise AdapterError(f"{self.alias}: gave up after {self.retries} retries")

    def _retry_after(self, exc, attempt: int) -> float:
        """How long to wait, preferring what the provider asked for."""
        header = exc.headers.get("retry-after") if exc.headers else None
        if header:
            try:
                return min(float(header) + 0.5, 90.0)
            except ValueError:
                pass
        return min(2.0 * (2**attempt), 60.0)

    def _openai_chat(self, prompt: str) -> str:
        payload = {
            "model": self.api_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        headers = {"Content-Type": "application/json"}
        key = self._key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        document = self._post(
            f"{self.base_url.rstrip('/')}/chat/completions", payload, headers
        )
        try:
            return document["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(
                f"{self.alias}: unexpected response shape: {str(document)[:300]}"
            ) from exc

    def _gemini(self, prompt: str) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": self.max_tokens},
        }
        if self.temperature is not None:
            payload["generationConfig"]["temperature"] = self.temperature
        url = (
            f"{self.base_url.rstrip('/')}/{self.api_model}:generateContent"
            f"?key={self._key()}"
        )
        document = self._post(url, payload, {"Content-Type": "application/json"})
        try:
            parts = document["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(
                f"{self.alias}: unexpected response shape: {str(document)[:300]}"
            ) from exc


def load_manifest(path=MANIFEST_PATH) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        document = json.load(handle)
    return {k: v for k, v in document.items() if not k.startswith("_")}


def build(entry: dict, manifest: dict | None = None) -> RemoteModel:
    """Build one model from a runtime config entry, checked against the manifest."""
    manifest = load_manifest() if manifest is None else manifest
    alias = entry.get("name")
    if alias not in manifest:
        raise AdapterError(
            f"alias {alias!r} is not in the committed manifest; add it there "
            f"before running, so the table column and the checkpoint agree"
        )
    declared = manifest[alias]["api_model"]
    if entry.get("model") != declared:
        raise AdapterError(
            f"alias {alias!r} runs {entry.get('model')!r} but the manifest "
            f"records {declared!r}; one of the two is wrong and a record "
            f"written now would name the wrong checkpoint"
        )
    return RemoteModel(
        alias=alias,
        api_model=declared,
        backend=entry["backend"],
        base_url=entry["base_url"],
        api_key_env=entry.get("api_key_env"),
        temperature=entry.get("temperature", 0.0),
        max_tokens=entry.get("max_tokens", 2000),
    )


def load_models(config_path, manifest=None) -> tuple[RemoteModel, ...]:
    with Path(config_path).open(encoding="utf-8") as handle:
        entries = json.load(handle)
    manifest = load_manifest() if manifest is None else manifest
    return tuple(build(entry, manifest) for entry in entries)
