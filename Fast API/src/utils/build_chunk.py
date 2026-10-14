
from ..schemas import DocumentChunk
from .chunk_ids import generate_chunk_id


def build_chunk(
    doc_id: str,
    page_number: int,
    section_path: list[str],
    content: str,
    token_count: int,
) -> DocumentChunk:
    chunk_id = generate_chunk_id(
        doc_id=doc_id,
        page_number=page_number,
        section_path=section_path,
        content=content,
    )

    return DocumentChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        page_number=page_number,
        section_path=section_path,
        content=content,
        token_count=token_count,
    )

