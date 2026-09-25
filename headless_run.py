"""
Drive main.py end to end without a display, without Docker and without a Viron server.

Pygame, RenderWindow and Graphik are the real ones, rendering to SDL's dummy video driver.
Only Viron is replaced: its service modules are stubbed in sys.modules so that main.py can
be imported (they need Python 3.10+ and a populated submodule), and main() is handed
in-memory services instead of ones pointed at http://localhost:9999.

Three scenarios are run, each in a fresh temporary working directory so that no
environments.json in the repository is read or written:

- create-and-exit:   a new environment is created and rendered once (--exit-after-create)
- create-and-render: a new environment is created and the render loop runs
- load-and-render:   a cached environment is loaded and the render loop runs

Usage:
    python headless_run.py [gridSize] [frames]

gridSize defaults to 10 and frames, the number of render-loop frames per scenario, to 30.
The exit status is 0 if every scenario behaved as expected and 1 otherwise.
"""
import json
import os
import sys
import tempfile
import time
import traceback
import types
from unittest.mock import MagicMock, patch

defaultGridSize = 10
defaultFrames = 30


def installVironStubs():
    """
    Register stand-in modules for Viron's service modules so that main.py can be imported
    without the submodule being populated and on interpreters older than Python 3.10.
    The stand-ins are never used to reach a server; main() is always given fake services.
    """
    servicesPath = "Viron.src.main.python.preponderous.viron.services"
    parts = servicesPath.split(".")
    for depth in range(1, len(parts) + 1):
        packageName = ".".join(parts[:depth])
        sys.modules.setdefault(packageName, types.ModuleType(packageName))
    for moduleName, className in (("environmentService", "EnvironmentService"),
                                  ("locationService", "LocationService")):
        qualifiedName = servicesPath + "." + moduleName
        if qualifiedName not in sys.modules:
            module = types.ModuleType(qualifiedName)
            setattr(module, className, MagicMock(name=className))
            sys.modules[qualifiedName] = module


class FakeEnvironment:
    def __init__(self, environmentId, gridSize):
        self.environmentId = environmentId
        self.gridSize = gridSize

    def getEnvironmentId(self):
        return self.environmentId


class FakeLocation:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y


class FakeEnvironmentService:
    """In-memory stand-in for Viron's EnvironmentService."""

    def __init__(self):
        self.environments = {}

    def create_environment(self, name, numGrids, gridSize):
        environment = FakeEnvironment(len(self.environments) + 1, gridSize)
        self.environments[environment.getEnvironmentId()] = environment
        return environment

    def get_environment_by_id(self, environmentId):
        return self.environments[environmentId]


class FakeLocationService:
    """In-memory stand-in for Viron's LocationService, with one location per grid cell."""

    def __init__(self, environmentService):
        self.environmentService = environmentService

    def get_locations_in_environment(self, environmentId):
        gridSize = self.environmentService.environments[environmentId].gridSize
        return [FakeLocation(x, y) for x in range(gridSize) for y in range(gridSize)]


class FrameCounter:
    """Counts render-loop frames and posts a QUIT event once the requested number is reached."""

    def __init__(self, pygame, frames):
        self.pygame = pygame
        self.frames = frames
        self.count = 0
        self.firstTickTime = None
        self.lastTickTime = None

    def wrapShouldContinue(self, shouldContinue):
        """
        Stop the loop after one iteration more than the requested frames even if tick() is
        never called, so that a render loop which stops ticking fails the check instead of
        running forever.
        """
        iterations = [0]

        def countingShouldContinue(window):
            iterations[0] += 1
            if iterations[0] > self.frames + 1:
                window.close()
            return shouldContinue(window)
        return countingShouldContinue

    def wrapTick(self, tick):
        def countingTick(window, fps):
            tick(window, fps)
            self.lastTickTime = time.perf_counter()
            if self.firstTickTime is None:
                self.firstTickTime = self.lastTickTime
            self.count += 1
            if self.count == self.frames:
                self.pygame.event.post(self.pygame.event.Event(self.pygame.QUIT))
        return countingTick

    def framesPerSecond(self):
        """The frame rate measured between the first and last ticks, or None below two frames."""
        if self.count < 2:
            return None
        return (self.count - 1) / (self.lastTickTime - self.firstTickTime)


def runScenario(name, gridSize, frames, exitAfterCreate, cachedEnvironment):
    """
    Run main() once in a fresh temporary working directory and check what it did.

    Args:
        name (str): The scenario name, used in the report
        gridSize (int): The size of one side of the grid
        frames (int): The number of render-loop frames after which the window is closed
        exitAfterCreate (bool): Whether to pass exitAfterCreate to main()
        cachedEnvironment (bool): Whether environments.json already records the environment

    Returns:
        bool: True if main() returned normally and behaved as expected
    """
    import pygame
    import main
    import render_window

    environmentService = FakeEnvironmentService()
    locationService = FakeLocationService(environmentService)
    envKey = main.getEnvironmentKey(gridSize)
    counter = FrameCounter(pygame, frames)
    previousDirectory = os.getcwd()

    with tempfile.TemporaryDirectory() as workingDirectory:
        os.chdir(workingDirectory)
        try:
            if cachedEnvironment:
                environment = environmentService.create_environment("Test", main.numGrids, gridSize)
                with open("environments.json", "w") as cacheFile:
                    json.dump({envKey: {"environment_id": environment.getEnvironmentId()}}, cacheFile)

            # The pause after --exit-after-create only exists so that a person can see the frame.
            renderWindow = render_window.RenderWindow
            with patch.object(renderWindow, "tick", counter.wrapTick(renderWindow.tick)), \
                    patch.object(renderWindow, "should_continue", counter.wrapShouldContinue(renderWindow.should_continue)), \
                    patch.object(main.time, "sleep"):
                main.main(gridSize, exitAfterCreate,
                          locationService=locationService, environmentService=environmentService)

            with open("environments.json", "r") as cacheFile:
                recorded = json.load(cacheFile)
        except Exception:
            print(f"FAIL {name}: main() raised")
            traceback.print_exc()
            return False
        finally:
            os.chdir(previousDirectory)

    expectedFrames = 0 if exitAfterCreate else frames
    problems = []
    if envKey not in recorded:
        problems.append(f"environments.json has no entry for {envKey}")
    if counter.count != expectedFrames:
        problems.append(f"rendered {counter.count} render-loop frame(s), expected {expectedFrames}")
    if pygame.get_init():
        problems.append("pygame was left initialised")

    if problems:
        print(f"FAIL {name}: " + "; ".join(problems))
        return False
    framesPerSecond = counter.framesPerSecond()
    rate = f" at {framesPerSecond:.1f} fps" if framesPerSecond is not None else ""
    print(f"PASS {name}: {counter.count} render-loop frame(s){rate}")
    return True


def run(gridSize=defaultGridSize, frames=defaultFrames):
    """
    Run every scenario against the real pygame, RenderWindow and Graphik.

    Args:
        gridSize (int): The size of one side of the grid
        frames (int): The number of render-loop frames per scenario

    Returns:
        bool: True if every scenario passed
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    installVironStubs()
    results = [
        runScenario("create-and-exit", gridSize, frames, exitAfterCreate=True, cachedEnvironment=False),
        runScenario("create-and-render", gridSize, frames, exitAfterCreate=False, cachedEnvironment=False),
        runScenario("load-and-render", gridSize, frames, exitAfterCreate=False, cachedEnvironment=True),
    ]
    return all(results)


if __name__ == "__main__":
    try:
        gridSize = int(sys.argv[1]) if len(sys.argv) > 1 else defaultGridSize
        frames = int(sys.argv[2]) if len(sys.argv) > 2 else defaultFrames
    except ValueError:
        gridSize = frames = 0
    if gridSize < 1 or frames < 1:
        print("Usage: python headless_run.py [gridSize] [frames], both positive integers")
        sys.exit(2)
    sys.exit(0 if run(gridSize, frames) else 1)
