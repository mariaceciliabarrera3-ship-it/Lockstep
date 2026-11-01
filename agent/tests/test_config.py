import json
import os
import tempfile
import unittest

from core.config import ConfigError, check_independence, load_config


def good():
    return {
        "nebius": {"base_url": "https://example.test/v1/"},
        "models": {"classifier": "m-nano", "architect": "m-super", "judge": "m-ultra"},
    }


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, data, raw=None):
        path = os.path.join(self._tmp.name, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(raw if raw is not None else json.dumps(data))
        return path

    def test_load_valid_config(self):
        cfg = load_config(self.write(good()))
        self.assertEqual(cfg["models"]["judge"], "m-ultra")

    def test_missing_file_raises(self):
        with self.assertRaises(ConfigError):
            load_config(os.path.join(self._tmp.name, "nope.json"))

    def test_invalid_json_raises(self):
        with self.assertRaises(ConfigError):
            load_config(self.write(None, raw="{not json"))

    def test_missing_required_role_raises(self):
        cfg = good()
        del cfg["models"]["judge"]
        with self.assertRaises(ConfigError):
            load_config(self.write(cfg))

    def test_missing_base_url_raises(self):
        cfg = good()
        del cfg["nebius"]["base_url"]
        with self.assertRaises(ConfigError):
            load_config(self.write(cfg))

    def test_placeholder_model_is_rejected(self):
        cfg = good()
        cfg["models"]["architect"] = "FILL_FROM_list_models"
        with self.assertRaises(ConfigError):
            load_config(self.write(cfg))

    def test_independent_models_pass(self):
        check_independence(good())  # must not raise

    def test_architect_equals_judge_raises(self):
        cfg = good()
        cfg["models"]["architect"] = cfg["models"]["judge"]
        with self.assertRaises(ConfigError):
            check_independence(cfg)

    def test_programmer_equals_judge_raises(self):
        cfg = good()
        cfg["models"]["programmer"] = cfg["models"]["judge"]
        with self.assertRaises(ConfigError):
            check_independence(cfg)

    def test_programmer_is_optional(self):
        check_independence(good())  # no "programmer" role: must not raise

    def test_startup_fails_when_models_are_not_independent(self):
        cfg = good()
        cfg["models"]["architect"] = cfg["models"]["judge"]
        with self.assertRaises(ConfigError):
            load_config(self.write(cfg))


if __name__ == "__main__":
    unittest.main()
