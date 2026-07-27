from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from document_agent import DocumentRetriever, load_policy_document  # noqa: E402


DEFAULT_QUERIES = (
    "What is the Singapore hotel limit?",
    "How much can I claim for personal car mileage?",
    "When is an expense claim due?",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show BM25 evidence selected from the Part 3 policy PDF."
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Question to retrieve evidence for.",
    )
    args = parser.parse_args()
    queries = (" ".join(args.query),) if args.query else DEFAULT_QUERIES

    document = load_policy_document()
    retriever = DocumentRetriever(document)
    print(
        f"Loaded {len(document.sections)} sections "
        f"from {document.page_count} pages."
    )
    for query in queries:
        result = retriever.retrieve(query)
        print(f"\nQuery: {query}")
        if not result.matches:
            print("  No relevant evidence.")
            continue
        for match in result.matches:
            print(
                f"  [{match.section.citation_id}] "
                f"{match.section.title} "
                f"(score={match.score}, "
                f"terms={','.join(match.matched_terms)})"
            )


if __name__ == "__main__":
    main()
