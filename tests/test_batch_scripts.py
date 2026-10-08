import os
import unittest

repositoryRoot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
batchScripts = ("up.bat", "down.bat", "create_environments.bat")


class TestCommentSyntax(unittest.TestCase):
    """Regression coverage for '#' comment lines that cmd.exe runs as a command (#37)."""

    def test_no_line_is_a_hash_comment(self):
        for script in batchScripts:
            with self.subTest(script=script):
                with open(os.path.join(repositoryRoot, script), "r") as f:
                    hashLines = [number for number, line in enumerate(f, start=1)
                                 if line.lstrip().startswith("#")]
                self.assertEqual(hashLines, [], f"{script} has '#' lines; cmd.exe comments use REM")
