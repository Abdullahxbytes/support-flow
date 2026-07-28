"""Text document chunking utility for knowledge base ingestion.

Splits incoming documents (Markdown, Plain Text, JSON) into semantic,
overlapping text chunks while tracking structural metadata such as
section headers and paragraph boundaries.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocumentChunk:
    """Dataclass representing a single chunk extracted from a document.

    Attributes
    ----------
    chunk_index:
        Zero-based index of this chunk within the source document.
    content:
        The text payload of the chunk.
    header_context:
        Associated section header or topic context (if detected).
    char_count:
        Length of chunk text in characters.
    """

    chunk_index: int
    content: str
    header_context: Optional[str] = None
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.content)


class DocumentChunker:
    """Configurable text chunker preserving header and paragraph boundaries."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_length: int = 20,
    ) -> None:
        """Initialize chunker options.

        Parameters
        ----------
        chunk_size:
            Target max character length per chunk (default: 500).
        chunk_overlap:
            Character overlap between adjacent chunks (default: 50).
        min_chunk_length:
            Minimum character length to keep a chunk (default: 20).
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length

    def chunk_text(
        self, text: str, doc_type: str = "markdown"
    ) -> list[DocumentChunk]:
        """Split text into overlapping chunks with header and paragraph preservation.

        Parameters
        ----------
        text:
            The raw string document content.
        doc_type:
            Format type ('markdown', 'text', 'json', etc.).

        Returns
        -------
        list[DocumentChunk]
            Extracted document chunks with index and structural metadata.
        """
        if not text or not text.strip():
            return []

        clean_text = text.strip()

        # Extract markdown headers if present
        if doc_type.lower() in ("markdown", "md"):
            return self._chunk_markdown(clean_text)

        return self._chunk_generic(clean_text)

    def _chunk_markdown(self, text: str) -> list[DocumentChunk]:
        """Chunk markdown text, tracking current active header context."""
        header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

        sections: list[tuple[Optional[str], str]] = []
        last_pos = 0
        current_header: Optional[str] = None

        for match in header_pattern.finditer(text):
            start = match.start()
            if start > last_pos:
                section_body = text[last_pos:start].strip()
                if section_body:
                    sections.append((current_header, section_body))

            current_header = match.group(2).strip()
            last_pos = match.end()

        if last_pos < len(text):
            section_body = text[last_pos:].strip()
            if section_body:
                sections.append((current_header, section_body))

        if not sections:
            sections = [(None, text)]

        chunks: list[DocumentChunk] = []
        chunk_index = 0

        for header, body in sections:
            sub_chunks = self._sliding_window_split(body)
            for sub_text in sub_chunks:
                if len(sub_text.strip()) >= self.min_chunk_length:
                    chunks.append(
                        DocumentChunk(
                            chunk_index=chunk_index,
                            content=sub_text.strip(),
                            header_context=header,
                        )
                    )
                    chunk_index += 1

        return chunks

    def _chunk_generic(self, text: str) -> list[DocumentChunk]:
        """Chunk plain text or JSON content using paragraph-aware sliding window."""
        sub_chunks = self._sliding_window_split(text)
        chunks: list[DocumentChunk] = []

        for index, sub_text in enumerate(sub_chunks):
            if len(sub_text.strip()) >= self.min_chunk_length:
                chunks.append(
                    DocumentChunk(
                        chunk_index=len(chunks),
                        content=sub_text.strip(),
                        header_context=None,
                    )
                )

        return chunks

    def _sliding_window_split(self, text: str) -> list[str]:
        """Split text into segments of ~chunk_size with ~chunk_overlap."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        raw_blocks: list[str] = []
        for p in paragraphs:
            if len(p) <= self.chunk_size:
                raw_blocks.append(p)
            else:
                # Split long paragraphs on sentences or linebreaks
                lines = re.split(r"(?<=[.!?])\s+|\n", p)
                current_block = ""
                for line in lines:
                    if len(current_block) + len(line) + 1 <= self.chunk_size:
                        current_block = (
                            f"{current_block} {line}".strip()
                            if current_block
                            else line
                        )
                    else:
                        if current_block:
                            raw_blocks.append(current_block)
                        current_block = line
                if current_block:
                    raw_blocks.append(current_block)

        # Merge blocks into sliding window chunks
        chunks: list[str] = []
        current_chunk = ""

        for block in raw_blocks:
            if not current_chunk:
                current_chunk = block
            elif len(current_chunk) + len(block) + 2 <= self.chunk_size:
                current_chunk = f"{current_chunk}\n\n{block}"
            else:
                chunks.append(current_chunk)
                # Apply overlap by taking trailing portion of previous chunk
                overlap_text = current_chunk[-self.chunk_overlap :] if len(current_chunk) > self.chunk_overlap else ""
                current_chunk = f"{overlap_text}\n\n{block}".strip()

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
