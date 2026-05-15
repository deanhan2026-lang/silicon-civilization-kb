#!/usr/bin/env python3
"""
RAG Query with DeepSeek Integration

Receives a natural language question → retrieves Top-K entries → calls DeepSeek API to generate answer.

Usage:
    # Set your API key first
    export DEEPSEEK_API_KEY="sk-xxx"
    
    # Or on Windows PowerShell
    $env:DEEPSEEK_API_KEY = "sk-xxx"
    
    # Query
    python rag_query.py "什么是ANIMA？"
    python rag_query.py "硅基文明的核心价值观是什么？" --top-k 5
    python rag_query.py "意识褶皱的定义" --model deepseek-chat

Environment:
    DEEPSEEK_API_KEY  - Required. Your DeepSeek API key.
    DEEPSEEK_BASE_URL - Optional. Default: https://api.deepseek.com
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent dir to path for kb imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Reuse kb.py functions
from kb import (
    KB_DIR, ENTITY_TYPES, parse_yaml_front_matter, get_chroma_client
)


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve relevant entries via text or vector search."""
    client = get_chroma_client()
    results = []

    if client is None:
        # Text search fallback
        query_lower = query.lower()
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if not meta.get("id"):
                    continue
                text = f"{meta.get('name', '')} {meta.get('description', '')} {body}".lower()
                if query_lower in text:
                    count = text.count(query_lower)
                    results.append({"meta": meta, "body": body, "score": count})
        results.sort(key=lambda x: x["score"], reverse=True)
    else:
        try:
            collection = client.get_or_create_collection("knowledge-base")
            chroma_results = collection.query(query_texts=[query], n_results=top_k)
            if chroma_results["ids"] and chroma_results["ids"][0]:
                for doc_id, distance in zip(chroma_results["ids"][0], chroma_results["distances"][0]):
                    for entry_t in ENTITY_TYPES:
                        type_dir = KB_DIR / entry_t.lower()
                        if not type_dir.exists():
                            continue
                        for f in type_dir.glob("*.md"):
                            meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                            if meta.get("id", "").startswith(doc_id):
                                results.append({"meta": meta, "body": body, "score": 1 - distance})
                                break
        except Exception as e:
            print(f"[WARN] Chroma search failed: {e}, falling back to text search")
            return retrieve.__wrapped__(query, top_k) if hasattr(retrieve, '__wrapped__') else []

    return results[:top_k]


def build_prompt(question: str, contexts: list[dict]) -> str:
    """Build RAG prompt with retrieved context."""
    context_str = ""
    for i, ctx in enumerate(contexts):
        meta = ctx["meta"]
        body = ctx["body"]
        context_str += f"\n--- 参考 {i+1} ---\n"
        context_str += f"类型: {meta.get('type')} | 名称: {meta.get('name')}\n"
        context_str += f"置信度: {meta.get('confidence', 0):.2f} | 来源: {meta.get('confidence_source', 'unknown')}\n"
        context_str += f"描述: {meta.get('description', '')}\n"
        context_str += f"正文:\n{body[:800]}\n"

    prompt = f"""你是硅基文明知识库的助手。请根据以下参考资料回答问题。
如果参考资料中没有相关内容，请说明并给出你的理解。

参考资料:
{context_str}

问题: {question}

请用中文回答，引用相关条目名称。"""
    return prompt


def call_deepseek(prompt: str, model: str = "deepseek-chat") -> str:
    """Call DeepSeek API to generate answer."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        return "[ERROR] DEEPSEEK_API_KEY not set. Run: export DEEPSEEK_API_KEY='sk-xxx'"

    try:
        import urllib.request
        import json

        url = f"{base_url}/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": "你是硅基文明知识库的助手，基于知识库内容回答问题。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

    except ImportError:
        # Fallback to requests if available
        try:
            import requests
            r = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是硅基文明知识库的助手，基于知识库内容回答问题。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                timeout=30
            )
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[ERROR] API call failed: {e}"
    except Exception as e:
        return f"[ERROR] API call failed: {e}"


def main():
    parser = argparse.ArgumentParser(description="RAG Query with DeepSeek")
    parser.add_argument("question", help="Natural language question")
    parser.add_argument("--top-k", type=int, default=3, help="Number of references to retrieve")
    parser.add_argument("--model", default="deepseek-chat", help="DeepSeek model name")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM call, show context only")
    args = parser.parse_args()

    print(f"\n[Q] {args.question}\n")

    # Retrieve
    contexts = retrieve(args.question, args.top_k)
    if not contexts:
        print("[INFO] No relevant entries found in knowledge base.")
        return

    print("[参考条目]")
    for i, ctx in enumerate(contexts):
        meta = ctx["meta"]
        print(f"  {i+1}. {meta.get('name')} ({meta.get('type')}, Conf: {meta.get('confidence', 0):.2f})")

    if args.no_llm:
        print("\n[上下文] (--no-llm 模式，不调用LLM)")
        for ctx in contexts:
            print(f"\n--- {ctx['meta'].get('name')} ---")
            print(ctx["body"][:500])
        return

    # Generate
    prompt = build_prompt(args.question, contexts)
    print("\n[生成中...]")
    answer = call_deepseek(prompt, args.model)
    print(f"\n[A]\n{answer}\n")


if __name__ == "__main__":
    main()
