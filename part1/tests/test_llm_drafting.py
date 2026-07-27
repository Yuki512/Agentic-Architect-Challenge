import json
import unittest
from unittest.mock import patch

from support_agent.classifier import classify_email
from support_agent.config import DraftLLMConfig
from support_agent.llm_drafting import (
    DeepSeekDraftError,
    draft_with_configured_provider,
    draft_with_deepseek,
)
from support_agent.subagents import route_to_subagent
from support_agent.tools import EvidencePassage, PDFSearchResult


EMAIL_CASE = {
    "customer_name": "Marcus",
    "subject": "Charged twice",
    "body": "I was charged twice for the same order.",
}
EVIDENCE_TEXT = (
    "The customer says they were charged twice. Ask for the order number, "
    "last four digits of the payment card, charge dates, and charge amounts."
)
SEARCH_RESULT = PDFSearchResult(
    query="charged twice",
    source_path="docs/nimbus_support_knowledge_base.pdf",
    found=True,
    passages=[
        EvidencePassage(
            source_path="docs/nimbus_support_knowledge_base.pdf",
            page_number=1,
            section="Billing FAQ",
            text=EVIDENCE_TEXT,
            score=10,
        )
    ],
)


class LLMDraftingTests(unittest.TestCase):
    def setUp(self):
        self.route = route_to_subagent(classify_email(EMAIL_CASE))
        self.config = DraftLLMConfig(
            provider="deepseek",
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=30,
        )

    def test_builds_grounded_dynamic_reply(self):
        reply = (
            "Hi Marcus, thanks for reaching out. To investigate the duplicate "
            "charge, please provide your order number, the last four digits of "
            "the payment card, and the charge dates and amounts."
        )

        def fake_transport(url, api_key, payload, timeout):
            self.assertEqual(url, "https://api.deepseek.com/chat/completions")
            self.assertEqual(api_key, "test-key")
            self.assertEqual(payload["model"], "deepseek-v4-flash")
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(timeout, 30)
            content = {
                "reply": reply,
                "source_evidence_ids": ["evidence-1"],
                "supporting_quotes": [EVIDENCE_TEXT],
            }
            return {
                "choices": [
                    {"message": {"content": json.dumps(content)}}
                ]
            }

        result = draft_with_deepseek(
            EMAIL_CASE,
            self.route,
            SEARCH_RESULT,
            config=self.config,
            transport=fake_transport,
        )

        self.assertEqual(result.status, "drafted")
        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.model, "deepseek-v4-flash")
        self.assertIn("order number", result.reply)
        self.assertEqual(len(result.evidence), 1)

    def test_rejects_number_absent_from_email_and_evidence(self):
        content = {
            "reply": (
                "Hi Marcus, the duplicate charge will be resolved within "
                "14 days after you provide the order number."
            ),
            "source_evidence_ids": ["evidence-1"],
            "supporting_quotes": [EVIDENCE_TEXT],
        }

        with self.assertRaisesRegex(DeepSeekDraftError, "number absent"):
            draft_with_deepseek(
                EMAIL_CASE,
                self.route,
                SEARCH_RESULT,
                config=self.config,
                transport=lambda *_args: {
                    "choices": [
                        {"message": {"content": json.dumps(content)}}
                    ]
                },
            )

    @patch("support_agent.llm_drafting.load_draft_llm_config")
    def test_missing_key_uses_template_fallback(self, config_loader):
        config_loader.return_value = DraftLLMConfig(
            provider="deepseek",
            api_key="",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=30,
        )

        result = draft_with_configured_provider(
            EMAIL_CASE,
            self.route,
            SEARCH_RESULT,
        )

        self.assertEqual(result.provider, "deterministic")
        self.assertIn("not configured", result.fallback_reason)
        self.assertIn("charged twice", result.reply.casefold())


if __name__ == "__main__":
    unittest.main()
