from pathlib import Path
import tempfile
import unittest

from document_agent.document_loader import (
    DEFAULT_DOCUMENT_PATH,
    DocumentLoadError,
    load_policy_document,
)


class DocumentLoaderTests(unittest.TestCase):
    def test_loads_overview_and_eight_policy_sections(self):
        document = load_policy_document()

        self.assertEqual(document.page_count, 2)
        self.assertEqual(len(document.sections), 9)
        self.assertEqual(
            tuple(section.citation_id for section in document.sections),
            (
                "P1:S0",
                "P1:S1",
                "P1:S2",
                "P1:S3",
                "P1:S4",
                "P2:S5",
                "P2:S6",
                "P2:S7",
                "P2:S8",
            ),
        )

    def test_preserves_policy_facts_and_removes_page_chrome(self):
        document = load_policy_document()
        combined_text = "\n".join(
            section.text for section in document.sections
        )

        self.assertIn("S$240 per night", combined_text)
        self.assertIn("S$0.70 per business kilometre", combined_text)
        self.assertIn("20 August 2026", combined_text)
        self.assertNotIn("NIMBUS FINANCE OPERATIONS", combined_text)
        self.assertNotIn("Internal policy Page", combined_text)

    def test_overview_contains_metadata(self):
        overview = load_policy_document().sections[0]

        self.assertEqual(overview.title, "Policy overview")
        self.assertIn("NIM-FIN-TRV-2026-01", overview.text)
        self.assertIn("1 July 2026", overview.text)

    def test_missing_document_raises_clear_error(self):
        missing = DEFAULT_DOCUMENT_PATH.with_name("missing-policy.pdf")

        with self.assertRaisesRegex(
            DocumentLoadError,
            "Policy PDF was not found",
        ):
            load_policy_document(missing)

    def test_non_pdf_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            path = Path(temp_directory) / "policy.txt"
            path.write_text("not a PDF", encoding="utf-8")

            with self.assertRaisesRegex(
                DocumentLoadError,
                "must be a PDF",
            ):
                load_policy_document(path)


if __name__ == "__main__":
    unittest.main()
