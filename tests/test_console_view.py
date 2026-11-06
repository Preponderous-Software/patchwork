import contextlib
import importlib
import io
import os
import runpy
import sys
import unittest
from unittest.mock import MagicMock, patch

import headless_run

headless_run.installVironStubs()

import console_view


def fakeLocationService(locations):
    locationService = MagicMock()
    locationService.get_locations_in_environment.return_value = locations
    return locationService


def runMain(argv, locationService=None):
    """Run console_view.main() and return its exit status along with what it printed."""
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = console_view.main(argv, locationService=locationService)
    return status, output.getvalue()


class TestParseEnvironmentId(unittest.TestCase):
    def test_reads_the_environment_id_from_the_first_argument(self):
        self.assertEqual(console_view.parseEnvironmentId(["console_view.py", "7"]), 7)

    def test_a_missing_argument_gives_none(self):
        self.assertIsNone(console_view.parseEnvironmentId(["console_view.py"]))

    def test_a_non_integer_argument_gives_none(self):
        self.assertIsNone(console_view.parseEnvironmentId(["console_view.py", "seven"]))

    def test_more_than_one_argument_gives_none(self):
        self.assertIsNone(console_view.parseEnvironmentId(["console_view.py", "7", "8"]))


class TestMain(unittest.TestCase):
    def test_prints_the_environment_and_exits_zero(self):
        locations = [headless_run.FakeLocation(x, y) for x in range(2) for y in range(2)]
        locationService = fakeLocationService(locations)

        status, output = runMain(["console_view.py", "7"], locationService)

        self.assertEqual(status, 0)
        self.assertEqual(output, "# #\n# #\n")
        locationService.get_locations_in_environment.assert_called_once_with(7)

    def test_a_missing_argument_prints_the_usage_and_exits_two_without_reaching_viron(self):
        locationService = fakeLocationService([])

        status, output = runMain(["console_view.py"], locationService)

        self.assertEqual(status, 2)
        self.assertEqual(output, console_view.usage + "\n")
        locationService.get_locations_in_environment.assert_not_called()

    def test_a_non_integer_argument_prints_the_usage_and_exits_two(self):
        status, output = runMain(["console_view.py", "seven"], fakeLocationService([]))

        self.assertEqual(status, 2)
        self.assertEqual(output, console_view.usage + "\n")

    def test_help_prints_the_usage_and_exits_zero_without_reaching_viron(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag), patch.object(console_view, "LocationService") as service:
                status, output = runMain(["console_view.py", flag])

                self.assertEqual(status, 0)
                self.assertEqual(output, console_view.usage + "\n")
                service.assert_not_called()

    def test_a_failed_fetch_prints_the_error_and_exits_one(self):
        locationService = MagicMock()
        locationService.get_locations_in_environment.side_effect = ConnectionError("refused")

        status, output = runMain(["console_view.py", "7"], locationService)

        self.assertEqual(status, 1)
        self.assertEqual(output, "Error fetching the locations of environment 7: refused\n")

    def test_an_environment_with_no_locations_is_reported_and_exits_one(self):
        status, output = runMain(["console_view.py", "7"], fakeLocationService([]))

        self.assertEqual(status, 1)
        self.assertEqual(output, "Environment 7 has no locations.\n")

    def test_a_service_pointed_at_the_local_viron_is_built_by_default(self):
        with patch.object(console_view, "LocationService") as service:
            service.return_value = fakeLocationService([headless_run.FakeLocation(0, 0)])

            status, output = runMain(["console_view.py", "7"])

        self.assertEqual(status, 0)
        self.assertEqual(output, "#\n")
        service.assert_called_once_with("http://localhost", 9999)


class TestEntryPoint(unittest.TestCase):
    def test_the_exit_status_of_main_reaches_the_process(self):
        scriptPath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "console_view.py")

        with patch.object(sys, "argv", ["console_view.py"]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(scriptPath, run_name="__main__")

        self.assertEqual(caught.exception.code, 2)

    def test_the_module_can_be_imported_without_pygame(self):
        with patch.dict(sys.modules, {"pygame": None}):
            importlib.reload(console_view)


if __name__ == "__main__":
    unittest.main()
