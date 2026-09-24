import json
import os
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import pygame


def installVironStubs():
    """
    Register stand-in modules for the Viron submodule so that main.py can be imported
    without the submodule being populated, and without any test reaching a real server.
    Viron's own service modules use PEP 585 annotations, so they are also unimportable
    on the Python versions below 3.9 that this suite is expected to run on.
    """
    servicesPath = "Viron.src.main.python.preponderous.viron.services"
    parts = servicesPath.split(".")
    for depth in range(1, len(parts) + 1):
        packageName = ".".join(parts[:depth])
        sys.modules.setdefault(packageName, types.ModuleType(packageName))
    for moduleName, className in (("environmentService", "EnvironmentService"),
                                  ("locationService", "LocationService")):
        qualifiedName = servicesPath + "." + moduleName
        module = types.ModuleType(qualifiedName)
        setattr(module, className, MagicMock(name=className))
        sys.modules[qualifiedName] = module


installVironStubs()

import main

# Captured immediately after the import above, so that the import-time side effects the
# module used to have are observable even once later tests have driven main() themselves.
pygameInitialisedAtImport = pygame.get_init()
environmentServiceCallsAtImport = main.EnvironmentService.call_count
locationServiceCallsAtImport = main.LocationService.call_count


class TestParseArgs(unittest.TestCase):
    def test_defaults_when_only_the_program_name_is_given(self):
        self.assertEqual(main.parseArgs(["main.py"]), (50, False))

    def test_reads_the_grid_size_from_the_first_argument(self):
        self.assertEqual(main.parseArgs(["main.py", "100"]), (100, False))

    def test_falls_back_to_the_default_on_an_unparseable_grid_size(self):
        self.assertEqual(main.parseArgs(["main.py", "wide"]), (50, False))

    def test_detects_the_exit_after_create_flag(self):
        self.assertEqual(main.parseArgs(["main.py", "100", "--exit-after-create"]), (100, True))

    def test_ignores_an_unrecognized_second_argument(self):
        self.assertEqual(main.parseArgs(["main.py", "100", "--render-forever"]), (100, False))


class TestGetEnvironmentKey(unittest.TestCase):
    def test_key_combines_the_grid_count_and_the_grid_size(self):
        self.assertEqual(main.getEnvironmentKey(50), "1x50")

    def test_key_tracks_the_requested_grid_size(self):
        self.assertEqual(main.getEnvironmentKey(7), "1x7")


class TestImportSideEffects(unittest.TestCase):
    def test_importing_main_does_not_construct_the_viron_services(self):
        self.assertEqual(environmentServiceCallsAtImport, 0)
        self.assertEqual(locationServiceCallsAtImport, 0)

    def test_importing_main_does_not_initialise_pygame(self):
        self.assertFalse(pygameInitialisedAtImport)


class MainTestCase(unittest.TestCase):
    """
    Base fixture for the tests that drive main() itself. Pygame, the window, the drawing
    helper and the clock are all replaced, and the working directory is a fresh temporary
    one so that the environments.json cache file written by main() is real but disposable.
    """

    def setUp(self):
        self.mockPygame = self.startPatch("main.pygame")
        self.mockRenderWindow = self.startPatch("main.RenderWindow")
        self.mockGraphik = self.startPatch("main.Graphik")
        self.mockStartUsageReporting = self.startPatch("main.startUsageReporting")
        self.mockTime = self.startPatch("main.time")
        self.mockTime.time.side_effect = [1.0, 3.5]

        self.window = self.mockRenderWindow.return_value
        self.graphik = self.mockGraphik.return_value
        self.setFrames(0)

        self.environmentService = MagicMock(name="EnvironmentService")
        self.environmentService.create_environment.return_value = self.makeEnvironment(7)
        self.environmentService.get_environment_by_id.return_value = self.makeEnvironment(42)
        self.locationService = MagicMock(name="LocationService")
        self.locationService.get_locations_in_environment.return_value = [self.makeLocation(0, 0)]

        workingDirectory = tempfile.TemporaryDirectory()
        self.addCleanup(workingDirectory.cleanup)
        previousDirectory = os.getcwd()
        self.addCleanup(os.chdir, previousDirectory)
        os.chdir(workingDirectory.name)

    def startPatch(self, target):
        patcher = patch(target)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def setFrames(self, frames):
        """Let the render loop run for the given number of iterations, then stop."""
        self.window.should_continue.side_effect = [True] * frames + [False]

    def makeEnvironment(self, environmentId):
        environment = MagicMock(name=f"Environment({environmentId})")
        environment.getEnvironmentId.return_value = environmentId
        return environment

    def makeLocation(self, x, y):
        location = MagicMock(name=f"Location({x},{y})")
        location.get_x.return_value = x
        location.get_y.return_value = y
        return location

    def writeCacheFile(self, contents):
        with open("environments.json", "w") as cacheFile:
            json.dump(contents, cacheFile)

    def readCacheFile(self):
        with open("environments.json", "r") as cacheFile:
            return json.load(cacheFile)

    def runMain(self, gridSize=10, exitAfterCreate=False, reportUsage=False):
        main.main(gridSize, exitAfterCreate,
                  locationService=self.locationService,
                  environmentService=self.environmentService,
                  reportUsage=reportUsage)


class TestEnvironmentCreation(MainTestCase):
    def test_creates_an_environment_when_the_cache_file_is_absent(self):
        self.runMain(gridSize=10)

        self.environmentService.create_environment.assert_called_once_with("Test", 1, 10)

    def test_records_the_created_environment_in_the_cache_file(self):
        self.runMain(gridSize=10)

        self.assertEqual(self.readCacheFile(), {
            "1x10": {
                "environment_id": 7,
                "grid_size": 10,
                "num_grids": 1,
                "creation_time_seconds": 2.5,
            }
        })

    def test_leaves_unrelated_cache_entries_intact(self):
        self.writeCacheFile({"1x99": {"environment_id": 99}})

        self.runMain(gridSize=10)

        self.assertEqual(self.readCacheFile()["1x99"], {"environment_id": 99})

    def test_reuses_a_cached_environment_instead_of_creating_a_new_one(self):
        self.writeCacheFile({"1x10": {"environment_id": 42}})

        self.runMain(gridSize=10)

        self.environmentService.create_environment.assert_not_called()
        self.environmentService.get_environment_by_id.assert_called_once_with(42)

    def test_exit_after_create_skips_the_render_loop(self):
        self.runMain(gridSize=10, exitAfterCreate=True)

        self.window.should_continue.assert_not_called()
        self.window.close.assert_called_once()

    def test_exit_after_create_is_ignored_for_a_cached_environment(self):
        self.writeCacheFile({"1x10": {"environment_id": 42}})

        self.runMain(gridSize=10, exitAfterCreate=True)

        self.window.should_continue.assert_called()


class TestLoadingMessage(MainTestCase):
    """Regression coverage for the cached-environment progress message (#21)."""

    def recordOrderedCalls(self):
        calls = []
        self.graphik.drawText.side_effect = lambda text, *rest: calls.append(("drawText", text))
        self.mockPygame.display.update.side_effect = lambda: calls.append(("update", None))
        self.environmentService.get_environment_by_id.side_effect = \
            lambda environmentId: calls.append(("get_environment_by_id", environmentId))
        return calls

    def test_loading_message_is_flushed_before_the_blocking_fetch(self):
        self.writeCacheFile({"1x10": {"environment_id": 42}})
        calls = self.recordOrderedCalls()

        self.runMain(gridSize=10)

        self.assertEqual(calls[:3], [
            ("drawText", "Loading existing environment, please wait..."),
            ("update", None),
            ("get_environment_by_id", 42),
        ])

    def test_creation_message_is_centred_on_the_display(self):
        self.runMain(gridSize=10)

        self.graphik.drawText.assert_any_call(
            "Creating environment, please wait...",
            main.displayWidth / 2, main.displayHeight / 2, 20, "white")

    def test_a_failed_load_reports_the_error_and_closes_the_window(self):
        self.writeCacheFile({"1x10": {"environment_id": 42}})
        self.environmentService.get_environment_by_id.side_effect = RuntimeError("unreachable")

        self.runMain(gridSize=10)

        self.graphik.drawText.assert_any_call(
            "Error loading environment, please check logs.",
            main.displayWidth / 2, main.displayHeight / 2 + 30, 20, "red")
        self.window.should_continue.assert_not_called()
        self.window.close.assert_called_once()


class TestUsageReporting(MainTestCase):
    def test_direct_main_call_does_not_start_usage_reporting_or_write_settings(self):
        self.runMain(gridSize=10)

        self.mockStartUsageReporting.assert_not_called()
        self.assertFalse(os.path.exists("settings.json"))

    def test_cli_path_can_opt_in_to_usage_reporting(self):
        self.runMain(gridSize=10, reportUsage=True)

        self.mockStartUsageReporting.assert_called_once_with(log=main.log)

    def test_creating_an_environment_reports_environment_created(self):
        self.runMain(gridSize=10, reportUsage=True)

        client = self.mockStartUsageReporting.return_value
        client.report.assert_called_once_with("environment-created")

    def test_loading_a_cached_environment_reports_nothing_further(self):
        self.writeCacheFile({"1x10": {"environment_id": 42, "grid_size": 10, "num_grids": 1}})

        self.runMain(gridSize=10, reportUsage=True)

        self.mockStartUsageReporting.return_value.report.assert_not_called()


class TestCliEntrypoint(unittest.TestCase):
    def test_module_entrypoint_enables_usage_reporting(self):
        usageReportingModule = types.ModuleType("usage_reporting")
        usageReportingModule.startUsageReporting = MagicMock(name="startUsageReporting")

        pygameModule = types.ModuleType("pygame")
        pygameModule.display = types.SimpleNamespace(update=MagicMock(name="update"))

        graphikModule = types.ModuleType("graphik")
        graphikModule.Graphik = MagicMock(name="Graphik")

        renderWindowModule = types.ModuleType("render_window")
        window = MagicMock(name="window")
        window.get_surface.return_value = MagicMock(name="surface")
        window.should_continue.return_value = False
        renderWindowModule.RenderWindow = MagicMock(name="RenderWindow", return_value=window)

        class FakeEnvironment:
            def getEnvironmentId(self):
                return 7

        class FakeEnvironmentService:
            def __init__(self, url, port):
                self.url = url
                self.port = port

            def create_environment(self, name, numGrids, gridSize):
                return FakeEnvironment()

        class FakeLocationService:
            def __init__(self, url, port):
                self.url = url
                self.port = port

            def get_locations_in_environment(self, environmentId):
                return []

        servicesPath = "Viron.src.main.python.preponderous.viron.services"
        moduleMap = {
            "usage_reporting": usageReportingModule,
            "pygame": pygameModule,
            "graphik": graphikModule,
            "render_window": renderWindowModule,
        }
        parts = servicesPath.split(".")
        for depth in range(1, len(parts) + 1):
            packageName = ".".join(parts[:depth])
            moduleMap[packageName] = types.ModuleType(packageName)

        environmentModule = types.ModuleType(servicesPath + ".environmentService")
        environmentModule.EnvironmentService = FakeEnvironmentService
        locationModule = types.ModuleType(servicesPath + ".locationService")
        locationModule.LocationService = FakeLocationService
        moduleMap[environmentModule.__name__] = environmentModule
        moduleMap[locationModule.__name__] = locationModule

        workingDirectory = tempfile.TemporaryDirectory()
        self.addCleanup(workingDirectory.cleanup)
        previousDirectory = os.getcwd()
        self.addCleanup(os.chdir, previousDirectory)
        os.chdir(workingDirectory.name)

        with patch.object(sys, "argv", ["main.py", "10", "--exit-after-create"]), \
                patch("time.sleep", return_value=None), \
                patch.dict(sys.modules, moduleMap, clear=False):
            moduleGlobals = runpy.run_module("main", run_name="__main__")

        usageReportingModule.startUsageReporting.assert_called_once_with(log=moduleGlobals["log"])


class TestRenderLoop(MainTestCase):
    def test_every_frame_is_capped_at_the_target_frame_rate(self):
        self.setFrames(3)

        self.runMain(gridSize=10)

        self.assertEqual(self.window.tick.call_count, 3)
        self.window.tick.assert_called_with(main.targetFramesPerSecond)

    def test_target_frame_rate_is_positive(self):
        self.assertGreater(main.targetFramesPerSecond, 0)

    def test_locations_are_fetched_once_and_then_reused(self):
        self.setFrames(3)

        self.runMain(gridSize=10)

        self.locationService.get_locations_in_environment.assert_called_once_with(7)

    def test_the_window_is_closed_once_the_loop_stops(self):
        self.setFrames(2)

        self.runMain(gridSize=10)

        self.window.close.assert_called_once()

    def test_each_frame_clears_the_surface_before_drawing(self):
        self.setFrames(2)

        self.runMain(gridSize=10)

        surface = self.window.get_surface.return_value
        self.assertEqual(surface.fill.call_count, 2)
        surface.fill.assert_called_with(main.white)


if __name__ == "__main__":
    unittest.main()
