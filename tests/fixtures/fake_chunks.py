"""
Fake chunks matching CONTRACT.md schema, for independent testing
until real sample_chunks.json is available from ingestion-pipeline.
"""
FAKE_CHUNKS = [
    {
        "category": "test",
        "source_type": "manual",
        "source_url": "local://fake1.pdf",
        "document_title": "Fake Policy Document",
        "publish_date": "2026-01-01",
        "ingestion_date": "2026-06-21",
        "content_hash": "fakehash001",
        "page_number": 1,
        "document_type": "policy",
        "expiry_or_superseded_by": None,
        "text": "Employees are entitled to 20 days of paid leave per year.",
    },
    {
        "category": "test",
        "source_type": "manual",
        "source_url": "local://fake1.pdf",
        "document_title": "Fake Policy Document",
        "publish_date": "2026-01-01",
        "ingestion_date": "2026-06-21",
        "content_hash": "fakehash002",
        "page_number": 2,
        "document_type": "policy",
        "expiry_or_superseded_by": None,
        "text": "The helpline for HR support is 1800-123-456, available 9am to 6pm.",
    },
]
