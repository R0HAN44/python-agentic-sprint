from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

@dataclass
class DocumentChunk:
  content:str
  document_title:str
  section_path:list[str]
  chunk_index:int
  
def chunk_section(
  text:str,
  document_title:str,
  section_path:list[str],
  chunk_size:int = 2000,
  chunk_overlap:int =200,
)->list[DocumentChunk]:
  if not text.strip():
    return []
  
  splitter = RecursiveCharacterTextSplitter(
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    length_function=len,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
  )
  
  pieces = splitter.split_text(text)
  
  return [
    DocumentChunk(
      content=piece,
      document_title=document_title,
      section_path=section_path,
      chunk_index=index
    )
    for index,piece in enumerate(pieces)
  ]