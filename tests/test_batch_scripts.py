import os
import unittest

repositoryRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
batchScripts = ("up.bat", "down.bat", "create_environments.bat")


def readCommands(script):
    """
    Read a batch script's lines with REM comments and blank lines dropped, so that only
    what cmd.exe actually runs is asserted on.
    """
    with open(os.path.join(repositoryRoot, script), "r") as f:
        lines = [line.strip() for line in f]
    return [line for line in lines if line and not line.upper().startswith("REM ")]


class TestCommentSyntax(unittest.TestCase):
    """Regression coverage for '#' comment lines that cmd.exe runs as a command (#37)."""

    def test_no_line_is_a_hash_comment(self):
        for script in batchScripts:
            with self.subTest(script=script):
                with open(os.path.join(repositoryRoot, script), "r") as f:
                    hashLines = [number for number, line in enumerate(f, start=1)
                                 if line.lstrip().startswith("#")]
                self.assertEqual(hashLines, [], f"{script} has '#' lines; cmd.exe comments use REM")


class TestVironScripts(unittest.TestCase):
    """Characterizes the Compose commands that the README gives as the equivalents of up.bat and down.bat."""

    def test_up_builds_and_starts_viron_detached(self):
        self.assertEqual(readCommands("up.bat"),
                         [r"docker compose -f .\viron\compose.yml up -d --build"])

    def test_down_removes_orphans_and_deletes_the_volumes(self):
        self.assertEqual(readCommands("down.bat"),
                         [r"docker compose -f .\viron\compose.yml down --remove-orphans --volumes"])


class TestCreateEnvironments(unittest.TestCase):
    """Characterizes what the README says create_environments.bat does."""

    def setUp(self):
        self.commands = readCommands("create_environments.bat")

    def test_the_maximum_size_defaults_to_100_and_is_read_from_the_first_argument(self):
        self.assertIn('set "max_size=100"', self.commands)
        self.assertIn('set "max_size=%~1"', self.commands)

    def test_sizes_run_from_1_up_to_and_including_the_maximum(self):
        self.assertIn('set "size_of_next_env=1"', self.commands)
        self.assertIn('set "increment=1"', self.commands)
        self.assertIn("if !size_of_next_env! leq !max_size! (", self.commands)

    def test_environments_json_is_deleted_before_the_first_run(self):
        self.assertLess(self.commands.index("del environments.json"), self.commands.index(":loop"))

    def test_main_is_invoked_with_the_size_and_the_exit_after_create_flag(self):
        self.assertIn('set "script=main.py"', self.commands)
        self.assertIn("%python_executable% %script% !size_of_next_env! --exit-after-create"
                      " >> %output_file% 2>> %error_log_file%", self.commands)

    def test_the_flag_is_the_one_main_compares_its_second_argument_against(self):
        with open(os.path.join(repositoryRoot, "main.py"), "r") as f:
            self.assertIn('argv[2] == "--exit-after-create"', f.read())

    def test_output_and_errors_are_appended_to_their_own_files(self):
        self.assertIn('set "output_file=output.txt"', self.commands)
        self.assertIn('set "error_log_file=error_log.txt"', self.commands)

    def test_a_non_zero_exit_status_is_reported_as_an_error_for_that_size(self):
        errorCheck = self.commands.index("if errorlevel 1 (")
        self.assertEqual(self.commands[errorCheck + 1],
                         "echo Error occurred while running with size !size_of_next_env!.")
