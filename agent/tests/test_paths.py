import os
import tempfile
import unittest

from sandbox.paths import PathEscapeError, is_inside, resolve_inside


class PathsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self._tmp.name, "project")
        os.makedirs(os.path.join(self.root, "src"))
        self.outside = os.path.join(self._tmp.name, "outside")
        os.makedirs(self.outside)

    def tearDown(self):
        self._tmp.cleanup()

    def test_normal_relative_paths_are_accepted(self):
        expected = os.path.join(os.path.realpath(self.root), "src", "app.py")
        self.assertEqual(resolve_inside(self.root, "src/app.py"), expected)

    def test_a_new_file_in_a_new_subfolder_is_accepted(self):
        self.assertTrue(resolve_inside(self.root, "new/deep/file.txt").endswith("file.txt"))

    def test_parent_traversal_is_rejected(self):
        for bad in ("../outside/x.txt", "src/../../outside/x.txt", ".."):
            with self.subTest(bad):
                with self.assertRaises(PathEscapeError):
                    resolve_inside(self.root, bad)

    def test_absolute_paths_are_rejected(self):
        with self.assertRaises(PathEscapeError):
            resolve_inside(self.root, os.path.join(self.outside, "x.txt"))

    def test_a_symlink_pointing_outside_is_rejected(self):
        os.symlink(self.outside, os.path.join(self.root, "link"))
        with self.assertRaises(PathEscapeError):
            resolve_inside(self.root, "link/secret.txt")

    def test_is_inside(self):
        self.assertTrue(is_inside(self.root, os.path.join(self.root, "src")))
        self.assertFalse(is_inside(self.root, self.outside))


if __name__ == "__main__":
    unittest.main()
