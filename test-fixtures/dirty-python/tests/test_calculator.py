import unittest

from src.calculator import multiply


class CalculatorTests(unittest.TestCase):
    def test_multiply(self) -> None:
        self.assertEqual(multiply(3, 4), 12)


if __name__ == "__main__":
    unittest.main()
