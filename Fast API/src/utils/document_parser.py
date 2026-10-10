from docling.document_converter import DocumentConverter
from pathlib import Path
import pymupdf4llm
from .table_normalizer import normalize_table
from .chunker import chunk_section

parent_path = Path(__file__).parent.parent.parent

PDF_PATH = parent_path/"data"/"clinical_trial_sample.pdf"
OUTPUT_DIR = parent_path/"output"
OUTPUT_DIR.mkdir(exist_ok=True)

def docling_parser():
  converter = DocumentConverter()
  result = converter.convert(str(PDF_PATH))
  markdown_result = result.document.export_to_markdown()
  (OUTPUT_DIR/"docling_output.md").write_text(markdown_result, encoding="utf-8")
  print(f"Docling characters: {len(markdown_result):,}")
  return

def extract_dynamic_metadata(doc, table):
    # 1. Page Number from table provenance
    page_number = table.prov[0].page_no if table.prov else 1
    
    # 2. Document Title dynamically derived from the file name
    document_title = PDF_PATH.stem.replace("_", " ").title()
    
    # 3. Dynamic Section Path tracking
    section_path = ["General"]
    current_headings = []
    
    table_prov = table.prov[0] if table.prov else None
    
    if table_prov:
        for element in doc.texts:
            # Stop tracking once we reach the page/position of the table
            if element.prov and element.prov[0].page_no > table_prov.page_no:
                break
                
            # Check if the element is a heading/section header
            if getattr(element, "label", "") == "section_header":
                current_headings.append(element.text)
        
        if current_headings:
            # Keep the last few relevant headings as the section breadcrumb path
            section_path = current_headings[-2:] if len(current_headings) >= 2 else current_headings

    return document_title, section_path, page_number

def docling_extract_tables():
    converter = DocumentConverter()
    result = converter.convert(str(PDF_PATH))
    doc = result.document
    
    print(f"Tables Found in document: {len(doc.tables)}")
    
    for index, table in enumerate(doc.tables, start=1):
        print(f"\n --- Table {index} ---")
        
        # Dynamically obtain title, section path, and page number
        doc_title, section_path, page_num = extract_dynamic_metadata(doc, table)
        
        # Pass dynamic metadata to your normalizer
        print(normalize_table(
            data_frame_table=table.export_to_dataframe(doc=doc),
            markdown_table=table.export_to_markdown(doc=doc),
            document_title=doc_title,
            section_path=section_path,
            page_number=page_num
        ))
    return

def pymupdf4llm_parser():
  markdown_result = pymupdf4llm.to_markdown(str(PDF_PATH))
  if isinstance(markdown_result, list):
        markdown_result = "\n".join([page.get("text", "") for page in markdown_result])
  (OUTPUT_DIR/"pymupdf4llm_output.md").write_text(markdown_result, encoding="utf-8")
  print(f"PyMuPDF characters: {len(markdown_result):,}")

  return

def parse_document():
  if not PDF_PATH.exists():
    raise FileNotFoundError("File not found: ",PDF_PATH)
  # print("Started Docling Parser")
  # docling_parser()
  # print("Parsed Docling Data: ",OUTPUT_DIR/"docling_output.md")
  
  # print("Started pymupdf4llm Parser")
  # pymupdf4llm_parser()
  # print("Parsed pymupdf4llm Data: ",OUTPUT_DIR/"pymupdf4llm_output.md")
  docling_extract_tables()


parse_document()