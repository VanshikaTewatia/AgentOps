import io
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from pypdf import PdfReader


class TextChunk(BaseModel):
    chunk_index: int
    content: str
    meta_info: Dict[str, Any] = {}


class DocumentChunker:
    """Configurable text chunker preserving paragraph structure and metadata."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, base_metadata: Optional[Dict[str, Any]] = None) -> List[TextChunk]:
        clean_text = text.strip()
        if not clean_text:
            return []

        # Split into logical paragraphs / sections
        raw_sections = re.split(r"(\n#{1,6} [^\n]+\n|\n\n+)", clean_text)
        sections: List[str] = []
        for s in raw_sections:
            if s and not s.isspace():
                sections.append(s)

        chunks: List[TextChunk] = []
        current_chunk_words: List[str] = []
        current_len = 0
        chunk_idx = 0

        words = clean_text.split()
        if not words:
            return []

        # Chunk by word length to maintain coherent boundaries
        step = max(1, self.chunk_size - self.chunk_overlap)
        i = 0
        while i < len(words):
            chunk_words = words[i : i + self.chunk_size]
            chunk_content = " ".join(chunk_words)
            meta = dict(base_metadata or {})
            meta["word_count"] = len(chunk_words)
            meta["start_word_idx"] = i
            meta["end_word_idx"] = min(len(words), i + self.chunk_size)

            chunks.append(
                TextChunk(
                    chunk_index=chunk_idx,
                    content=chunk_content,
                    meta_info=meta,
                )
            )
            chunk_idx += 1
            i += step

        return chunks


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """Extract raw text from .txt, .md, or .pdf file bytes."""
    lower_filename = filename.lower()
    if lower_filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        extracted_pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            if page_text.strip():
                extracted_pages.append(f"--- Page {i+1} ---\n{page_text.strip()}")
        return "\n\n".join(extracted_pages)
    else:
        # Default utf-8 text / markdown decoding
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="replace")
