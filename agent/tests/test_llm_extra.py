import unittest

from core.llm import NebiusClient

OK = {"choices": [{"message": {"content": "x"}}], "usage": {"total_tokens": 1}}


class RecordingPost:
    def __init__(self):
        self.bodies = []

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        return OK


def make(post):
    return NebiusClient("https://example.test/v1/", "sk-test-123456",
                        post=post, sleep=lambda s: None)


class ExtraOptionsTest(unittest.TestCase):
    def test_extra_is_added_to_the_request_body(self):
        post = RecordingPost()
        make(post).chat("m", [], extra={"chat_template_kwargs": {"enable_thinking": False}})
        self.assertEqual(post.bodies[0]["chat_template_kwargs"], {"enable_thinking": False})

    def test_extra_cannot_override_protected_fields(self):
        post = RecordingPost()
        make(post).chat("m", [{"role": "user", "content": "hi"}], max_tokens=50,
                        temperature=0.0,
                        extra={"model": "evil", "messages": [], "max_tokens": 1,
                               "temperature": 2.0})
        body = post.bodies[0]
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(body["max_tokens"], 50)
        self.assertEqual(body["temperature"], 0.0)

    def test_without_extra_nothing_changes(self):
        post = RecordingPost()
        make(post).chat("m", [])
        self.assertEqual(set(post.bodies[0]), {"model", "messages", "max_tokens", "temperature"})


if __name__ == "__main__":
    unittest.main()
