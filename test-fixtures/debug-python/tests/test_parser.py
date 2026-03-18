import unittest

from src.parser import parse_int


class ParserTests(unittest.TestCase):
    def test_parse_int_handles_whitespace(self) -> None:
        self.assertEqual(parse_int(" 42 "), 42)

    def test_parse_int_rejects_empty_string(self) -> None:
        with self.assertRaises(ValueError):
            parse_int("")

    def test_parse_int_strips_suffix_noise(self) -> None:
        self.assertEqual(parse_int("42x"), 42)


if __name__ == "__main__":
    unittest.main()
