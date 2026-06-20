import unittest

import app


class HelperTests(unittest.TestCase):
    def test_sanitize_filename_removes_path_separators(self):
        self.assertEqual(app._sanitize_filename("../test\\file.pdf"), ".._test_file.pdf")

    def test_sanitize_filename_keeps_slovenian_letters(self):
        self.assertEqual(app._sanitize_filename("ČŠŽ čšž.pdf"), "ČŠŽ čšž.pdf")

    def test_sanitize_filename_never_returns_empty(self):
        self.assertEqual(app._sanitize_filename("////"), "____")
        self.assertEqual(app._sanitize_filename(""), "fajl")

    def test_sanitize_filename_truncates_long_names(self):
        self.assertEqual(len(app._sanitize_filename("a" * 300)), 180)


if __name__ == "__main__":
    unittest.main()
