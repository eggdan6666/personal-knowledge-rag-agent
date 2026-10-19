"""Build full index for 15 datasheets and run complete evaluation."""
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

def main():
    import torch
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    from config import CONFIG
    import ingest
    from run_datasheet_eval import evaluate

    torch.set_num_threads(4)
    data_root = Path(CONFIG.data_path)
    if not data_root.is_dir():
        raise RuntimeError("Configured data directory is missing")

    manifest = json.loads((EVAL_DIR / "datasheet_manifest.json").read_text(encoding="utf-8"))
    print(f"Manifest contains {len(manifest)} manuals, {sum(m['pdf_pages'] for m in manifest)} pages", flush=True)

    files = ingest.collect_files(str(data_root))
    print(f"Collected {len(files)} files to chunk", flush=True)

    ids, texts, metadata = ingest.prepare_chunks(files)
    if len(set(ids)) != len(ids):
        raise RuntimeError("Record ID collision")
    print(f"Total chunks prepared: {len(ids)}", flush=True)

    db = Path(CONFIG.db_path)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    backup = PROJECT / "backups" / ("db_backup_" + stamp)
    if db.exists():
        backup.parent.mkdir(exist_ok=True)
        shutil.copytree(db, backup)
        print("Backed up existing db to", str(backup), flush=True)
        # remove broken db dir to ensure pristine HNSW construction
        shutil.rmtree(db)

    print("Loading cached BGE model...", flush=True)
    model = SentenceTransformer(ingest.EMBED_MODEL_NAME, local_files_only=True)

    client = chromadb.PersistentClient(path=str(db), settings=Settings(anonymized_telemetry=False))
    collection = ingest.get_collection(client)

    print(f"Embedding and adding {len(ids)} chunks in batches of 128...", flush=True)
    t0 = time.time()
    batch_size = 128
    for offset in range(0, len(ids), batch_size):
        end = min(offset + batch_size, len(ids))
        batch_ids = ids[offset:end]
        batch_texts = texts[offset:end]
        batch_meta = metadata[offset:end]
        vectors = ingest.embed_texts(model, batch_texts)
        collection.add(ids=batch_ids, documents=batch_texts, embeddings=vectors, metadatas=batch_meta)
        print(f"Indexed {end}/{len(ids)} ({end*100//len(ids)}%) in {time.time()-t0:.1f}s", flush=True)

    total_chunks = collection.count()
    print(f"Index complete! Collection total count: {total_chunks}", flush=True)

    result = {
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "selected_pdf_count": len(manifest),
        "selected_pdf_pages": sum(m["pdf_pages"] for m in manifest),
        "all_document_count": len(files),
        "before_chunks": 14,
        "added_chunks": total_chunks - 14,
        "total_chunks": total_chunks,
        "data_path": str(data_root),
        "db_path": str(db),
        "backup_path": str(backup),
        "model": ingest.EMBED_MODEL_NAME,
        "chunk_characters": ingest.CHUNK_LIMIT,
        "long_paragraph_overlap": ingest.CHUNK_OVERLAP
    }
    (EVAL_DIR / "extension_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Starting evaluation on 45 parameter questions + 4 out-of-scope questions...", flush=True)
    evaluate(collection, model, result)
    print("Evaluation completed successfully!", flush=True)

if __name__ == "__main__":
    main()
