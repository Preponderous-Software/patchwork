import random
import pygame
from Viron.src.main.python.preponderous.viron.services.environmentService import EnvironmentService
from Viron.src.main.python.preponderous.viron.services.locationService import LocationService
from graphik import Graphik
from render_window import RenderWindow
from usage_reporting import startUsageReporting
import os
import json
import sys
import time


black = (0,0,0)
white = (255,255,255)

displayWidth = 800
displayHeight = 800

targetFramesPerSecond = 60

numGrids = 1
defaultGridSize = 50

url = "http://localhost"
port = 9999

def log(message):
    print(message)

def parseArgs(argv):
    """
    Parse the command line arguments.

    Args:
        argv (list): The argument vector, including the program name at index 0

    Returns:
        tuple: The grid size to use, and whether to exit after creating the environment
    """
    gridSize = defaultGridSize
    if len(argv) > 1:
        try:
            gridSize = int(argv[1])
        except ValueError:
            log("Invalid grid size argument, using default of " + str(defaultGridSize) + ".")
            gridSize = defaultGridSize
    exitAfterCreate = len(argv) > 2 and argv[2] == "--exit-after-create"
    return gridSize, exitAfterCreate

def getEnvironmentKey(gridSize):
    """
    Build the key under which an environment of the given size is recorded in the cache file.

    Args:
        gridSize (int): The size of one side of the grid

    Returns:
        str: The cache key, for example "1x50"
    """
    return f"{numGrids}x{gridSize}"

def drawEnvironment(locations, graphik, locationWidth, locationHeight):
    for location in locations:
        red = random.randrange(50, 200)
        green = random.randrange(50, 200)
        blue = random.randrange(50, 200)
        x = location.get_x() * locationWidth
        y = location.get_y() * locationHeight
        graphik.drawRectangle(x - 1, y - 1, locationWidth * 1.5, locationHeight * 1.5, (red,green,blue))

def main(gridSize=defaultGridSize, exitAfterCreate=False, locationService=None, environmentService=None,
         reportUsage=False):
    """
    Render an environment of the requested size, creating it through Viron if it is not
    already recorded in the cache file.

    Args:
        gridSize (int): The size of one side of the grid
        exitAfterCreate (bool): Whether to render a newly created environment once and exit
        locationService (LocationService): The location service to use, or None to build one
        environmentService (EnvironmentService): The environment service to use, or None to build one
        reportUsage (bool): Whether to start usage reporting for this process
    """
    usage = startUsageReporting(log=log) if reportUsage else None
    if locationService is None:
        locationService = LocationService(url, port)
    if environmentService is None:
        environmentService = EnvironmentService(url, port)
    window = RenderWindow("Visualizing Environment With Random Colors", displayWidth, displayHeight, resizable=True)
    gameDisplay = window.get_surface()
    graphik = Graphik(gameDisplay)

    env_file = "environments.json"
    environments = {}

    # Load existing environments if file exists
    if os.path.exists(env_file):
        log("Environments file exists, loading...")
        with open(env_file, "r") as f:
            environments = json.load(f)

    # Create a unique key for the environment based on grid size and numGrids
    env_key = getEnvironmentKey(gridSize)

    if env_key in environments:
        graphik.drawText("Loading existing environment, please wait...", displayWidth/2, displayHeight/2, 20, "white")
        pygame.display.update()
        env_id = environments[env_key]["environment_id"]
        try:
            environment = environmentService.get_environment_by_id(env_id)
            log(f"Loaded existing environment with id {env_id} and size {gridSize}x{gridSize} with {numGrids} grid(s).")
        except Exception as e:
            log(f"Error loading existing environment: {e}")
            graphik.drawText("Error loading environment, please check logs.", displayWidth/2, displayHeight/2 + 30, 20, "red")
            pygame.display.update()
            time.sleep(2)
            window.close()
            return
    else:
        graphik.drawText("Creating environment, please wait...", displayWidth/2, displayHeight/2, 20,"white")
        pygame.display.update()
        log("Creating environment with " + str(numGrids) + " grid(s) of size " + str(gridSize) + "x" + str(gridSize))
        start_time = time.time()
        environment = environmentService.create_environment("Test", numGrids, gridSize)
        end_time = time.time()
        environments[env_key] = {
            "environment_id": environment.getEnvironmentId(),
            "grid_size": gridSize,
            "num_grids": numGrids,
            "creation_time_seconds": end_time - start_time
        }
        with open(env_file, "w") as f:
            json.dump(environments, f, indent=2)
        if usage is not None:
            usage.report("environment-created")
        log(f"Created new environment with id {environment.getEnvironmentId()} in {end_time - start_time:.2f} seconds.")

        if exitAfterCreate:
            log("Exiting after environment creation.")
            locations = locationService.get_locations_in_environment(environment.getEnvironmentId())
            drawEnvironment(locations, graphik, displayWidth/gridSize, displayHeight/gridSize)
            pygame.display.update()
            time.sleep(2)
            window.close()
            return

    locationsCache = {}

    while window.should_continue():
        if locationsCache == {}:
            log("Fetching locations from service...")
            locationsCache = locationService.get_locations_in_environment(environment.getEnvironmentId())

        # the window is resizable, so the grid is scaled to the surface's current size every frame
        surfaceWidth, surfaceHeight = gameDisplay.get_size()
        locationWidth = surfaceWidth/gridSize
        locationHeight = surfaceHeight/gridSize

        gameDisplay.fill(white)
        drawEnvironment(locationsCache, graphik, locationWidth, locationHeight)
        pygame.display.update()
        window.tick(targetFramesPerSecond)

    window.close()

if __name__ == "__main__":
    gridSize, exitAfterCreate = parseArgs(sys.argv)
    main(gridSize, exitAfterCreate, reportUsage=True)
