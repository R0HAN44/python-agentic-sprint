-- Day 21: Setting Up PostgreSQL with pgvector in Docker
-- Initial migration: CREATE EXTENSION vector; and define documents and document_chunks tables

-- 1. Enable pgvector extension and UUID helper
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Define documents table
CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR(255) PRIMARY KEY,
    title TEXT,
    total_pages INTEGER NOT NULL DEFAULT 1 CHECK (total_pages >= 1),
    total_chunks INTEGER NOT NULL DEFAULT 0 CHECK (total_chunks >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index on documents metadata and creation date
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin ON documents USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);

-- Trigger to maintain updated_at on documents
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 3. Define document_chunks table
-- chunk_id: SHA-256 hash (64 hex characters) matching Pydantic DocumentChunk
-- embedding: 1536-dim vector for text-embedding-3-small (nullable until embedded)
-- section_path: JSONB array of breadcrumbs matching Pydantic list[str]
-- metadata: JSONB for rich filtering (doc_type, authors, phase, etc.)
-- tsv: tsvector GENERATED ALWAYS column for native BM25 full-text search
CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id VARCHAR(64) PRIMARY KEY,
    doc_id VARCHAR(255) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL DEFAULT 1 CHECK (page_number >= 1),
    section_path JSONB NOT NULL DEFAULT '[]'::jsonb,
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    token_count INTEGER NOT NULL CHECK (token_count > 0),
    embedding vector(1536),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Essential relational & vector-support indexes
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_page ON document_chunks(page_number);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata_gin ON document_chunks USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv_gin ON document_chunks USING gin (tsv);
