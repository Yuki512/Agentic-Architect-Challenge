import json
import unittest
from unittest.mock import patch

from support_agent.config import DraftLLMConfig
from support_agent.router_agent import (
    RouterAgentError,
    classify_with_configured_router,
    classify_with_deepseek,
)


class RouterAgentTests(unittest.TestCase):
    def setUp(self):
        self.config = DraftLLMConfig(
            provider="deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.test",
            model="deepseek-test",
            timeout_seconds=15,
        )

    def test_deepseek_router_returns_valid_category(self):
        captured = {}

        def transport(url, api_key, payload, timeout):
            captured.update(
                url=url,
                api_key=api_key,
                payload=payload,
                timeout=timeout,
            )
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "primary_category": "Technical",
                                    "categories": ["Technical"],
                                    "confidence": 0.97,
                                    "reason": (
                                        "The customer reports an app crash."
                                    ),
                                }
                            )
                        }
                    }
                ]
            }

        result = classify_with_deepseek(
            {
                "subject": "App crashed",
                "body": "My saved details disappeared.",
            },
            config=self.config,
            transport=transport,
        )

        self.assertEqual(result.primary_category, "Technical")
        self.assertEqual(result.recommended_subagent, "TechnicalSubagent")
        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(captured["payload"]["temperature"], 0)

    def test_router_rejects_unknown_category(self):
        def transport(*_args):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "primary_category": "Legal",
                                    "categories": ["Legal"],
                                    "confidence": 0.9,
                                    "reason": "Unsupported category.",
                                }
                            )
                        }
                    }
                ]
            }

        with self.assertRaises(RouterAgentError):
            classify_with_deepseek(
                {
                    "subject": "Question",
                    "body": "Please help.",
                },
                config=self.config,
                transport=transport,
            )

    @patch("support_agent.router_agent.load_router_llm_config")
    def test_missing_key_uses_keyword_fallback(self, load_config):
        load_config.return_value = DraftLLMConfig(
            provider="deepseek",
            api_key="",
            base_url="https://api.deepseek.test",
            model="deepseek-test",
            timeout_seconds=15,
        )

        result = classify_with_configured_router(
            {
                "subject": "Charged twice",
                "body": "There is a duplicate card payment.",
            }
        )

        self.assertEqual(result.primary_category, "Billing")
        self.assertEqual(result.provider, "deterministic")
        self.assertIn("API_KEY", result.fallback_reason)


if __name__ == "__main__":
    unittest.main()
