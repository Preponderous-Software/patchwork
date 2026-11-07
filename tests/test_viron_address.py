import contextlib
import importlib
import io
import os
import sys
import unittest
from unittest.mock import patch

import viron_address


def readAddress(environment):
    """Return the address read from exactly these variables, along with what was printed."""
    output = io.StringIO()
    with patch.dict(os.environ, environment), contextlib.redirect_stdout(output):
        for name in (viron_address.URL_ENV_VAR, viron_address.PORT_ENV_VAR):
            if name not in environment:
                os.environ.pop(name, None)
        address = viron_address.getVironAddress()
    return address, output.getvalue()


class TestGetVironAddress(unittest.TestCase):
    def test_defaults_to_the_local_viron(self):
        address, output = readAddress({})

        self.assertEqual(address, ("http://localhost", 9999))
        self.assertEqual(output, "")

    def test_reads_the_url_and_the_port_from_the_environment(self):
        address, output = readAddress({"PATCHWORK_VIRON_URL": "https://viron.example",
                                       "PATCHWORK_VIRON_PORT": "8080"})

        self.assertEqual(address, ("https://viron.example", 8080))
        self.assertEqual(output, "")

    def test_each_variable_can_be_set_on_its_own(self):
        self.assertEqual(readAddress({"PATCHWORK_VIRON_URL": "http://viron"})[0], ("http://viron", 9999))
        self.assertEqual(readAddress({"PATCHWORK_VIRON_PORT": "8080"})[0], ("http://localhost", 8080))

    def test_an_empty_or_blank_variable_leaves_the_default(self):
        for value in ("", "   "):
            with self.subTest(value=value):
                address, output = readAddress({"PATCHWORK_VIRON_URL": value, "PATCHWORK_VIRON_PORT": value})

                self.assertEqual(address, ("http://localhost", 9999))
                self.assertEqual(output, "")

    def test_surrounding_whitespace_is_ignored(self):
        address, _ = readAddress({"PATCHWORK_VIRON_URL": " http://viron ", "PATCHWORK_VIRON_PORT": " 8080 "})

        self.assertEqual(address, ("http://viron", 8080))

    def test_a_trailing_slash_is_removed_from_the_url(self):
        address, _ = readAddress({"PATCHWORK_VIRON_URL": "http://viron/"})

        self.assertEqual(address, ("http://viron", 9999))

    def test_the_lowest_and_highest_ports_are_accepted(self):
        for value, port in (("1", 1), ("65535", 65535)):
            with self.subTest(value=value):
                address, output = readAddress({"PATCHWORK_VIRON_PORT": value})

                self.assertEqual(address, ("http://localhost", port))
                self.assertEqual(output, "")

    def test_an_invalid_port_falls_back_to_the_default_and_says_so(self):
        for value in ("http", "0", "-1", "65536", "99.5"):
            with self.subTest(value=value):
                address, output = readAddress({"PATCHWORK_VIRON_PORT": value})

                self.assertEqual(address, ("http://localhost", 9999))
                self.assertEqual(output, f"Invalid PATCHWORK_VIRON_PORT value {value!r}, using default of 9999.\n")

    def test_an_invalid_port_leaves_the_url_in_force(self):
        address, _ = readAddress({"PATCHWORK_VIRON_URL": "http://viron", "PATCHWORK_VIRON_PORT": "http"})

        self.assertEqual(address, ("http://viron", 9999))


class TestImport(unittest.TestCase):
    def test_the_module_can_be_imported_without_pygame(self):
        with patch.dict(sys.modules, {"pygame": None}):
            importlib.reload(viron_address)


if __name__ == "__main__":
    unittest.main()
