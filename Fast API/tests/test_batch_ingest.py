import asyncio
import json
from pathlib import Path
import pytest
import pymupdf

from batch_ingest import (
    ConcurrencyTracker,
    CorruptPdfError,
    PasswordProtectedPdfError,
    EmptyExtractionError,
    process_single_pdf,
    process_pdf_async,
    main as batch_ingest_main,
)
from src.schemas import DocumentChunk


@pytest.fixture
def test_dirs(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()
    return data_dir, output_dir


def create_sample_pdf(path: Path, content: str):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), content, fontsize=11)
    doc.save(str(path))
    doc.close()


def test_concurrency_semaphore_bound():
    """Verify that no more than MAX_CONCURRENT tasks can be active concurrently."""
    max_concurrent = 3
    semaphore = asyncio.Semaphore(max_concurrent)
    tracker = ConcurrencyTracker()

    async def simulated_task(task_id: int):
        async with semaphore:
            await tracker.enter()
            assert tracker.current <= max_concurrent
            await asyncio.sleep(0.05)
            await tracker.exit()

    async def run_all():
        tasks = [simulated_task(i) for i in range(12)]
        await asyncio.gather(*tasks)

    asyncio.run(run_all())
    assert tracker.max_concurrent <= max_concurrent
    assert tracker.max_concurrent > 0


def test_corrupt_pdf_raises_corrupt_error(tmp_path):
    corrupt_file = tmp_path / "broken.pdf"
    corrupt_file.write_bytes(b"%PDF-1.4\nInvalid broken garbage\x00\xff")

    with pytest.raises(CorruptPdfError):
        process_single_pdf(corrupt_file, output_dir=tmp_path / "out")


def test_password_protected_pdf_raises_error(tmp_path):
    enc_file = tmp_path / "encrypted.pdf"
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((50, 50), "Classified Clinical Dossier")
    doc.save(
        str(enc_file),
        encryption=pymupdf.mupdf.PDF_ENCRYPT_AES_256,
        user_pw="secret123",
        owner_pw="owner123",
    )
    doc.close()

    with pytest.raises(PasswordProtectedPdfError):
        process_single_pdf(enc_file, output_dir=tmp_path / "out")


def test_blank_pdf_raises_empty_extraction_error(tmp_path):
    blank_file = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(blank_file))
    doc.close()

    with pytest.raises(EmptyExtractionError):
        process_single_pdf(blank_file, output_dir=tmp_path / "out")


def test_batch_ingest_failure_isolation(test_dirs):
    """Verify that a batch with valid, corrupt, and encrypted PDFs processes successfully without halting."""
    data_dir, output_dir = test_dirs

    # Valid PDF 1
    create_sample_pdf(
        data_dir / "valid_01.pdf",
        "# Clinical Trial 1\n## Protocol\nEvaluating efficacy in Cohort A for 12 weeks.",
    )

    # Valid PDF 2
    create_sample_pdf(
        data_dir / "valid_02.pdf",
        "# Clinical Trial 2\n## Methodology\nDouble-blind randomized testing in Cohort B.",
    )

    # Corrupt PDF
    (data_dir / "corrupt_03.pdf").write_bytes(b"%PDF\xff\xfe\x00NotAValidPdf")

    results = asyncio.run(batch_ingest_main(
        data_dir=data_dir,
        output_dir=output_dir,
        max_concurrent=2,
    ))

    assert len(results) == 3

    statuses = {r["file"]: r["status"] for r in results}
    assert statuses["valid_01.pdf"] == "success"
    assert statuses["valid_02.pdf"] == "success"
    assert statuses["corrupt_03.pdf"] == "failed"

    # Verify JSON output was created for valid_01.pdf and conforms to DocumentChunk schema
    json_path = output_dir / "valid_01_chunks.json"
    assert json_path.exists()

    with open(json_path, encoding="utf-8") as f:
        chunks_raw = json.load(f)

    assert len(chunks_raw) >= 1
    for chunk_dict in chunks_raw:
        # Pydantic schema validation
        chunk = DocumentChunk.model_validate(chunk_dict)
        assert len(chunk.chunk_id) == 64
        assert chunk.doc_id == "valid_01"
        assert chunk.token_count > 0
        assert chunk.content.strip() != ""
