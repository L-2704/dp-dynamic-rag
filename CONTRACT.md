## Chunker output → Embedder input contract

`chunker.py` exports: `chunk_documents() -> list[dict]`

Each dict matches the Section 6.3 metadata schema exactly:

{
  "category",
  "source_type",
  "source_url",
  "document_title",
  "publish_date",
  "ingestion_date",
  "content_hash",
  "page_number",
  "document_type",
  "expiry_or_superseded_by",
  "text"
}

("text" = the actual chunk content, added on top of Section 6.3's metadata fields)
