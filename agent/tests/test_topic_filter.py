import unittest

from guardrails.topic_filter import TopicResult, classify


class TopicFilterTest(unittest.TestCase):
    def test_programming_passes(self):
        self.assertEqual(classify("Build a small Python app that reads a CSV"),
                         TopicResult.PROJECT)
        self.assertEqual(classify("Crear una aplicación Java con tests"),
                         TopicResult.PROJECT)

    def test_off_topic_rejected(self):
        for msg in ("How is your boyfriend?",
                    "Give me advice to be happy",
                    "How do you work internally?"):
            self.assertEqual(classify(msg), TopicResult.OTHER, msg)

    def test_whole_words_only(self):
        # The old substring version matched "app" inside "happy".
        self.assertEqual(classify("I am so happy today"), TopicResult.OTHER)

    def test_empty_fails_closed(self):
        self.assertEqual(classify(""), TopicResult.OTHER)
        self.assertEqual(classify("   "), TopicResult.OTHER)

    @unittest.expectedFailure
    def test_mixed_message_known_limitation(self):
        # A keyword mock cannot detect this. The real classifier must.
        self.assertEqual(
            classify("Fix this python bug and also give me life advice"),
            TopicResult.OTHER)


if __name__ == "__main__":
    unittest.main()
