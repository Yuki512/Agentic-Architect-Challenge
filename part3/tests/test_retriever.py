import unittest

from document_agent import DocumentRetriever, load_policy_document


class DocumentRetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = DocumentRetriever(load_policy_document())

    def test_finds_accommodation_for_hotel_limit(self):
        result = self.retriever.retrieve(
            "What is the Singapore hotel limit?"
        )

        self.assertTrue(result.has_relevant_evidence)
        self.assertEqual(result.matches[0].section.citation_id, "P1:S3")
        self.assertIn("hotel", result.matches[0].matched_terms)

    def test_finds_transportation_for_personal_car_mileage(self):
        result = self.retriever.retrieve(
            "How much can I claim for personal car mileage?"
        )

        self.assertEqual(result.matches[0].section.citation_id, "P2:S5")
        self.assertIn("mileage", result.matches[0].matched_terms)

    def test_finds_claim_deadline(self):
        result = self.retriever.retrieve(
            "What is the receipt claim deadline?"
        )

        self.assertEqual(result.matches[0].section.citation_id, "P2:S6")

    def test_unrelated_query_returns_no_evidence(self):
        result = self.retriever.retrieve(
            "Who won the football championship?"
        )

        self.assertFalse(result.has_relevant_evidence)
        self.assertEqual(result.matches, ())

    def test_result_count_respects_top_k(self):
        result = self.retriever.retrieve(
            "approval claim expense manager",
            top_k=2,
        )

        self.assertLessEqual(len(result.matches), 2)

    def test_empty_query_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.retriever.retrieve("  ")

    def test_invalid_top_k_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "top_k must be between"):
            self.retriever.retrieve("hotel", top_k=0)


if __name__ == "__main__":
    unittest.main()
