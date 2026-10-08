import pytest
from app.rag.chunking import DocumentChunker, extract_text_from_bytes


def test_chunking_word_boundaries_and_metadata():
    chunker = DocumentChunker(chunk_size=10, chunk_overlap=2)
    sample_text = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12 word13 word14 word15"

    chunks = chunker.chunk_text(sample_text, base_metadata={"source": "test_doc.md"})
    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].meta_info["source"] == "test_doc.md"
    assert "word1" in chunks[0].content
    assert "word15" in chunks[1].content


def test_chunking_overlap_validation():
    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=50, chunk_overlap=50)


def test_extract_text_from_raw_bytes():
    raw_md = b"# Title\n\nContent of markdown."
    text = extract_text_from_bytes(raw_md, "runbook.md")
    assert "# Title" in text
    assert "Content of markdown." in text
