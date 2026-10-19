"""Run a fixed retrieval-only baseline against the application's own retrieve()."""
import hashlib
import json
import os
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


def normalize(value):
    value = unicodedata.normalize("NFKC", value).lower()
    return "".join(c for c in value if c.isalnum() or c in ".%±")


def anchors_match(text, groups):
    text = normalize(text)
    return any(all(normalize(part) in text for part in group) for group in groups)


def evaluate(collection, model, extension=None):
    import query

    cases_path = EVAL_DIR / "datasheet_cases.json"
    definition = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = definition["cases"]
    rows = []
    for case in cases:
        started = time.perf_counter()
        hits = query.retrieve(collection, model, case["question"])
        elapsed_ms = (time.perf_counter() - started) * 1000
        row = dict(case)
        row["retrieval_ms"] = round(elapsed_ms, 2)
        row["hits"] = hits
        if case["kind"] == "answerable":
            relevant = [h for h in hits if h["source"] == case["source"]]
            row["source_hit_at_1"] = bool(hits and hits[0]["source"] == case["source"])
            row["source_hit_at_5"] = bool(relevant)
            row["anchor_coverage_at_5"] = anchors_match(
                "\n".join(h["text"] for h in relevant), case["anchors"]
            )
        else:
            row["observation"] = "仅记录召回；未调用大模型，未评估拒答是否成功。"
        rows.append(row)
        print("CASE", case["id"], "source@1=", row.get("source_hit_at_1"),
              "source@5=", row.get("source_hit_at_5"), flush=True)

    positives = [r for r in rows if r["kind"] == "answerable"]
    negatives = [r for r in rows if r["kind"] != "answerable"]
    durations = sorted(r["retrieval_ms"] for r in rows)
    summary = {
        "positive_cases": len(positives),
        "out_of_corpus_cases": len(negatives),
        "source_hit_at_1": sum(r["source_hit_at_1"] for r in positives),
        "source_hit_at_5": sum(r["source_hit_at_5"] for r in positives),
        "anchor_coverage_at_5": sum(r["anchor_coverage_at_5"] for r in positives),
        "retrieval_median_ms": round((durations[len(durations)//2-1] + durations[len(durations)//2])/2, 2),
        "retrieval_p95_ms": durations[min(len(durations)-1, int(len(durations)*0.95))],
        "llm_answer_evaluated": False,
        "refusal_evaluated": False,
        "collection_count": collection.count(),
    }
    report = {
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "test_cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "scope": f"固定{len(positives)}道单文档参数/用法检索题与{len(negatives)}道库外题；Top-K=5；未调用LLM。",
        "metric_definitions": {
            "source_hit_at_1": "首条召回的来源文件是否为参考文件；不代表答案或证据正确。",
            "source_hit_at_5": "前5条召回是否包含参考文件；不代表答案或证据正确。",
            "anchor_coverage_at_5": "正确来源的Top-5文本合并后，是否匹配预先定义的一组关键词；仅为字符串规则诊断，不是语义正确率。",
        },
        "summary": summary,
        "extension": extension,
        "cases": rows,
        "limitations": [
            "人工编写的小规模固定测试，多数问题显式包含型号，属于基础检索验证。",
            "未进行随机抽样、独立留出集或跨文档替代兼容性评估。",
            "没有调用大模型，不报告答案准确率、幻觉率或拒答成功率。",
            "库外问题仍会返回相似文本；当前检索器没有显式拒绝机制。",
            "耗时来自单次本机CPU运行，包含问题向量化与检索，不包含模型加载和答案生成。",
            "参考页码是PDF物理页码，从1开始；部分资料的印刷页码与其不同。",
        ],
    }
    reports = EVAL_DIR / "reports"
    reports.mkdir(exist_ok=True)
    json_path = reports / "datasheet_retrieval_latest.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Datasheet 检索测试报告", "", f"测试时间：{report['created_at']}", "",
             report["scope"], "", "## 实测结果", "",
             f"- 库内文本块：{summary['collection_count']}",
             f"- 文档来源命中@1：{summary['source_hit_at_1']}/{len(positives)}",
             f"- 文档来源命中@5：{summary['source_hit_at_5']}/{len(positives)}",
             f"- 参考要点字符串覆盖@5：{summary['anchor_coverage_at_5']}/{len(positives)}",
             f"- 检索中位耗时：{summary['retrieval_median_ms']} ms", "",
             "以上均为检索指标，不是大模型问答准确率。", "",
             "## 逐题结果", "",
             "| ID | 问题 | 参考来源及PDF页码 | 来源@1 | 来源@5 | 要点覆盖@5 |",
             "|---|---|---|---|---|---|"]
    for row in positives:
        lines.append(f"| {row['id']} | {row['question']} | {row['source']} p.{row['reference_page']} | "
                     f"{'是' if row['source_hit_at_1'] else '否'} | {'是' if row['source_hit_at_5'] else '否'} | "
                     f"{'是' if row['anchor_coverage_at_5'] else '否'} |")
    lines += ["", "## 库外问题观察", "", "仅记录检索器返回内容，未测试模型是否会拒答。", ""]
    for row in negatives:
        first = row["hits"][0] if row["hits"] else None
        lines.append(f"- {row['id']} {row['question']} 首条来源：{first['source'] if first else '无'}；"
                     f"相似度：{first['similarity']:.3f}" if first else f"- {row['id']} 无召回")
    lines += ["", "## 指标含义与限制", ""]
    lines += [f"- {k}：{v}" for k, v in report["metric_definitions"].items()]
    lines += [f"- {v}" for v in report["limitations"]]
    lines += ["", "## 复现", "", "在 knowledge-agent 目录运行：", "", "```powershell",
              "python evaluation/run_datasheet_eval.py", "```", "",
              f"固定题集SHA256：`{report['test_cases_sha256']}`", "",
              "逐题参考答案、召回原文与相似度详见同目录JSON报告。"]
    (reports / "datasheet_retrieval_latest.md").write_text("\n".join(lines), encoding="utf-8")
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    return report


def main():
    print("Loading local retrieval dependencies...", flush=True)
    import torch
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    from config import CONFIG
    from ingest import EMBED_MODEL_NAME
    torch.set_num_threads(4)
    model = SentenceTransformer(EMBED_MODEL_NAME, local_files_only=True)
    client = chromadb.PersistentClient(path=CONFIG.db_path, settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection("knowledge_base")
    extension_path = EVAL_DIR / "extension_result.json"
    extension = json.loads(extension_path.read_text(encoding="utf-8")) if extension_path.exists() else None
    evaluate(collection, model, extension)


if __name__ == "__main__":
    main()
