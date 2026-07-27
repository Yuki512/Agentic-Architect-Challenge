from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from web_summary_agent.config import load_llm_config


class ConfigTests(unittest.TestCase):
    def test_loads_deepseek_settings_from_env_file(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "SUMMARY_PROVIDER=deepseek",
                        "DEEPSEEK_API_KEY=test-key",
                        "DEEPSEEK_BASE_URL=https://api.deepseek.com",
                        "DEEPSEEK_MODEL=deepseek-v4-flash",
                        "DEEPSEEK_TIMEOUT_SECONDS=30",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True):
                config = load_llm_config(env_path)

        self.assertTrue(config.deepseek_enabled)
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.model, "deepseek-v4-flash")
        self.assertEqual(config.timeout_seconds, 30)

    def test_environment_setting_overrides_env_file(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "SUMMARY_PROVIDER=deterministic\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"SUMMARY_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "runtime-key"},
                clear=True,
            ):
                config = load_llm_config(env_path)

        self.assertEqual(config.provider, "deepseek")
        self.assertEqual(config.api_key, "runtime-key")

    def test_loads_gemini_settings_from_env_file(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "SUMMARY_PROVIDER=gemini",
                        "GEMINI_API_KEY=test-gemini-key",
                        "GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta",
                        "GEMINI_MODEL=gemini-2.0-flash",
                        "GEMINI_TIMEOUT_SECONDS=25",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True):
                config = load_llm_config(env_path)

        self.assertTrue(config.gemini_enabled)
        self.assertEqual(config.provider, "gemini")
        self.assertEqual(config.api_key, "test-gemini-key")
        self.assertEqual(config.model, "gemini-2.0-flash")
        self.assertEqual(config.timeout_seconds, 25)


if __name__ == "__main__":
    unittest.main()
