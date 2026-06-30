import unittest
from pathlib import Path
from unittest.mock import patch

from ym_to_apple.config import AppConfig


class ConfigPromptTests(unittest.TestCase):
    def test_prompts_missing_yandex_token(self) -> None:
        config = AppConfig.load("missing.env", interactive=True)
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", return_value="token"):
            self.assertEqual(config.require_yandex(), "token")

    def test_prompts_missing_apple_signing(self) -> None:
        config = AppConfig.load("missing.env", interactive=True)
        answers = iter(["TEAMID", "KEYID", __file__])
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=lambda _: next(answers)):
            team_id, key_id, key_path = config.require_apple_signing()
        self.assertEqual(team_id, "TEAMID")
        self.assertEqual(key_id, "KEYID")
        self.assertEqual(key_path, Path(__file__).expanduser())


if __name__ == "__main__":
    unittest.main()
