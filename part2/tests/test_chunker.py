import unittest

from web_summary_agent.chunker import chunk_cleaned_page
from web_summary_agent.content_cleaner import CleanedPage


def make_cleaned_page(blocks: list[str]) -> CleanedPage:
    text = "\n\n".join(blocks)
    return CleanedPage(
        source_url="https://example.com/article",
        title="Example Article",
        text=text,
        blocks=tuple(blocks),
        word_count=len(text.split()),
        block_count=len(blocks),
        used_primary_content=True,
        duplicate_blocks_removed=0,
    )


class ChunkerTests(unittest.TestCase):
    def test_short_page_stays_in_one_chunk(self):
        page = make_cleaned_page(
            [
                "A short heading",
                "This article contains a concise paragraph with useful information.",
            ]
        )

        chunks = chunk_cleaned_page(page, max_words=80, overlap_words=10)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "chunk-001")
        self.assertEqual(chunks[0].word_count, page.word_count)

    def test_long_page_creates_limited_chunks(self):
        blocks = [
            f"Section {index} contains " + " ".join(f"word{index}" for _ in range(32)) + "."
            for index in range(8)
        ]
        page = make_cleaned_page(blocks)

        chunks = chunk_cleaned_page(page, max_words=80, overlap_words=10)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.word_count <= 80 for chunk in chunks))

    def test_sentence_overlap_preserves_context(self):
        first = " ".join(["first"] * 18) + "."
        second = " ".join(["second"] * 18) + "."
        third = " ".join(["third"] * 18) + "."
        page = make_cleaned_page([first, second, third])

        chunks = chunk_cleaned_page(page, max_words=40, overlap_words=19)

        self.assertEqual(len(chunks), 2)
        self.assertIn(second, chunks[0].text)
        self.assertIn(second, chunks[1].text)

    def test_oversized_sentence_is_split(self):
        page = make_cleaned_page([" ".join(["long"] * 95)])

        chunks = chunk_cleaned_page(page, max_words=40, overlap_words=0)

        self.assertEqual([chunk.word_count for chunk in chunks], [40, 40, 15])

    def test_ellipsis_does_not_split_one_thought(self):
        page = make_cleaned_page(
            ["Python is powerful... and fast; friendly, easy to learn, and open."]
        )

        chunks = chunk_cleaned_page(page, max_words=40, overlap_words=0)

        self.assertEqual(len(chunks), 1)
        self.assertIn("Python is powerful... and fast", chunks[0].text)

    def test_empty_page_returns_no_chunks(self):
        page = make_cleaned_page([])

        self.assertEqual(chunk_cleaned_page(page), ())

    def test_rejects_excessive_overlap(self):
        page = make_cleaned_page(["Useful content remains here."])

        with self.assertRaisesRegex(ValueError, "less than half"):
            chunk_cleaned_page(page, max_words=80, overlap_words=40)


if __name__ == "__main__":
    unittest.main()
