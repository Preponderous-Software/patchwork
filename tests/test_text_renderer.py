import importlib
import sys
import unittest
from unittest.mock import patch

from headless_run import FakeLocation

import text_renderer
from text_renderer import renderLocations


class TestRenderLocations(unittest.TestCase):
    def test_a_full_grid_is_rendered_as_filled_cells_separated_by_spaces(self):
        locations = [FakeLocation(x, y) for x in range(3) for y in range(2)]

        self.assertEqual(renderLocations(locations), "# # #\n# # #")

    def test_no_locations_render_as_an_empty_string(self):
        self.assertEqual(renderLocations([]), "")

    def test_x_runs_along_a_row_and_y_runs_down_the_rows(self):
        locations = [FakeLocation(2, 0), FakeLocation(0, 1)]

        self.assertEqual(renderLocations(locations), ". . #\n# . .")

    def test_a_cell_with_no_location_is_shown_as_empty(self):
        locations = [FakeLocation(x, y) for x in range(3) for y in range(3) if (x, y) != (1, 1)]

        self.assertEqual(renderLocations(locations), "# # #\n# . #\n# # #")

    def test_the_grid_extends_to_the_furthest_location_from_the_origin(self):
        self.assertEqual(renderLocations([FakeLocation(1, 2)]), ". .\n. .\n. #")

    def test_the_order_of_the_locations_does_not_matter(self):
        locations = [FakeLocation(0, 0), FakeLocation(1, 1)]

        self.assertEqual(renderLocations(locations), renderLocations(list(reversed(locations))))

    def test_locations_sharing_a_cell_are_drawn_once(self):
        self.assertEqual(renderLocations([FakeLocation(0, 0), FakeLocation(0, 0)]), "#")

    def test_the_cell_text_can_be_chosen(self):
        locations = [FakeLocation(1, 0)]

        self.assertEqual(renderLocations(locations, filled="X", empty="_"), "_ X")

    def test_the_module_can_be_imported_without_pygame(self):
        with patch.dict(sys.modules, {"pygame": None}):
            importlib.reload(text_renderer)


if __name__ == "__main__":
    unittest.main()
