
from src.utils.build_chunk import build_chunk
import pytest
from pydantic import ValidationError




def make_chunk(content="Drug A was given for 12 weeks."):
    return build_chunk(
        doc_id="trial-001",
        page_number=7,
        section_path=["Methods", "Dosage"],
        content=content,
        token_count=10,
    )


def test_same_input_produces_same_id():
    first = make_chunk()
    second = make_chunk()

    assert first.chunk_id == second.chunk_id


def test_changed_content_produces_different_id():
    first = make_chunk("Drug A was given for 12 weeks.")
    second = make_chunk("Drug A was given for 16 weeks.")

    assert first.chunk_id != second.chunk_id


def test_empty_content_is_rejected():
    with pytest.raises(ValidationError):
        make_chunk("   ")


def test_invalid_page_is_rejected():
    with pytest.raises(ValidationError):
        build_chunk(
            doc_id="trial-001",
            page_number=0,
            section_path=["Methods"],
            content="Valid content",
            token_count=5,
        )


def test_unicode_content_is_supported():
    first = make_chunk("Tratamiento: 20 mg — café")
    second = make_chunk("Tratamiento: 20 mg — café")

    assert first.content == second.content
    assert first.chunk_id == second.chunk_id
