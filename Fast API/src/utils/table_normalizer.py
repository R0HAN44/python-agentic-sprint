import json

def normalize_table(
    data_frame_table,
    markdown_table: str,
    document_title: str,
    section_path: list[str],
    page_number: int,
):
    table = markdown_table.strip()
    
    if not table:
        raise ValueError("Table cannot be empty")
    
    lines = table.splitlines()
    table_start_index = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            table_start_index = i
            break
    else:
        raise ValueError("Expected a Markdown table starting with '|'")
      
    if not section_path:
        raise ValueError("Section path cannot be empty")
      
    section = " > ".join(section_path)
    
    cleaned_table = "\n".join(lines[table_start_index:])
    
    # Construct the structured JSON schema representation
    json_table = {
        "document_title": document_title,
        "section": section_path,
        "page_number": page_number,
        "columns": list(data_frame_table.columns),
        "rows": data_frame_table.fillna("").values.tolist()
    }
    
    # Return both the readable Markdown context and the JSON block
    return (
        f"Document: {document_title}\n"
        f"Section: {section}\n"
        f"Page: {page_number}\n\n"
        f"{cleaned_table}\n\n"
        f"```json\n"
        f"{json.dumps(json_table, indent=4, ensure_ascii=False)}\n"
        f"```"
    )