"""Copy eight supplied PDFs, extend the live index, and run a frozen retrieval baseline."""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
RAW_PDF = Path(r"E:\HD-Agent·分层记忆RAG的电子Dstasheet智能问答\corpus\data\raw_pdf")
SELECTED = [
    "ST/stm32f103c8.pdf", "Quectel/EC600M-CN.pdf", "TI/TL431.pdf", "TI/LM2596.pdf",
    "MPS/MP1584.pdf", "TI/ADS1115.pdf", "TI/INA219.pdf", "Bosch/BME280.pdf",
    "ST/LIS3DH.pdf", "InvenSense/MPU6050.pdf", "Winbond/W25Q64.pdf", "TI/TMP102.pdf",
    "TI/INA226.pdf", "Microchip/ATmega328P.pdf", "TI/NE555.pdf"
]
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


def main():
    print("Loading local index dependencies; no external LLM calls...", flush=True)
    import torch
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    from config import CONFIG
    import ingest
    from run_datasheet_eval import anchors_match, evaluate

    torch.set_num_threads(4)
    data_root = Path(CONFIG.data_path)
    if not data_root.is_dir():
        raise RuntimeError("Configured data directory is missing")
    cases = json.loads((EVAL_DIR / "datasheet_cases.json").read_text(encoding="utf-8"))["cases"]
    source_map = {Path(rel).name: RAW_PDF / rel for rel in SELECTED}
    for case in cases:
        if case["kind"] != "answerable":
            continue
        with ingest.pymupdf.open(source_map[case["source"]]) as pdf:
            reference_text = pdf[case["reference_page"] - 1].get_text()
        if not anchors_match(reference_text, case["anchors"]):
            raise RuntimeError(f"Reference anchors do not match original PDF: {case['id']}")
    print(f"REFERENCE_VALIDATION_OK {len([c for c in cases if c['kind'] == 'answerable'])} fixed reference cases", flush=True)

    manifest = []
    for rel in SELECTED:
        source = RAW_PDF / rel
        target = data_root / "datasheets" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Refusing to overwrite a different existing file: {target.name}")
        shutil.copy2(source, target)
        with ingest.pymupdf.open(source) as pdf:
            pages = len(pdf)
        manifest.append({"source_path": str(source), "copied_path": str(target),
                         "source": source.name, "sha256": digest, "pdf_pages": pages})
    (EVAL_DIR / "datasheet_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("COPIED", len(manifest), "PDF_PAGES", sum(m["pdf_pages"] for m in manifest), flush=True)

    print("Loading cached BGE model...", flush=True)
    model = SentenceTransformer(ingest.EMBED_MODEL_NAME, local_files_only=True)
    db = Path(CONFIG.db_path)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    backup = PROJECT / "backups" / ("db_before_datasheets_" + stamp)
    if db.exists():
        backup.parent.mkdir(exist_ok=True)
        shutil.copytree(db, backup)
        print("BACKUP", str(backup), flush=True)
    client = chromadb.PersistentClient(path=str(db), settings=Settings(anonymized_telemetry=False))
    collection = ingest.get_collection(client)
    before = collection.count()
    files = ingest.collect_files(str(data_root))
    ids, texts, metadata = ingest.prepare_chunks(files)
    if len(set(ids)) != len(ids):
        raise RuntimeError("Record ID collision; index was not modified")
    existing_ids = set(collection.get(include=[]) ["ids"])
    positions = [i for i, record_id in enumerate(ids) if record_id not in existing_ids]
    print("TO_EMBED", len(positions), "EXISTING", before, flush=True)
    for offset in range(0, len(positions), 128):
        batch = positions[offset:offset + 128]
        batch_texts = [texts[i] for i in batch]
        vectors = ingest.embed_texts(model, batch_texts)
        collection.add(ids=[ids[i] for i in batch], documents=batch_texts,
                       embeddings=vectors, metadatas=[metadata[i] for i in batch])
        print("INDEX_PROGRESS", min(offset + len(batch), len(positions)), "/", len(positions), flush=True)
    result = {"created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "selected_pdf_count": len(manifest), "selected_pdf_pages": sum(m["pdf_pages"] for m in manifest),
              "all_document_count": len(files), "before_chunks": before,
              "added_chunks": len(positions), "total_chunks": collection.count(),
              "data_path": str(data_root), "db_path": str(db), "backup_path": str(backup),
              "model": ingest.EMBED_MODEL_NAME, "chunk_characters": ingest.CHUNK_LIMIT,
              "long_paragraph_overlap": ingest.CHUNK_OVERLAP}
    (EVAL_DIR / "extension_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("INDEX_COMPLETE", json.dumps(result, ensure_ascii=False), flush=True)
    evaluate(collection, model, result)


if __name__ == "__main__":
    main()
