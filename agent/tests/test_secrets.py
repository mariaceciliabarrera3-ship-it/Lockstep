import os
import unittest
from unittest import mock

from security.secrets import SecretManager


class SecretsTest(unittest.TestCase):
    def test_redacts_known_value(self):
        s = SecretManager()
        s.set("TAVILY_API_KEY", "tvly-SECRET-12345")
        out = s.redact("the key is tvly-SECRET-12345 ok")
        self.assertNotIn("tvly-SECRET-12345", out)
        self.assertIn("***", out)

    def test_short_values_are_not_redacted(self):
        s = SecretManager()
        s.set("X", "1")
        self.assertEqual(s.redact("version 1.0"), "version 1.0")

    def test_redacts_api_key_pattern(self):
        out = SecretManager().redact("api_key=abc123def")
        self.assertNotIn("abc123def", out)

    def test_env_for_stage_returns_only_requested(self):
        s = SecretManager()
        s.set("A_KEY", "value-aaaaaa")
        s.set("B_KEY", "value-bbbbbb")
        self.assertEqual(s.env_for_stage(["A_KEY"]), {"A_KEY": "value-aaaaaa"})

    def test_missing_secret_raises(self):
        with self.assertRaises(KeyError):
            SecretManager().env_for_stage(["NOPE"])

    def test_load_from_environment(self):
        with mock.patch.dict(os.environ, {"MY_KEY": "value-123456"}):
            s = SecretManager()
            self.assertTrue(s.load_from_environment("MY_KEY"))
            self.assertEqual(s.names(), ["MY_KEY"])

    def test_hidden_prompt_is_used(self):
        s = SecretManager(prompt=lambda _msg: "typed-secret-1")
        self.assertTrue(s.request_hidden("K"))
        self.assertEqual(s.env_for_stage(["K"]), {"K": "typed-secret-1"})


if __name__ == "__main__":
    unittest.main()
