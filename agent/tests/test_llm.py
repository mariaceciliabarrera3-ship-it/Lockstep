import unittest

from core.llm import LLMError, NebiusClient

KEY = "sk-secret-123456"
BASE = "https://example.test/v1/"
OK = {"choices": [{"message": {"content": "hello"}}],
      "usage": {"total_tokens": 42}}


class FakePost:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def client(post, **kw):
    return NebiusClient(BASE, KEY, post=post, sleep=lambda s: None, **kw)


class NebiusClientTest(unittest.TestCase):
    def test_returns_content_and_tokens(self):
        r = client(FakePost([OK])).chat("m", [{"role": "user", "content": "hi"}])
        self.assertEqual(r.content, "hello")
        self.assertEqual(r.total_tokens, 42)
        self.assertEqual(r.model, "m")

    def test_url_headers_and_body(self):
        post = FakePost([OK])
        client(post).chat("m", [{"role": "user", "content": "hi"}],
                          max_tokens=77, temperature=0.0)
        url, headers, body, _timeout = post.calls[0]
        self.assertEqual(url, "https://example.test/v1/chat/completions")
        self.assertEqual(headers["Authorization"], f"Bearer {KEY}")
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(body["max_tokens"], 77)
        self.assertEqual(body["temperature"], 0.0)

    def test_none_content_becomes_empty_string(self):
        data = {"choices": [{"message": {"content": None}}],
                "usage": {"total_tokens": 5}}
        self.assertEqual(client(FakePost([data])).chat("m", []).content, "")

    def test_retries_then_succeeds(self):
        post = FakePost([Exception("boom"), Exception("boom"), OK])
        self.assertEqual(client(post).chat("m", []).content, "hello")
        self.assertEqual(len(post.calls), 3)

    def test_gives_up_after_two_retries(self):
        post = FakePost([Exception("boom")] * 3)
        with self.assertRaises(LLMError):
            client(post).chat("m", [])
        self.assertEqual(len(post.calls), 3)

    def test_error_message_never_contains_the_api_key(self):
        post = FakePost([Exception(f"401 for key {KEY}")] * 3)
        with self.assertRaises(LLMError) as ctx:
            client(post).chat("m", [])
        self.assertNotIn(KEY, str(ctx.exception))

    def test_malformed_response_is_not_retried(self):
        post = FakePost([{"oops": 1}])
        with self.assertRaises(LLMError):
            client(post).chat("m", [])
        self.assertEqual(len(post.calls), 1)

    def test_missing_api_key_raises(self):
        with self.assertRaises(LLMError):
            NebiusClient(BASE, "")


if __name__ == "__main__":
    unittest.main()
