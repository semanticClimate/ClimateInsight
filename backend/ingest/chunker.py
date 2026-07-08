"""
chunker.py
----------
Split Sections into overlapping chunks.
"""

from .models import Section, Chunk


def chunk_records(
    records: list[Section],
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:

    chunks = []

    chunk_index = 0

    for record in records:

        words = record.text.split()

        if len(words) <= chunk_size:

            chunks.append(
                Chunk(
                    chunk_id=f"{record.section or 'nosec'}__chunk_{chunk_index}",
                    text=record.text,
                    section=record.section,
                    section_title=record.section_title,
                )
            )

            chunk_index += 1
            continue

        start = 0

        while start < len(words):

            end = min(start + chunk_size, len(words))

            chunk_text = " ".join(words[start:end])

            chunks.append(
                Chunk(
                    chunk_id=f"{record.section or 'nosec'}__chunk_{chunk_index}",
                    text=chunk_text,
                    section=record.section,
                    section_title=record.section_title,
                )
            )

            chunk_index += 1

            start += chunk_size - overlap

    print(f"Created {len(chunks)} chunks.")

    with open("chunks.txt", "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write("=" * 80 + "\n")
            f.write(f"{chunk.chunk_id}\n")
            f.write(f"Section: {chunk.section}\n")
            f.write(f"Title: {chunk.section_title}\n")
            f.write("=" * 80 + "\n")
            f.write(chunk.text)
            f.write("\n\n")

    return chunks