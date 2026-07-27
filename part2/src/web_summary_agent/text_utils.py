import re


SENTENCE_BOUNDARY = re.compile(r"(?<=[!?])\s+|(?<=[^.]\.)\s+")


def split_sentences(value: str) -> list[str]:
    parts = [
        sentence.strip()
        for sentence in SENTENCE_BOUNDARY.split(value)
        if sentence.strip()
    ]
    sentences: list[str] = []
    for part in parts:
        if sentences and part[0].islower():
            sentences[-1] = f"{sentences[-1]} {part}"
        else:
            sentences.append(part)
    return sentences
