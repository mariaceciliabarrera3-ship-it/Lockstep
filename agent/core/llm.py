import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class LLMError(Exception):
    pass


@dataclass
class LLMResponse:
    content: str
    total_tokens: int
    model: str


def _default_post(url, headers, body, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:300]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


class NebiusClient:
    def __init__(self, base_url, api_key, post=None, timeout=60,
                 max_retries=2, sleep=time.sleep):
        if not api_key:
            raise LLMError("Missing API key")
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._post = post or _default_post
        self._timeout = timeout
        self._retries = max_retries
        self._sleep = sleep

    def _safe(self, text):
        return str(text).replace(self._key, "***")

    def chat(self, model, messages, max_tokens=1024, temperature=0.0, extra=None):
        url = f"{self._base}/chat/completions"
        headers = {"Authorization": f"Bearer {self._key}",
                   "Content-Type": "application/json"}
        body = {"model": model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature}
        for key, value in (extra or {}).items():
            if key not in ("model", "messages", "max_tokens", "temperature"):
                body[key] = value
        last = None
        for attempt in range(self._retries + 1):
            try:
                data = self._post(url, headers, body, self._timeout)
                break
            except Exception as exc:
                last = exc
                if attempt < self._retries:
                    self._sleep(2 ** attempt)
        else:
            raise LLMError(f"Request failed after retries: {self._safe(last)}")
        try:
            content = data["choices"][0]["message"].get("content") or ""
            tokens = int(data.get("usage", {}).get("total_tokens", 0))
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMError(f"Malformed response: {exc}")
        return LLMResponse(content=content, total_tokens=tokens, model=model)


def make_llm_call(client, model, max_tokens=1024, extra=None):
    def llm_call(prompt):
        reply = client.chat(model, [{"role": "user", "content": prompt}],
                            max_tokens=max_tokens, temperature=0.0, extra=extra)
        return reply.content
    return llm_call
