import os
import unittest
from unittest.mock import patch

import headless_run

headless_run.installVironStubs()

import main
import render_window


class TestFakeServices(unittest.TestCase):
    def test_created_environments_can_be_loaded_by_id(self):
        environmentService = headless_run.FakeEnvironmentService()

        environment = environmentService.create_environment("Test", 1, 4)

        self.assertIs(environmentService.get_environment_by_id(environment.getEnvironmentId()), environment)

    def test_loading_an_unknown_environment_raises(self):
        environmentService = headless_run.FakeEnvironmentService()

        with self.assertRaises(KeyError):
            environmentService.get_environment_by_id(99)

    def test_one_location_is_returned_per_grid_cell(self):
        environmentService = headless_run.FakeEnvironmentService()
        locationService = headless_run.FakeLocationService(environmentService)
        environment = environmentService.create_environment("Test", 1, 3)

        locations = locationService.get_locations_in_environment(environment.getEnvironmentId())

        self.assertEqual(sorted((location.get_x(), location.get_y()) for location in locations),
                         [(x, y) for x in range(3) for y in range(3)])


class TestRun(unittest.TestCase):
    """
    Runs the harness end to end against the real pygame, RenderWindow and Graphik, rendering
    to SDL's dummy drivers, so that the smoke test itself is kept working.
    """

    def setUp(self):
        environment = patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
        environment.start()
        self.addCleanup(environment.stop)

    def test_every_scenario_passes_against_the_current_main(self):
        self.assertTrue(headless_run.run(gridSize=3, frames=2))

    def test_a_failing_render_loop_is_reported_as_a_failure(self):
        with patch.object(main, "drawEnvironment", side_effect=RuntimeError("render failed")):
            self.assertFalse(headless_run.run(gridSize=3, frames=2))

    def test_a_render_loop_that_stops_ticking_fails_instead_of_hanging(self):
        class NonTickingWindow(render_window.RenderWindow):
            def tick(self, fps):
                pass

        with patch.object(main, "RenderWindow", NonTickingWindow):
            self.assertFalse(headless_run.run(gridSize=3, frames=2))

    def test_the_repository_working_directory_is_left_untouched(self):
        before = os.getcwd()
        entries = sorted(os.listdir(before))

        headless_run.run(gridSize=3, frames=2)

        self.assertEqual(os.getcwd(), before)
        self.assertEqual(sorted(os.listdir(before)), entries)
