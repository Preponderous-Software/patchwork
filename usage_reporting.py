import atexit
import json
import os
import re
import sys

from trace_client import TraceClient, allows_reporting, environment_opts_out

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
# Sent as the version when version.txt cannot be read: the client requires one, and a missing
# file must never stop patchwork from starting.
UNKNOWN_VERSION = "unknown"

DETAILS_URL = "https://danielstephenson.dev/usage-reporting"

FIRST_RUN_NOTICE = (
    "Usage reporting is on: patchwork sends its name, its version and a random installation ID "
    "at startup and an environment-created event to https://trace.danielstephenson.dev - "
    "nothing about you or the environments. "
    'Turn it off with "usage_reporting": {"enabled": false} in settings.json, or for every '
    "trace-reporting program with the environment variable TRACE_USAGE_REPORTING=off. "
    "Details: " + DETAILS_URL
)

# Shown on the first run instead when TRACE_USAGE_REPORTING=off or DO_NOT_TRACK=1 is already
# set: settings.json gets its block with "enabled": false, so a later run without the variable
# does not report either.
FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT = (
    'Usage reporting is off (environment), and "usage_reporting": {"enabled": false} was written '
    "to settings.json so it stays off. Details: " + DETAILS_URL
)


# Shown on the first run instead when settings.json already turns reporting off under another
# spelling (see hasNearMissOptOut): the real block is written with "enabled": false next to it.
FIRST_RUN_NOTICE_OFF_BY_SETTINGS = (
    'Usage reporting is off (settings.json), and "usage_reporting": {"enabled": false} was '
    "written to settings.json so it stays off. Details: " + DETAILS_URL
)


def firstRunNotice(nearMissOptOut=False):
    """The line the first run prints: FIRST_RUN_NOTICE, unless the environment or a near-miss
    opt-out in settings.json has already turned reporting off."""
    if environment_opts_out():
        return FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT
    if nearMissOptOut:
        return FIRST_RUN_NOTICE_OFF_BY_SETTINGS
    return FIRST_RUN_NOTICE


def _normaliseKey(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def hasNearMissOptOut(settings, settingsKey=SETTINGS_SECTION, switchKey="enabled"):
    """
    Whether ``settings`` holds an attempt to turn usage reporting off that is not written exactly
    as ``usage_reporting`` -> ``enabled``. Such a setting would not be recognised, the default
    block (``enabled: true``) would be written next to it, and reporting would stay on. An operator
    who wrote any of these did not ask for reporting, so each counts as off:

    - a top-level key that spells "usage reporting" another way (``usage-reporting``,
      ``usageReporting``, ``UsageReporting``, ...) holding a value, or an ``enabled``-like key,
      that is not clearly on;
    - ``"usage_reporting": "off"`` -- a value instead of a block;
    - inside any such block, a key that spells "enabled" another way (``enable``, ``Enabled``,
      ...) that is not clearly on, or one that spells "disabled" whose value is on.
    """
    for key, value in settings.items():
        if "usagereport" not in _normaliseKey(key):
            continue
        if not isinstance(value, dict):
            if not allows_reporting(value):
                return True
            continue
        for child, childValue in value.items():
            if key == settingsKey and child == switchKey:
                continue  # the switch itself, read by the caller
            name = _normaliseKey(child)
            if "disabl" in name and allows_reporting(childValue):
                return True
            if "enabl" in name and not allows_reporting(childValue):
                return True
    return False


def defaultSettings(enabled=True):
    """The usage_reporting block written to settings.json on first run."""
    return {"enabled": enabled, "endpoint": DEFAULT_ENDPOINT, "key": DEFAULT_KEY}


def installIdFile():
    """Where this installation's random ID (the tag ``install`` on every event) is kept:
    ``<user data dir>/patchwork/trace-install-id``, the user data dir being %APPDATA% on
    Windows, ~/Library/Application Support on macOS and $XDG_DATA_HOME (or ~/.local/share)
    elsewhere. The client only reads or creates it when reporting is on; deleting it resets
    the ID."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "").strip() or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", "").strip() or os.path.join(home, ".local", "share")
    return os.path.join(base, APPLICATION.lower(), "trace-install-id")


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

    # An opt-out written under another spelling (usage-reporting, an "enable" switch,
    # "disabled": true, ...) is an opt-out.
    nearMissOptOut = hasNearMissOptOut(settings)
    section = settings.get(SETTINGS_SECTION)
    if isinstance(section, dict):
        return dict(section, enabled=False) if nearMissOptOut else section
    if SETTINGS_SECTION in settings:
        # "usage_reporting": false (or "off", or anything else that is not a block) is the
        # switch itself: read it as such, and never write the default block (on) over it.
        return {"enabled": False if nearMissOptOut else section}

    # Under an environment or near-miss opt-out the first run records "off", so a later run
    # does not quietly report.
    settings[SETTINGS_SECTION] = defaultSettings(
        enabled=not (environment_opts_out() or nearMissOptOut))
    log(firstRunNotice(nearMissOptOut))
    try:
        with open(settingsFile, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        log(f"Could not write {settingsFile} ({e}); the notice above will be shown again next time.")
    return settings[SETTINGS_SECTION]


def buildClient(section, log=print):
    """
    A TraceClient for the given usage_reporting settings; disabled when they are None or opted out.
    Every event it sends carries the version from version.txt (or UNKNOWN_VERSION) as ``version``,
    and a random installation ID as ``install``: TRACE_INSTALL_ID when set, otherwise the one kept
    in installIdFile(). The client resolves both only after its opt-out checks, so a disabled
    client never creates the file.

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
        return TraceClient(endpoint, APPLICATION, readVersion() or UNKNOWN_VERSION, key=key,
                           # not bool(): bool("false") is True. Only true or an "on" string
                           # reports; "false", "off", 0, null or a typo do not.
                           enabled=allows_reporting(enabled),
                           install_id=os.environ.get("TRACE_INSTALL_ID"),
                           install_id_file=installIdFile())
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
    client.report("startup")
    atexit.register(client.close)
    return client
