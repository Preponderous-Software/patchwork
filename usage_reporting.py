import atexit
import json
import os

from trace_client import TraceClient, environment_opts_out

#  @author Daniel McCoy Stephenson
#  @since September 11th, 2026

APPLICATION = "patchwork"
SETTINGS_FILE = "settings.json"
SETTINGS_SECTION = "usage_reporting"
DEFAULT_ENDPOINT = "https://trace.danielstephenson.dev"
# The program key patchwork ships with. Keys identify a program rather than
# guard anything (trace's ADR 0001), so it lives here and in settings.json in
# the open. PATCHWORK_USAGE_REPORTING_KEY, when set, overrides both.
DEFAULT_KEY = "oAMBqZC_yjTIqlB86_O7G4ZZ3gWuGBCBLJLFbUuFaoU"
KEY_ENV_VAR = "PATCHWORK_USAGE_REPORTING_KEY"
VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")

DETAILS_URL = "https://github.com/Stephenson-Software/trace#usage-reporting"

FIRST_RUN_NOTICE = (
    "Usage reporting is on: patchwork sends its name and version at startup and an "
    "environment-created event to https://trace.danielstephenson.dev - "
    "nothing about you, your machine or the environments. "
    'Turn it off with "usage_reporting": {"enabled": false} in settings.json, or for every '
    "trace-reporting program with the environment variable TRACE_USAGE_REPORTING=off. "
    "Details: " + DETAILS_URL
)

# Shown on the first run instead when TRACE_USAGE_REPORTING=off or DO_NOT_TRACK=1 is already
# set: settings.json still gets its block, but saying reporting is on would mislead.
FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT = "Usage reporting is off (environment). Details: " + DETAILS_URL


def firstRunNotice():
    """The line the first run prints: FIRST_RUN_NOTICE, unless the environment has opted out."""
    if environment_opts_out():
        return FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT
    return FIRST_RUN_NOTICE


def defaultSettings():
    """The usage_reporting block written to settings.json on first run."""
    return {"enabled": True, "endpoint": DEFAULT_ENDPOINT, "key": DEFAULT_KEY}


def readVersion(versionFile=VERSION_FILE):
    """The program's own version, as recorded in version.txt, or None if it cannot be read."""
    try:
        with open(versionFile, "r") as f:
            version = f.read().strip()
        return version or None
    except OSError:
        return None


def loadSettings(settingsFile=SETTINGS_FILE, log=print):
    """
    Read the usage_reporting block from the settings file, writing the default
    block (and printing the one-time notice) when the file does not have one yet.

    Returns:
        dict or None: The usage_reporting settings, or None if the settings file
        exists but cannot be read, in which case nothing should be reported.
    """
    settings = {}
    if os.path.exists(settingsFile):
        try:
            with open(settingsFile, "r") as f:
                settings = json.load(f)
            if not isinstance(settings, dict):
                raise ValueError("settings file is not a JSON object")
        except (OSError, ValueError) as e:
            log(f"Could not read {settingsFile} ({e}); usage reporting is off until it is fixed.")
            return None

    section = settings.get(SETTINGS_SECTION)
    if isinstance(section, dict):
        return section

    settings[SETTINGS_SECTION] = defaultSettings()
    log(firstRunNotice())
    try:
        with open(settingsFile, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        log(f"Could not write {settingsFile} ({e}); the notice above will be shown again next time.")
    return settings[SETTINGS_SECTION]


def buildClient(section, log=print):
    """
    A TraceClient for the given usage_reporting settings; disabled when they are None or opted out.

    The client is built through TraceClient whenever the settings could be read, because the
    client checks the TRACE_USAGE_REPORTING and DO_NOT_TRACK environment variables before the
    settings' own ``enabled`` and records why it is off in ``disabled_reason``.
    """
    if section is None:
        return TraceClient.disabled()
    enabled = section.get("enabled", True)
    endpoint = section.get("endpoint") or DEFAULT_ENDPOINT
    # PATCHWORK_USAGE_REPORTING_KEY first, then the settings block, then the shipped key: a
    # settings.json written before the key shipped has no "key" entry and still reports.
    key = os.environ.get(KEY_ENV_VAR, "").strip() or str(section.get("key") or "").strip() or DEFAULT_KEY
    try:
        return TraceClient(endpoint, APPLICATION, key=key, enabled=bool(enabled))
    except ValueError as e:
        log(f"Could not configure usage reporting ({e}); usage reporting is off.")
        return TraceClient.disabled()


def startUsageReporting(settingsFile=SETTINGS_FILE, log=print):
    """
    Read the settings, build the client and report the startup event.
    Never raises; the client is closed automatically when the interpreter exits.

    Returns:
        TraceClient: The client, so that further events could be reported.
    """
    try:
        client = buildClient(loadSettings(settingsFile, log), log)
    except Exception as e:
        log(f"Could not start usage reporting ({e}); usage reporting is off.")
        return TraceClient.disabled()
    version = readVersion()
    client.report("startup", tags={"version": version} if version else None)
    atexit.register(client.close)
    return client
