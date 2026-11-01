import unittest

from profiles.registry import command_for


class ProfileCommandsTest(unittest.TestCase):
    def test_python_test_command_runs_unittest(self):
        cmd = command_for("python", "test")
        self.assertIsInstance(cmd, list)
        self.assertIn("unittest", cmd)

    def test_python_lint_command_exists(self):
        self.assertIsInstance(command_for("python", "lint"), list)

    def test_java_commands_use_maven(self):
        self.assertEqual(command_for("java", "test")[0], "mvn")
        self.assertEqual(command_for("java", "build")[0], "mvn")

    def test_profile_name_is_case_insensitive(self):
        self.assertEqual(command_for("PYTHON", "test"), command_for("python", "test"))

    def test_unknown_action_or_profile_raises(self):
        for profile, action in (("python", "deploy"), ("cobol", "test"), ("java", "lint")):
            with self.subTest((profile, action)):
                with self.assertRaises(ValueError):
                    command_for(profile, action)

    def test_returned_command_is_a_copy(self):
        cmd = command_for("python", "test")
        cmd.append("--evil")
        self.assertNotIn("--evil", command_for("python", "test"))


if __name__ == "__main__":
    unittest.main()
