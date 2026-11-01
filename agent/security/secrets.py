import os
import re
from getpass import getpass
from typing import Callable

# Values shorter than this are not redacted (they would corrupt normal text).
MIN_SECRET_LEN = 6


class SecretManager:
    """
    Holds secret values. The language models only ever see the NAMES.
    Values must never reach prompts or saved state.
    """

    def __init__(self, prompt: Callable[[str], str] = getpass):
        self._secrets: dict = {}
        self._prompt = prompt

    def set(self, name: str, value: str) -> None:
        if value:
            self._secrets[name] = value

    def load_from_environment(self, name: str) -> bool:
        value = os.getenv(name)
        if value:
            self._secrets[name] = value
            return True
        return False

    def request_hidden(self, name: str) -> bool:
        value = self._prompt(f"Enter value for {name} (hidden): ")
        if not value:
            return False
        self._secrets[name] = value
        return True

    def env_for_stage(self, required_names: list) -> dict:
        """Only the secrets a Stage declared. Meant for the Executor only."""
        missing = [n for n in required_names if n not in self._secrets]
        if missing:
            raise KeyError(f"Secrets not available: {', '.join(missing)}")
        return {n: self._secrets[n] for n in required_names}

    def redact(self, text: str) -> str:
        if not text:
            return text
        result = text
        for value in sorted(self._secrets.values(), key=len, reverse=True):
            if len(value) >= MIN_SECRET_LEN:
                result = result.replace(value, "***")
        result = re.sub(
            r"(api[_-]?key\s*[:=]\s*)[^\s,]+",
            r"\1***",
            result,
            flags=re.IGNORECASE,
        )
        return result

    def names(self) -> list:
        return list(self._secrets.keys())
