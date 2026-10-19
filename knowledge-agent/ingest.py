"""文档导入入库：扫描 DATA_PATH → 解析 → 分块 → 向量化 → 写入 chromadb。"""

import hashlib
import os

import chromadb
from chromadb.config import Settings
from docx import Document
from sentence_transformers import SentenceTransformer

from config import CONFIG

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

# 支持的文档格式
SUPPORTED_EXT = (".pdf", ".docx", ".txt")

# 分块参数（调优后的值，勿随意改大）
CHUNK_LIMIT = 300
CHUNK_OVERLAP = 30

# 本地向量模型，首次运行自动下载约 100MB
EMBED_MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# chromadb collection 名
COLLECTION_NAME = "knowledge_base"


def parse_pdf(file_path):
    """用 pymupdf 逐页提取 PDF 文本，每页前加页码标注。"""
    parts = []
    with pymupdf.open(file_path) as doc:
        for page_no, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                parts.append(f"[第{page_no}页]\n{text}")
    return "\n\n".join(parts)


def parse_docx(file_path):
    """用 python-docx 提取 Word 段落文本。"""
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def parse_txt(file_path):
    """按 UTF-8 读取 txt，非法字节丢弃避免乱码崩溃。"""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
}


def read_document(file_path):
    """按扩展名把文档解析为纯文本，失败返回空串。"""
    ext = os.path.splitext(file_path)[1].lower()
    parser = PARSERS.get(ext)
    if parser is None:
        return ""
    try:
        return parser(file_path).strip()
    except Exception as exc:
        name = os.path.basename(file_path)
        print(f"  [跳过] 解析失败 {name}：{exc}")
        return ""


def split_long_text(text, limit=CHUNK_LIMIT, overlap=CHUNK_OVERLAP):
    """把超长文本按固定长度切分，相邻块保留 overlap 个字符重叠。"""
    step = max(limit - overlap, 1)
    pieces = []
    start = 0
    while start < len(text):
        pieces.append(text[start:start + limit])
        start += step
    return pieces


def chunk_text(text, limit=CHUNK_LIMIT, overlap=CHUNK_OVERLAP):
    """按空行分隔段落，把连续段落累积到接近 limit 字符成一块。"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    buffer = ""
    for para in paragraphs:
        if len(para) > limit:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(split_long_text(para, limit, overlap))
            continue
        if not buffer:
            buffer = para
        elif len(buffer) + 1 + len(para) <= limit:
            buffer = f"{buffer}\n{para}"
        else:
            chunks.append(buffer)
            buffer = para
    if buffer:
        chunks.append(buffer)
    return [c.strip() for c in chunks if c.strip()]


def collect_files(root_path):
    """递归收集 root_path 下所有受支持格式的文档路径。"""
    files = []
    for dir_path, _dir_names, file_names in os.walk(root_path):
        for name in file_names:
            if name.startswith("~$"):
                continue
            if os.path.splitext(name)[1].lower() in SUPPORTED_EXT:
                files.append(os.path.join(dir_path, name))
    return sorted(files)


def build_record_id(file_name, chunk_index, content):
    """生成稳定 id：文件名-块序号-内容哈希前10位，重复入库不产生重复块。"""
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
    return f"{file_name}-{chunk_index}-{digest}"


def embed_texts(model, texts):
    """批量向量化并做归一化。"""
    vectors = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def get_collection(client):
    """取或建 collection，距离度量为 cosine。"""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def prepare_chunks(files):
    """解析并分块，返回 ids、texts、metadatas 三条列表。"""
    ids = []
    texts = []
    metadatas = []
    print(f"开始解析 {len(files)} 个文档：")
    for file_path in files:
        file_name = os.path.basename(file_path)
        chunks = chunk_text(read_document(file_path))
        print(f"  {file_name:<40} {len(chunks):>3} 块")
        for index, chunk in enumerate(chunks):
            ids.append(build_record_id(file_name, index, chunk))
            texts.append(chunk)
            metadatas.append({"source": file_name})
    return ids, texts, metadatas


def main():
    """执行一次完整导入流程。"""
    if not os.path.isdir(CONFIG.data_path):
        print(f"[错误] DATA_PATH 不存在，请在 .env 里检查：{CONFIG.data_path}")
        return
    files = collect_files(CONFIG.data_path)
    if not files:
        print(f"[提示] 在 {CONFIG.data_path} 下没有找到 .pdf/.docx/.txt 文档。")
        return
    ids, texts, metadatas = prepare_chunks(files)
    if not texts:
        print("[提示] 文档均无有效文本（可能是扫描版 PDF，本版不做 OCR）。")
        return

    print(f"加载向量模型 {EMBED_MODEL_NAME} ...")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    embeddings = embed_texts(model, texts)

    client = chromadb.PersistentClient(
        path=CONFIG.db_path,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = get_collection(client)
    batch = 200
    for start in range(0, len(ids), batch):
        collection.add(
            ids=ids[start:start + batch],
            embeddings=embeddings[start:start + batch],
            documents=texts[start:start + batch],
            metadatas=metadatas[start:start + batch],
        )
    print(f"入库完成：本次写入 {len(ids)} 块，库内总条数 {collection.count()}")


if __name__ == "__main__":
    main()
