from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from support_agent.config import load_draft_llm_config


class DraftConfigTests(unittest.TestCase):
    def test_loads_deepseek_settings_from_env_file(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DRAFT_PROVIDER=deepseek",
                        "DEEPSEEK_API_KEY=test-key",
                        "DEEPSEEK_BASE_URL=https://api.deepseek.com",
                        "DEEPSEEK_MODEL=deepseek-v4-flash",
                        "DEEPSEEK_TIMEOUT_SECONDS=30",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {}, clear=True):
                config = load_draft_llm_config(env_path)

        self.assertTrue(config.deepseek_enabled)
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.model, "deepseek-v4-flash")
        self.assertEqual(config.timeout_seconds, 30)

    def test_environment_setting_overrides_env_file(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            env_path.write_text(
                "DRAFT_PROVIDER=deterministic\n",
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {"DRAFT_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "runtime-key"},
                clear=True,
            ):
                config = load_draft_llm_config(env_path)

        self.assertEqual(config.provider, "deepseek")
        self.assertEqual(config.api_key, "runtime-key")


if __name__ == "__main__":
    unittest.main()

