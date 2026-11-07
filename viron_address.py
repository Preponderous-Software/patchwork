"""
Work out where the Viron server is, for main.py and console_view.py alike.

This has its own module because console_view.py cannot import main.py without pulling in
Pygame.
"""
import os

URL_ENV_VAR = "PATCHWORK_VIRON_URL"
PORT_ENV_VAR = "PATCHWORK_VIRON_PORT"

defaultUrl = "http://localhost"
defaultPort = 9999

def parsePort(value):
    """
    Read a port number, falling back to the default if the value cannot be one.

    Args:
        value (str): The text of the port

    Returns:
        int: The port, or the default port if the value is not an integer from 1 to 65535
    """
    try:
        port = int(value)
    except ValueError:
        port = 0
    if port < 1 or port > 65535:
        print(f"Invalid {PORT_ENV_VAR} value {value!r}, using default of {defaultPort}.")
        return defaultPort
    return port

def getVironAddress():
    """
    Read the address of the Viron server from the environment.

    A variable that is unset, empty or only whitespace leaves its default in place.

    Returns:
        tuple: The URL, without a trailing slash, and the port
    """
    # Viron's services append ":<port>/api/v1/..." to the URL, so a trailing slash would put the port in the path
    url = os.environ.get(URL_ENV_VAR, "").strip().rstrip("/") or defaultUrl
    portValue = os.environ.get(PORT_ENV_VAR, "").strip()
    port = parsePort(portValue) if portValue else defaultPort
    return url, port
