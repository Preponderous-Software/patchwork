"""
Print a Viron environment to the console, as an example of using text_renderer.

The environment must already exist, for example from a run of main.py, whose
environments.json records the ID. Nothing is created in Viron and no file is written.

Usage:
    python console_view.py <environmentId>

The exit status is 0 if the environment was printed, 1 if it could not be fetched or has
no locations, and 2 if the argument is missing or is not an integer.
"""
import sys

from Viron.src.main.python.preponderous.viron.services.locationService import LocationService
from text_renderer import renderLocations

url = "http://localhost"
port = 9999

usage = "Usage: python console_view.py <environmentId>"

def parseEnvironmentId(argv):
    """
    Read the environment ID from the command line.

    Args:
        argv (list): The argument vector, including the program name at index 0

    Returns:
        int: The environment ID, or None if there is not exactly one integer argument
    """
    if len(argv) != 2:
        return None
    try:
        return int(argv[1])
    except ValueError:
        return None

def main(argv, locationService=None):
    """
    Print the environment named on the command line.

    Args:
        argv (list): The argument vector, including the program name at index 0
        locationService (LocationService): The location service to use, or None to build one

    Returns:
        int: The exit status
    """
    if "--help" in argv[1:] or "-h" in argv[1:]:
        print(usage)
        return 0
    environmentId = parseEnvironmentId(argv)
    if environmentId is None:
        print(usage)
        return 2
    if locationService is None:
        locationService = LocationService(url, port)
    try:
        locations = locationService.get_locations_in_environment(environmentId)
    except Exception as e:
        print(f"Error fetching the locations of environment {environmentId}: {e}")
        return 1
    # Viron answers an unknown environment ID with an empty list rather than an error
    if not locations:
        print(f"Environment {environmentId} has no locations.")
        return 1
    print(renderLocations(locations))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
