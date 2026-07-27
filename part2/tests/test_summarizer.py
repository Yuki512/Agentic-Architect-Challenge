import unittest

from web_summary_agent.chunker import ContentChunk
from web_summary_agent.summarizer import (
    SummaryError,
    check_summary_guardrail,
    summarize_chunks,
)


class SummarizerTests(unittest.TestCase):
    def test_creates_grounded_summary_within_limit(self):
        chunks = (
            ContentChunk(
                "chunk-001",
                (
                    "Python is a readable programming language.\n\n"
                    "It is widely used for web development and automation.\n\n"
                    "The language has a large open-source community."
                ),
                24,
            ),
        )

        result = summarize_chunks(
            chunks,
            focus="Explain Python benefits and applications.",
            max_words=40,
        )

        self.assertLessEqual(result.word_count, 40)
        self.assertEqual(result.guardrail.status, "passed")
        self.assertIn("Python", result.summary)
        self.assertIn("web development", result.summary)

    def test_deduplicates_overlap_between_chunks(self):
        repeated = "Python is easy to learn and useful for automation."
        chunks = (
            ContentChunk("chunk-001", repeated, 9),
            ContentChunk(
                "chunk-002",
                f"{repeated}\n\nPython also supports scientific software development.",
                15,
            ),
        )

        result = summarize_chunks(
            chunks,
            focus="Python benefits and scientific applications",
            max_words=40,
        )

        self.assertEqual(result.summary.count(repeated), 1)

    def test_focus_prioritizes_relevant_application_content(self):
        chunks = (
            ContentChunk(
                "chunk-001",
                (
                    "The community organizes conferences throughout the year.\n\n"
                    "Python supports web development, databases, automation, and scientific computing."
                ),
                17,
            ),
        )

        result = summarize_chunks(
            chunks,
            focus="common applications",
            max_words=12,
        )

        self.assertIn("web development", result.summary)
        self.assertNotIn("conferences", result.summary)

    def test_preserves_sentence_with_ellipsis(self):
        hero = "Python is powerful... and fast; friendly, easy to learn, and open."
        chunks = (
            ContentChunk(
                "chunk-001",
                f"{hero}\n\nFriendly and Easy to Learn",
                16,
            ),
        )

        result = summarize_chunks(
            chunks,
            focus="Python benefits",
            max_words=30,
        )

        self.assertIn(hero, result.points)
        self.assertNotIn("Friendly and Easy to Learn", result.points)

    def test_preserves_exclamation_mark_inside_title(self):
        introduction = (
            "Reborn!, also known as Hitman Reborn! for disambiguation purposes, "
            "is a Japanese manga series written by Akira Amano."
        )
        chunks = (ContentChunk("chunk-001", introduction, 18),)

        result = summarize_chunks(
            chunks,
            focus="Summarize the manga.",
            max_words=40,
        )

        self.assertIn(introduction, result.points)

    def test_review_sentence_is_deprioritized_when_reception_is_not_requested(self):
        chunks = (
            ContentChunk(
                "chunk-001",
                (
                    "The series follows Tsunayoshi Sawada as he trains to lead the "
                    "Vongola family.\n\n"
                    "According to one reviewer, the manga initially had a weak plot."
                ),
                25,
            ),
        )

        result = summarize_chunks(
            chunks,
            focus="Summarize the main story.",
            max_words=16,
        )

        self.assertIn("series follows Tsunayoshi", result.summary)
        self.assertNotIn("According to", result.summary)

    def test_guardrail_blocks_unsupported_text(self):
        chunks = (
            ContentChunk(
                "chunk-001",
                "Python is an open-source programming language.",
                6,
            ),
        )

        guardrail = check_summary_guardrail(
            ["Python guarantees every program is secure."],
            chunks,
            max_words=20,
        )

        self.assertEqual(guardrail.status, "blocked")
        self.assertIn("not supported", guardrail.reason)

    def test_guardrail_blocks_excessive_length(self):
        chunks = (
            ContentChunk(
                "chunk-001",
                "This source contains several grounded words for a summary.",
                9,
            ),
        )

        guardrail = check_summary_guardrail(
            ["This source contains several grounded words for a summary."],
            chunks,
            max_words=5,
        )

        self.assertEqual(guardrail.status, "blocked")
        self.assertIn("exceeds", guardrail.reason)

    def test_rejects_missing_content(self):
        with self.assertRaisesRegex(SummaryError, "No cleaned webpage content"):
            summarize_chunks((), focus="summary", max_words=100)


if __name__ == "__main__":
    unittest.main()
