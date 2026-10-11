import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in python path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from docling.document_converter import DocumentConverter
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pymupdf
from tqdm.asyncio import tqdm

from src.schemas import DocumentChunk
from src.utils.build_chunk import build_chunk

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("batch_ingest")

DATA_DIR = CURRENT_DIR / "data"
OUTPUT_DIR = CURRENT_DIR / "output"
MAX_CONCURRENT = 3


# Custom exception hierarchy for PDF failure isolation
class IngestionError(Exception):
    """Base exception for PDF ingestion errors."""
    pass


class CorruptPdfError(IngestionError):
    """Raised when a PDF is unreadable, has invalid structure, or is corrupted."""
    pass


class PasswordProtectedPdfError(IngestionError):
    """Raised when a PDF is encrypted and requires a password."""
    pass


class EmptyExtractionError(IngestionError):
    """Raised when extraction produces empty or negligible text (e.g. non-OCR scanned page)."""
    pass


class ConcurrencyTracker:
    """Tracks active and peak concurrent execution within protected sections."""

    def __init__(self):
        self._current = 0
        self._max = 0
        self._lock = asyncio.Lock()

    async def enter(self):
        async with self._lock:
            self._current += 1
            if self._current > self._max:
                self._max = self._current

    async def exit(self):
        async with self._lock:
            self._current -= 1

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def current(self) -> int:
        return self._current


def precheck_pdf(pdf_path: Path) -> None:
    """Fast inspection for corruption and password protection using PyMuPDF."""
    try:
        doc = pymupdf.open(str(pdf_path))
        if doc.is_encrypted:
            doc.close()
            raise PasswordProtectedPdfError(
                f"PDF '{pdf_path.name}' is password-protected and requires decryption credentials."
            )
        if len(doc) == 0:
            doc.close()
            raise CorruptPdfError(f"PDF '{pdf_path.name}' contains 0 pages.")
        doc.close()
    except PasswordProtectedPdfError:
        raise
    except pymupdf.FileDataError as exc:
        raise CorruptPdfError(f"PDF '{pdf_path.name}' is corrupt or unreadable: {exc}") from exc
    except Exception as exc:
        err = str(exc).lower()
        if "encrypted" in err or "password" in err:
            raise PasswordProtectedPdfError(f"PDF '{pdf_path.name}' is password-protected.") from exc
        raise CorruptPdfError(f"Failed opening PDF '{pdf_path.name}': {exc}") from exc


def extract_markdown(pdf_path: Path) -> str:
    """Converts PDF to structured Markdown using Docling."""
    precheck_pdf(pdf_path)

    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        markdown_text = result.document.export_to_markdown()
    except IngestionError:
        raise
    except Exception as exc:
        err = str(exc).lower()
        if "password" in err or "encrypt" in err:
            raise PasswordProtectedPdfError(f"Decryption error in '{pdf_path.name}': {exc}") from exc
        raise CorruptPdfError(f"Docling conversion failed for '{pdf_path.name}': {exc}") from exc

    if not markdown_text or len(markdown_text.strip()) < 20:
        raise EmptyExtractionError(
            f"Extracted content from '{pdf_path.name}' is empty or negligible "
            f"({len(markdown_text.strip())} characters). Scanned document may require OCR or is blank."
        )

    return markdown_text


def chunk_document(
    markdown_text: str,
    doc_id: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 150,
) -> list[DocumentChunk]:
    """Splits markdown into context-aware chunks validated by DocumentChunk Pydantic model."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )

    splits = splitter.split_text(markdown_text)
    chunks: list[DocumentChunk] = []
    current_section = ["General"]

    for piece in splits:
        cleaned = piece.strip()
        if not cleaned:
            continue

        # Detect active section header breadcrumb
        for line in cleaned.splitlines():
            sline = line.strip()
            if sline.startswith("## "):
                current_section = [sline.lstrip("#").strip()]
                break
            elif sline.startswith("### "):
                parent = current_section[0] if current_section else "General"
                current_section = [parent, sline.lstrip("#").strip()]
                break

        # Token count estimate (Day 18/19 schema requirement: token_count > 0)
        tokens = max(1, len(cleaned.split()))

        chunk = build_chunk(
            doc_id=doc_id,
            page_number=1,
            section_path=current_section,
            content=cleaned,
            token_count=tokens,
        )
        chunks.append(chunk)

    if not chunks:
        raise EmptyExtractionError(f"No valid chunks generated for document '{doc_id}'.")

    return chunks


def process_single_pdf(pdf_path: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    """Synchronous pipeline worker: Parse -> Chunk -> Validate -> Save JSON."""
    doc_id = pdf_path.stem
    markdown_text = extract_markdown(pdf_path)
    chunks = chunk_document(markdown_text, doc_id=doc_id)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{doc_id}_chunks.json"

    serialized = [chunk.model_dump() for chunk in chunks]
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)

    return {
        "chunk_count": len(chunks),
        "output_file": str(out_file),
    }


async def process_pdf_async(
    pdf_path: Path,
    semaphore: asyncio.Semaphore,
    tracker: ConcurrencyTracker,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    """Asynchronous worker with semaphore gating and individual failure isolation."""
    async with semaphore:
        await tracker.enter()
        logger.info("Processing %s (Active tasks: %d)", pdf_path.name, tracker.current)
        try:
            # Delegate blocking CPU-bound parsing to worker thread
            result = await asyncio.to_thread(process_single_pdf, pdf_path, output_dir)
            return {
                "file": pdf_path.name,
                "status": "success",
                "chunks": result["chunk_count"],
                "output_file": result["output_file"],
            }
        except Exception as exc:
            logger.exception("Failed to process %s", pdf_path.name)
            return {
                "file": pdf_path.name,
                "status": "failed",
                "error": f"{type(exc).__name__}: {str(exc)}",
            }
        finally:
            await tracker.exit()


async def main(
    data_dir: Path = DATA_DIR,
    output_dir: Path = OUTPUT_DIR,
    max_concurrent: int = MAX_CONCURRENT,
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = sorted(data_dir.glob("*.pdf"))

    if not pdf_files:
        logger.warning("No PDFs found in %s", data_dir)
        return []

    logger.info("Found %d PDFs to process with concurrency limit %d", len(pdf_files), max_concurrent)

    semaphore = asyncio.Semaphore(max_concurrent)
    tracker = ConcurrencyTracker()

    tasks = [
        process_pdf_async(pdf, semaphore, tracker, output_dir)
        for pdf in pdf_files
    ]

    results = []
    for task in tqdm(
        asyncio.as_completed(tasks),
        total=len(tasks),
        desc="Ingesting PDFs",
    ):
        results.append(await task)

    successful = sum(result["status"] == "success" for result in results)
    failed = len(results) - successful
    total_chunks = sum(result.get("chunks", 0) for result in results)

    print("\n" + "=" * 55)
    print("             BATCH INGESTION SUMMARY")
    print("=" * 55)
    print(f"Documents found:            {len(pdf_files)}")
    print(f"Successful:                 {successful}")
    print(f"Failed:                     {failed}")
    print(f"Total chunks generated:     {total_chunks}")
    print(f"Max concurrency observed:   {tracker.max_concurrent} (Semaphore limit: {max_concurrent})")
    print("=" * 55)

    if failed:
        print("\nFailed documents:")
        for result in results:
            if result["status"] == "failed":
                print(f"  • {result['file']}: {result['error']}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
