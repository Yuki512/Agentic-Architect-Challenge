from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from document_agent.config import (
    AgentConfig,
    AgentConfigurationError,
    build_chat_model,
    load_agent_config,
)


class AgentConfigTests(unittest.TestCase):
    def test_loads_deepseek_settings_from_env_file(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            env_path = Path(temp_directory) / ".env"
            env_path.write_text(
                "\n".join(
                    (
                        "QA_PROVIDER=deepseek",
                        "DEEPSEEK_API_KEY=test-key",
                        "DEEPSEEK_BASE_URL=https://api.example.test",
                        "DEEPSEEK_MODEL=test-model",
                        "DEEPSEEK_TIMEOUT_SECONDS=30",
                        "PART3_TIMEZONE=Asia/Singapore",
                    )
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_agent_config(env_path)

        self.assertEqual(config.provider, "deepseek")
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.base_url, "https://api.example.test")
        self.assertEqual(config.model, "test-model")
        self.assertEqual(config.timeout_seconds, 30)
        self.assertEqual(config.timezone_name, "Asia/Singapore")

    def test_environment_overrides_file(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            env_path = Path(temp_directory) / ".env"
            env_path.write_text(
                "DEEPSEEK_MODEL=file-model",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"DEEPSEEK_MODEL": "process-model"},
                clear=True,
            ):
                config = load_agent_config(env_path)

        self.assertEqual(config.model, "process-model")

    def test_rejects_unsupported_provider(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            env_path = Path(temp_directory) / ".env"
            env_path.write_text(
                "QA_PROVIDER=gemini",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    AgentConfigurationError,
                    "must be 'deepseek'",
                ):
                    load_agent_config(env_path)

    def test_rejects_invalid_timeout(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            env_path = Path(temp_directory) / ".env"
            env_path.write_text(
                "DEEPSEEK_TIMEOUT_SECONDS=2",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    AgentConfigurationError,
                    "between 5 and 120",
                ):
                    load_agent_config(env_path)

    def test_rejects_invalid_timezone(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            env_path = Path(temp_directory) / ".env"
            env_path.write_text(
                "PART3_TIMEZONE=Not/AZone",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    AgentConfigurationError,
                    "not recognized",
                ):
                    load_agent_config(env_path)

    def test_model_factory_requires_api_key(self):
        config = AgentConfig(
            provider="deepseek",
            api_key="",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=45,
            timezone_name="Asia/Singapore",
        )

        with self.assertRaisesRegex(
            AgentConfigurationError,
            "API_KEY is not configured",
        ):
            build_chat_model(config)

    def test_model_factory_builds_non_thinking_client(self):
        config = AgentConfig(
            provider="deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=45,
            timezone_name="Asia/Singapore",
        )

        model = build_chat_model(config)

        self.assertEqual(model.model_name, "deepseek-v4-flash")
        self.assertEqual(
            model.extra_body,
            {"thinking": {"type": "disabled"}},
        )


if __name__ == "__main__":
    unittest.main()
