
import unittest

from var_validation import kupiec_pof_test


class TestKupiecPOF(unittest.TestCase):

    def test_existing_backtest(self):
        result = kupiec_pof_test(
            exceptions=11,
            observations=189,
            confidence=0.95,
        )

        self.assertEqual(result["Observations"], 189)
        self.assertEqual(result["Exceptions"], 11)
        self.assertAlmostEqual(
            result["Observed Exception Rate"],
            11 / 189,
        )
        self.assertGreaterEqual(result["P-Value"], 0)
        self.assertLessEqual(result["P-Value"], 1)

    def test_expected_exception_rate(self):
        result = kupiec_pof_test(5, 100, 0.95)

        self.assertAlmostEqual(
            result["Expected Exception Rate"], 0.05
        )
        self.assertAlmostEqual(
            result["Kupiec LR Statistic"], 0.0, places=8
        )
        self.assertFalse(result["Reject at 5%"])

    def test_excessive_exceptions(self):
        result = kupiec_pof_test(30, 100, 0.95)

        self.assertTrue(result["Reject at 5%"])
        self.assertLess(result["P-Value"], 0.05)

    def test_zero_exceptions(self):
        result = kupiec_pof_test(0, 100, 0.95)

        self.assertGreaterEqual(
            result["Kupiec LR Statistic"], 0
        )

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            kupiec_pof_test(11, 0)

        with self.assertRaises(ValueError):
            kupiec_pof_test(101, 100)

        with self.assertRaises(ValueError):
            kupiec_pof_test(5, 100, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
