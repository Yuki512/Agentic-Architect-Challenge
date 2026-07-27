import json
import unittest
from unittest.mock import patch

from web_summary_agent.chunker import ContentChunk
from web_summary_agent.config import LLMConfig
from web_summary_agent.llm_summarizer import (
    GroundedPoint,
    check_llm_summary_guardrail,
    summarize_with_configured_provider,
    summarize_with_deepseek,
    summarize_with_gemini,
)


CHUNKS = (
    ContentChunk(
        "chunk-001",
        (
            "Tsunayoshi Sawada is the bearer of the Sky Ring and leads "
            "the Vongola family."
        ),
        15,
    ),
    ContentChunk(
        "chunk-002",
        (
            "Hayato Gokudera is Tsuna's Guardian of the Storm Ring and "
            "serves as his right-hand man."
        ),
        16,
    ),
)


class LLMSummarizerTests(unittest.TestCase):
    def setUp(self):
        self.config = LLMConfig(
            provider="deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=30,
        )

    def test_builds_grounded_deepseek_summary(self):
        def fake_transport(url, api_key, payload, timeout):
            self.assertEqual(url, "https://api.deepseek.com/chat/completions")
            self.assertEqual(api_key, "test-key")
            self.assertEqual(payload["model"], "deepseek-v4-flash")
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(timeout, 30)
            content = {
                "points": [
                    {
                        "text": (
                            "Tsunayoshi Sawada bears the Sky Ring and leads "
                            "the Vongola family."
                        ),
                        "source_chunk_ids": ["chunk-001"],
                    },
                    {
                        "text": (
                            "Hayato Gokudera is the Storm Ring Guardian and "
                            "Tsuna's right-hand man."
                        ),
                        "source_chunk_ids": ["chunk-002"],
                    },
                ]
            }
            return {
                "choices": [
                    {"message": {"content": json.dumps(content)}}
                ]
            }

        result = summarize_with_deepseek(
            CHUNKS,
            focus="List the Vongola members and Ring attributes.",
            max_words=60,
            config=self.config,
            transport=fake_transport,
        )

        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.model, "deepseek-v4-flash")
        self.assertEqual(result.guardrail.status, "passed")
        self.assertEqual(result.source_chunk_ids, ("chunk-001", "chunk-002"))

    def test_builds_grounded_gemini_summary(self):
        config = LLMConfig(
            provider="gemini",
            api_key="test-gemini-key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.0-flash",
            timeout_seconds=25,
        )

        def fake_transport(url, api_key, payload, timeout):
            self.assertEqual(
                url,
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.0-flash:generateContent",
            )
            self.assertEqual(api_key, "test-gemini-key")
            self.assertEqual(timeout, 25)
            self.assertEqual(
                payload["generationConfig"]["responseMimeType"],
                "application/json",
            )
            content = {
                "points": [
                    {
                        "text": (
                            "Tsunayoshi Sawada bears the Sky Ring and leads "
                            "the Vongola family."
                        ),
                        "source_chunk_ids": ["chunk-001"],
                    },
                    {
                        "text": (
                            "Hayato Gokudera is the Storm Ring Guardian and "
                            "Tsuna's right-hand man."
                        ),
                        "source_chunk_ids": ["chunk-002"],
                    },
                ]
            }
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(content)}]
                        }
                    }
                ]
            }

        result = summarize_with_gemini(
            CHUNKS,
            focus="List the Vongola members and Ring attributes.",
            max_words=60,
            config=config,
            transport=fake_transport,
        )

        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model, "gemini-2.0-flash")
        self.assertEqual(result.guardrail.status, "passed")
        self.assertEqual(result.source_chunk_ids, ("chunk-001", "chunk-002"))

    def test_guardrail_blocks_number_absent_from_cited_source(self):
        guardrail = check_llm_summary_guardrail(
            (
                GroundedPoint(
                    "Tsunayoshi Sawada became the Vongola boss in 2026.",
                    ("chunk-001",),
                ),
            ),
            CHUNKS,
            max_words=40,
        )

        self.assertEqual(guardrail.status, "blocked")
        self.assertIn("number", guardrail.reason)

    @patch("web_summary_agent.llm_summarizer.load_llm_config")
    def test_missing_key_uses_deterministic_fallback(self, config_loader):
        config_loader.return_value = LLMConfig(
            provider="deepseek",
            api_key="",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=30,
        )

        result = summarize_with_configured_provider(
            CHUNKS,
            focus="Vongola Ring attributes",
            max_words=60,
        )

        self.assertEqual(result.provider, "deterministic")
        self.assertIn("not configured", result.fallback_reason)
        self.assertEqual(result.guardrail.status, "passed")

    @patch("web_summary_agent.llm_summarizer.load_llm_config")
    def test_missing_gemini_key_uses_deterministic_fallback(self, config_loader):
        config_loader.return_value = LLMConfig(
            provider="gemini",
            api_key="",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.0-flash",
            timeout_seconds=25,
        )

        result = summarize_with_configured_provider(
            CHUNKS,
            focus="Vongola Ring attributes",
            max_words=60,
        )

        self.assertEqual(result.provider, "deterministic")
        self.assertIn("GEMINI_API_KEY", result.fallback_reason)
        self.assertEqual(result.guardrail.status, "passed")


if __name__ == "__main__":
    unittest.main()
