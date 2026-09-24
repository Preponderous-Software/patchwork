import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import usage_reporting
from usage_reporting import (
    DEFAULT_ENDPOINT,
    DEFAULT_KEY,
    DETAILS_URL,
    FIRST_RUN_NOTICE,
    FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT,
    KEY_ENV_VAR,
    buildClient,
    loadSettings,
    readVersion,
    startUsageReporting,
)

_ENV_VARS = ("TRACE_USAGE_REPORTING", "DO_NOT_TRACK")


def _scrubEnvironment(test):
    """The machine running the tests may itself have opted out of usage reporting; every
    test starts from a clean environment and sets what it needs."""
    scrubbed = {k: v for k, v in os.environ.items() if k not in _ENV_VARS}
    patcher = patch.dict(os.environ, scrubbed, clear=True)
    patcher.start()
    test.addCleanup(patcher.stop)


def _stubServer(requests, arrived):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            requests.append({
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(self.rfile.read(length).decode("utf-8")),
            })
            self.send_response(201)
            self.send_header("Content-Length", "0")
            self.end_headers()
            arrived.set()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class TestUsageReportingSettings(unittest.TestCase):
    def setUp(self):
        _scrubEnvironment(self)
        self.tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempDir.cleanup)
        self.settingsFile = os.path.join(self.tempDir.name, "settings.json")
        self.logged = []

    def log(self, message):
        self.logged.append(message)

    def readSettingsFile(self):
        with open(self.settingsFile, "r") as f:
            return json.load(f)

    def test_first_run_writes_defaults_and_shows_the_notice_once(self):
        section = loadSettings(self.settingsFile, self.log)

        self.assertEqual({"enabled": True, "endpoint": DEFAULT_ENDPOINT, "key": DEFAULT_KEY}, section)
        self.assertEqual([FIRST_RUN_NOTICE], self.logged)
        self.assertEqual({"usage_reporting": section}, self.readSettingsFile())

        self.logged.clear()
        secondRun = loadSettings(self.settingsFile, self.log)

        self.assertEqual(section, secondRun)
        self.assertEqual([], self.logged, "the notice must not be shown on the second run")

    def test_notice_names_the_program_and_every_opt_out(self):
        self.assertTrue(FIRST_RUN_NOTICE.startswith("Usage reporting is on: patchwork sends"))
        self.assertIn("environment-created", FIRST_RUN_NOTICE)
        self.assertIn("https://trace.danielstephenson.dev", FIRST_RUN_NOTICE)
        self.assertIn('"enabled": false', FIRST_RUN_NOTICE)
        self.assertIn("settings.json", FIRST_RUN_NOTICE)
        self.assertIn("TRACE_USAGE_REPORTING=off", FIRST_RUN_NOTICE)
        self.assertIn(DETAILS_URL, FIRST_RUN_NOTICE)
        self.assertEqual("https://github.com/Stephenson-Software/trace#usage-reporting", DETAILS_URL)
        self.assertNotIn("\n", FIRST_RUN_NOTICE)

    def test_first_run_under_an_environment_opt_out_says_reporting_is_off(self):
        with patch.dict(os.environ, {"DO_NOT_TRACK": "1"}):
            section = loadSettings(self.settingsFile, self.log)

        self.assertEqual([FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT], self.logged)
        self.assertIn(DETAILS_URL, FIRST_RUN_NOTICE_OFF_BY_ENVIRONMENT)
        # the environment never rewrites the settings: the block is still the default
        self.assertEqual({"enabled": True, "endpoint": DEFAULT_ENDPOINT, "key": DEFAULT_KEY}, section)
        self.assertEqual({"usage_reporting": section}, self.readSettingsFile())

    def test_existing_settings_without_the_block_are_preserved(self):
        with open(self.settingsFile, "w") as f:
            json.dump({"other": {"kept": 1}}, f)

        loadSettings(self.settingsFile, self.log)

        written = self.readSettingsFile()
        self.assertEqual({"kept": 1}, written["other"])
        self.assertEqual(True, written["usage_reporting"]["enabled"])
        self.assertEqual([FIRST_RUN_NOTICE], self.logged)

    def test_opt_out_is_respected_and_not_rewritten(self):
        with open(self.settingsFile, "w") as f:
            json.dump({"usage_reporting": {"enabled": False}}, f)

        section = loadSettings(self.settingsFile, self.log)
        client = buildClient(section)

        self.assertFalse(client.enabled)
        self.assertEqual([], self.logged)
        self.assertEqual({"usage_reporting": {"enabled": False}}, self.readSettingsFile())

    def test_unreadable_settings_file_disables_reporting_without_raising(self):
        with open(self.settingsFile, "w") as f:
            f.write("{not json")

        section = loadSettings(self.settingsFile, self.log)
        client = buildClient(section)

        self.assertIsNone(section)
        self.assertFalse(client.enabled)
        self.assertEqual(1, len(self.logged))
        self.assertIn("usage reporting is off", self.logged[0])
        with open(self.settingsFile, "r") as f:
            self.assertEqual("{not json", f.read(), "a broken settings file must not be overwritten")

    def test_missing_endpoint_and_key_fall_back_to_the_shipped_defaults(self):
        # a settings.json written before the key shipped has no "key" entry and still reports
        client = buildClient({"enabled": True})

        self.assertTrue(client.enabled)
        self.assertEqual(DEFAULT_ENDPOINT + "/api/metrics", client._endpoint)
        self.assertEqual(DEFAULT_KEY, client._key)
        # nothing was reported, so close() sends nothing to the real service
        client.close()

    def test_a_key_is_shipped(self):
        self.assertEqual(43, len(DEFAULT_KEY))

    def test_settings_key_wins_over_the_shipped_key(self):
        client = buildClient({"enabled": True, "key": "settings-key"})

        self.assertEqual("settings-key", client._key)
        client.close()

    def test_environment_key_overrides_settings_and_the_shipped_key(self):
        with patch.dict(os.environ, {KEY_ENV_VAR: "runtime-key"}):
            client = buildClient({"enabled": True, "key": "settings-key"})

        self.assertTrue(client.enabled)
        self.assertEqual("runtime-key", client._key)
        client.close()

    def test_read_version_comes_from_version_txt(self):
        with open(os.path.join(os.path.dirname(usage_reporting.__file__), "version.txt"), "r") as f:
            expected = f.read().strip()

        self.assertEqual(expected, readVersion())
        self.assertIsNone(readVersion(os.path.join(self.tempDir.name, "missing.txt")))


class TestStartupEvent(unittest.TestCase):
    def setUp(self):
        self.tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempDir.cleanup)
        _scrubEnvironment(self)
        self.settingsFile = os.path.join(self.tempDir.name, "settings.json")
        self.requests = []
        self.arrived = threading.Event()
        self.server = _stubServer(self.requests, self.arrived)
        self.addCleanup(self.server.shutdown)
        self.endpoint = "http://127.0.0.1:%d" % self.server.server_address[1]

    def test_startup_event_reaches_the_configured_endpoint_with_name_and_version(self):
        with open(self.settingsFile, "w") as f:
            json.dump({"usage_reporting": {"enabled": True, "endpoint": self.endpoint}}, f)

        with patch("usage_reporting.atexit"), patch.dict(os.environ, {KEY_ENV_VAR: "test-key"}):
            client = startUsageReporting(self.settingsFile, lambda message: None)
        self.addCleanup(client.close)

        self.assertTrue(self.arrived.wait(5), "the startup event should reach the stub server")
        request = self.requests[0]
        self.assertEqual("/api/metrics", request["path"])
        self.assertEqual("Bearer test-key", request["authorization"])
        self.assertEqual({"application": "patchwork", "name": "startup", "tags": {"version": readVersion()}},
                         request["body"])

    def test_opted_out_startup_sends_nothing(self):
        with open(self.settingsFile, "w") as f:
            json.dump({"usage_reporting": {"enabled": False, "endpoint": self.endpoint}}, f)

        with patch("usage_reporting.atexit"), patch.dict(os.environ, {KEY_ENV_VAR: "test-key"}):
            client = startUsageReporting(self.settingsFile, lambda message: None)

        self.assertFalse(client.enabled)
        self.assertFalse(self.arrived.wait(0.3))
        self.assertEqual([], self.requests)

    def test_environment_opt_out_wins_over_enabled_settings_and_a_key(self):
        with open(self.settingsFile, "w") as f:
            json.dump({"usage_reporting": {"enabled": True, "endpoint": self.endpoint}}, f)

        for variable, value in (("DO_NOT_TRACK", "1"), ("TRACE_USAGE_REPORTING", "off")):
            with self.subTest(variable=variable):
                with patch("usage_reporting.atexit"), \
                        patch.dict(os.environ, {KEY_ENV_VAR: "test-key", variable: value}):
                    client = startUsageReporting(self.settingsFile, lambda message: None)

                self.assertFalse(client.enabled)
                self.assertEqual("environment", client.disabled_reason)
                self.assertFalse(self.arrived.wait(0.3))
                self.assertEqual([], self.requests)

    def test_start_never_raises_even_if_settings_loading_fails(self):
        with patch("usage_reporting.loadSettings", side_effect=RuntimeError("boom")):
            client = startUsageReporting(self.settingsFile, lambda message: None)

        self.assertFalse(client.enabled)


if __name__ == "__main__":
    unittest.main()
