import json
import unittest

from support_agent.config import DraftLLMConfig
from support_agent.semantic_critical import (
    SemanticCriticalError,
    check_semantic_critical_with_deepseek,
)


CONFIG = DraftLLMConfig(
    provider="deepseek",
    api_key="test-key",
    base_url="https://api.deepseek.com",
    model="deepseek-v4-flash",
    timeout_seconds=30,
)


def deepseek_response(content):
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content),
                }
            }
        ]
    }


class SemanticCriticalTests(unittest.TestCase):
    def test_detects_data_loss_paraphrase_with_email_evidence(self):
        def transport(_url, _key, payload, _timeout):
            self.assertEqual(payload["temperature"], 0)
            return deepseek_response(
                {
                    "decision": "critical",
                    "condition": "data_loss",
                    "confidence": 0.96,
                    "evidence": "All saved customer records vanished overnight",
                    "reason": "The email reports that stored records disappeared.",
                }
            )

        result = check_semantic_critical_with_deepseek(
            {
                "subject": "Customer records disappeared",
                "body": "All saved customer records vanished overnight.",
            },
            config=CONFIG,
            transport=transport,
        )

        self.assertEqual(result.status, "critical")
        self.assertTrue(result.requires_human_review)
        self.assertEqual(result.matched_condition, "data_loss")

    def test_low_confidence_noncritical_result_becomes_uncertain(self):
        result = check_semantic_critical_with_deepseek(
            {
                "subject": "Account question",
                "body": "I noticed something unusual in my account.",
            },
            config=CONFIG,
            transport=lambda *_args: deepseek_response(
                {
                    "decision": "non_critical",
                    "condition": "none",
                    "confidence": 0.55,
                    "evidence": "",
                    "reason": "The email does not clearly describe an incident.",
                }
            ),
        )

        self.assertEqual(result.status, "uncertain")
        self.assertTrue(result.requires_human_review)

    def test_high_confidence_noncritical_result_continues(self):
        result = check_semantic_critical_with_deepseek(
            {
                "subject": "Refund question",
                "body": "Can I return an unused item?",
            },
            config=CONFIG,
            transport=lambda *_args: deepseek_response(
                {
                    "decision": "non_critical",
                    "condition": "none",
                    "confidence": 0.98,
                    "evidence": "",
                    "reason": "This is an ordinary refund question.",
                }
            ),
        )

        self.assertEqual(result.status, "non_critical")
        self.assertFalse(result.requires_human_review)

    def test_rejects_critical_evidence_absent_from_email(self):
        with self.assertRaisesRegex(
            SemanticCriticalError,
            "evidence is absent",
        ):
            check_semantic_critical_with_deepseek(
                {
                    "subject": "Account question",
                    "body": "I cannot update my profile.",
                },
                config=CONFIG,
                transport=lambda *_args: deepseek_response(
                    {
                        "decision": "critical",
                        "condition": "security_breach",
                        "confidence": 0.99,
                        "evidence": "An attacker stole all customer passwords",
                        "reason": "This reports a security breach.",
                    }
                ),
            )

    def test_rejects_unknown_condition(self):
        with self.assertRaisesRegex(
            SemanticCriticalError,
            "unsupported critical condition",
        ):
            check_semantic_critical_with_deepseek(
                {
                    "subject": "Payment issue",
                    "body": "My payment was declined.",
                },
                config=CONFIG,
                transport=lambda *_args: deepseek_response(
                    {
                        "decision": "critical",
                        "condition": "payment_failure",
                        "confidence": 0.95,
                        "evidence": "My payment was declined",
                        "reason": "Payment failed.",
                    }
                ),
            )


if __name__ == "__main__":
    unittest.main()
