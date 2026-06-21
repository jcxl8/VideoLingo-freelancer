import tempfile
import unittest
from pathlib import Path


class StructuredCellsTest(unittest.TestCase):
    def test_parse_list_cell_accepts_literal_and_existing_list(self):
        from core.utils.structured_cells import parse_list_cell

        self.assertEqual(parse_list_cell('["hello", "world"]', field="lines"), ["hello", "world"])
        self.assertEqual(parse_list_cell(["hello"], field="lines"), ["hello"])

    def test_parse_list_cell_rejects_wrong_type_with_location(self):
        from core.utils.structured_cells import parse_list_cell

        with self.assertRaisesRegex(ValueError, "lines at row 7 must be a list"):
            parse_list_cell('{"text": "hello"}', field="lines", row=7)

    def test_parse_list_cell_does_not_execute_expression(self):
        from core.utils.structured_cells import parse_list_cell

        with tempfile.TemporaryDirectory() as tmpdir:
            marker = Path(tmpdir) / "forbidden"
            payload = f"__import__('pathlib').Path({str(marker)!r}).touch()"

            with self.assertRaisesRegex(ValueError, "lines at row 2 contains an invalid literal"):
                parse_list_cell(payload, field="lines", row=2)

            self.assertFalse(marker.exists())

    def test_parse_time_ranges_validates_shape_numbers_and_order(self):
        from core.utils.structured_cells import parse_time_ranges_cell

        self.assertEqual(
            parse_time_ranges_cell("[[0, 1.5], [2, 3]]", row=4),
            [[0.0, 1.5], [2.0, 3.0]],
        )
        for invalid in ("[[0]]", "[['zero', 1]]", "[[2, 1]]"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    parse_time_ranges_cell(invalid, row=4)


if __name__ == "__main__":
    unittest.main()
