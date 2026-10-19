"""问答入口：问题向量化 → 召回 TOP_K 块 → LLM 生成带 [来源N] 引用的回答。"""

import sys

import chromadb
from chromadb.config import Settings
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from config import CONFIG
from ingest import EMBED_MODEL_NAME, embed_texts, get_collection

# bge 官方检索前缀，问题向量化必须加，否则召回明显变差
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

SYSTEM_PROMPT = (
    "你是一个严谨的资料问答助手。只能依据下面提供的资料回答问题。"
    "资料里没有的内容，必须明确回答『资料里没有相关信息』，不要用自己的知识编造。"
    "引用资料时，在相关句子末尾用 [来源N] 标注，N 是资料编号。"
    "回答用简体中文，简洁准确。"
)

EXIT_WORDS = ("exit", "quit", "退出")

# 向量模型加载后常驻，避免每轮问答重新加载
_model = None


def get_embed_model():
    """惰性加载本地向量模型。"""
    global _model
    if _model is None:
        print(f"加载向量模型 {EMBED_MODEL_NAME} ...")
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def retrieve(collection, model, question):
    """召回与问题最相关的 TOP_K 个文本块。"""
    query_vector = embed_texts(model, [QUERY_PREFIX + question])[0]
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(CONFIG.top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for doc, meta, dist in zip(
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        hits.append({"text": doc, "source": meta.get("source", "未知来源"), "similarity": 1.0 - dist})
    return hits


def build_context(hits):
    """把召回结果拼成带编号的上下文。"""
    blocks = []
    for index, hit in enumerate(hits, start=1):
        blocks.append(f"[来源{index}] {hit['source']}\n{hit['text']}")
    return "\n\n".join(blocks)


def ask(client, question, context):
    """调用 LLM 生成回答。"""
    response = client.chat.completions.create(
        model=CONFIG.llm_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"资料：\n{context}\n\n问题：{question}"},
        ],
    )
    return response.choices[0].message.content


def print_sources(hits):
    """列出引用资料及相似度。"""
    print("─" * 46)
    print("引用资料：")
    for index, hit in enumerate(hits, start=1):
        print(f"  [来源{index}] {hit['source']}  相似度 {hit['similarity']:.3f}")
    print()


def check_ready():
    """启动前检查配置，返回 (llm客户端, 向量库collection)，不就绪则退出。"""
    if not CONFIG.has_valid_key:
        print("还没有配置 LLM_API_KEY。")
        print("请打开 .env 文件，把 LLM_API_KEY= 后面换成你自己的 key（火山方舟或 DeepSeek 都行）。")
        print("同时确认 LLM_BASE_URL 和 LLM_MODEL 与你的 key 属于同一家。")
        sys.exit(0)
    client = OpenAI(base_url=CONFIG.llm_base_url, api_key=CONFIG.llm_api_key)
    chroma = chromadb.PersistentClient(
        path=CONFIG.db_path,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = get_collection(chroma)
    if collection.count() == 0:
        print("向量库是空的。先运行 python ingest.py 把文档导入，再回来提问。")
        sys.exit(0)
    return client, collection


def main():
    """命令行问答循环。"""
    client, collection = check_ready()
    model = get_embed_model()
    print("个人知识库问答已就绪，输入问题回车即可，输入 exit / quit / 退出 结束。")
    print(f"模型 {CONFIG.llm_model} ｜ 知识库 {CONFIG.db_path} ｜ 每次召回 {CONFIG.top_k} 块\n")
    while True:
        try:
            question = input("你问> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break
        if not question:
            continue
        if question.lower() in EXIT_WORDS or question in EXIT_WORDS:
            print("已退出。")
            break
        hits = retrieve(collection, model, question)
        answer = ask(client, question, build_context(hits))
        print(f"回答> {answer}\n")
        print_sources(hits)


if __name__ == "__main__":
    main()
