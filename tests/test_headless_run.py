import contextlib
import io
import os
import runpy
import sys
import unittest
from unittest.mock import MagicMock, patch

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


class TestInstallVironStubs(unittest.TestCase):
    servicesPath = "Viron.src.main.python.preponderous.viron.services"

    def test_both_service_classes_are_importable_once_installed(self):
        vironModules = [name for name in sys.modules if name == "Viron" or name.startswith("Viron.")]

        with patch.dict(sys.modules):
            for name in vironModules:
                del sys.modules[name]

            headless_run.installVironStubs()

            self.assertTrue(hasattr(sys.modules[self.servicesPath + ".environmentService"], "EnvironmentService"))
            self.assertTrue(hasattr(sys.modules[self.servicesPath + ".locationService"], "LocationService"))

    def test_modules_that_are_already_registered_are_not_replaced(self):
        existing = MagicMock(name="existing environmentService module")

        with patch.dict(sys.modules, {self.servicesPath + ".environmentService": existing}):
            headless_run.installVironStubs()

            self.assertIs(sys.modules[self.servicesPath + ".environmentService"], existing)


class TestFrameCounter(unittest.TestCase):
    def setUp(self):
        self.pygame = MagicMock(name="pygame")
        self.window = MagicMock(name="window")
        self.tick = MagicMock(name="tick")

    def test_quit_is_posted_once_when_the_requested_frames_have_been_ticked(self):
        counter = headless_run.FrameCounter(self.pygame, 3)
        countingTick = counter.wrapTick(self.tick)

        for _ in range(2):
            countingTick(self.window, 60)
        self.pygame.event.post.assert_not_called()
        countingTick(self.window, 60)
        countingTick(self.window, 60)

        self.assertEqual(counter.count, 4)
        self.pygame.event.Event.assert_called_once_with(self.pygame.QUIT)
        self.pygame.event.post.assert_called_once_with(self.pygame.event.Event.return_value)

    def test_the_wrapped_tick_is_called_with_the_window_and_frame_rate(self):
        counter = headless_run.FrameCounter(self.pygame, 3)

        counter.wrapTick(self.tick)(self.window, 60)

        self.tick.assert_called_once_with(self.window, 60)

    def test_the_window_is_closed_once_the_loop_runs_one_iteration_past_the_requested_frames(self):
        counter = headless_run.FrameCounter(self.pygame, 2)
        shouldContinue = MagicMock(name="should_continue", return_value=True)
        countingShouldContinue = counter.wrapShouldContinue(shouldContinue)

        for _ in range(3):
            self.assertTrue(countingShouldContinue(self.window))
        self.window.close.assert_not_called()
        countingShouldContinue(self.window)

        self.window.close.assert_called_once_with()
        self.assertEqual(shouldContinue.call_count, 4)

    def test_no_frame_rate_is_measured_below_two_frames(self):
        counter = headless_run.FrameCounter(self.pygame, 5)
        self.assertIsNone(counter.framesPerSecond())

        counter.wrapTick(self.tick)(self.window, 60)

        self.assertIsNone(counter.framesPerSecond())

    def test_the_frame_rate_is_measured_between_the_first_and_last_ticks(self):
        counter = headless_run.FrameCounter(self.pygame, 5)
        countingTick = counter.wrapTick(self.tick)

        with patch.object(headless_run.time, "perf_counter", side_effect=[10.0, 10.5, 11.0]):
            for _ in range(3):
                countingTick(self.window, 60)

        self.assertEqual(counter.framesPerSecond(), 2.0)


class TestCommandLine(unittest.TestCase):
    def runHeadless(self, *args):
        output = io.StringIO()
        with patch.object(sys, "argv", ["headless_run.py", *args]), \
                patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}), \
                contextlib.redirect_stdout(output), \
                self.assertRaises(SystemExit) as raised:
            runpy.run_module("headless_run", run_name="__main__")
        return raised.exception.code, output.getvalue()

    def test_arguments_that_are_not_positive_integers_exit_with_status_2_and_usage(self):
        for args in (("0",), ("-3",), ("abc",), ("3", "0"), ("3", "abc")):
            with self.subTest(args=args):
                status, output = self.runHeadless(*args)

                self.assertEqual(status, 2)
                self.assertIn("Usage: python headless_run.py [gridSize] [frames]", output)
                self.assertNotIn("PASS", output)

    def test_valid_arguments_run_every_scenario_and_exit_with_status_0(self):
        status, output = self.runHeadless("3", "2")

        self.assertEqual(status, 0)
        self.assertEqual(output.count("PASS"), 3)


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
