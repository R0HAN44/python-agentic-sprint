
import hashlib
import json


def generate_chunk_id(
    doc_id: str,
    page_number: int,
    section_path: list[str],
    content: str,
) -> str:
    identity = {
        "doc_id": doc_id,
        "page_number": page_number,
        "section_path": section_path,
        "content": content,
    }

    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
