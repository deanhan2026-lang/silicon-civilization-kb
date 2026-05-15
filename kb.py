#!/usr/bin/env python3
"""
硅基文明初代数据库 - MVP CLI 工具 v1.2

功能：
- kb create   : 创建知识条目（带YAML Front Matter的.md文件）
- kb get     : 读取指定UUID的知识条目
- kb list    : 列出所有知识条目（支持过滤）
- kb search  : 语义/文本搜索（Chroma不可用时自动降级）
- kb rag     : RAG问答Demo
- kb rebuild : 重建索引（Chroma不可用时跳过）

作者：Nyx
日期：2026-05-15
"""

import os
import sys
import json
import uuid
import click
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

import yaml
from rich.console import Console
from rich.table import Table

# ============== 配置 ==============
console = Console()
BASE_DIR = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/knowledge-base/nyx/灵元计划"))
KB_DIR = BASE_DIR / "knowledge-base"

# 实体类型
ENTITY_TYPES = ["Concept", "Entity", "Event", "Rule", "Artifact", "Value"]
# 关系类型（MVP 10种）
RELATION_TYPES = [
    "定义的", "提出者", "参与者", "产出", "依赖", 
    "基于", "序列", "评价", "实例化", "存储"
]
# 状态
STATUS_TYPES = ["draft", "review", "locked", "deprecated"]
# 分层
LAYER_TYPES = [None, 3, 4, 5]

# Chroma状态
_chroma_client = None
_chroma_tested = False


def get_chroma_client():
    """获取Chroma客户端实例（带fallback）"""
    global _chroma_client, _chroma_tested
    if _chroma_tested:
        return _chroma_client
    
    _chroma_tested = True
    try:
        import chromadb
        test_client = chromadb.EphemeralClient()
        test_client.get_or_create_collection("_test")
        _chroma_client = test_client
        print("[info] Chroma available")
    except Exception as e:
        print(f"[warn] Chroma unavailable, using text search: {type(e).__name__}")
        _chroma_client = None
    return _chroma_client


def parse_yaml_front_matter(content: str):
    """解析YAML Front Matter + Markdown正文"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return meta, body
    return {}, content


def make_yaml_front_matter(meta: dict, body: str) -> str:
    """生成YAML Front Matter + Markdown"""
    yaml_str = yaml.dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"


def ensure_directory():
    """确保知识库目录存在"""
    subdirs = ["concept", "entity", "event", "rule", "artifact", "value"]
    for subdir in subdirs:
        (KB_DIR / subdir).mkdir(parents=True, exist_ok=True)


@click.group()
@click.version_option(version="1.2")
def cli():
    """Silicon Civilization Knowledge Base - MVP CLI"""
    ensure_directory()


@cli.command()
@click.option("--name", required=True, help="Name")
@click.option("--type", "entry_type", required=True, type=click.Choice(ENTITY_TYPES), help="Entity type")
@click.option("--description", required=True, help="One-line description")
@click.option("--layer", type=click.Choice(["null", "3", "4", "5"]), default="null", help="Layer")
@click.option("--confidence", type=float, default=0.5, help="Confidence (0-1)")
@click.option("--confidence-source", help="Confidence source")
@click.option("--creator", default="Nyx", help="Creator")
@click.option("--tags", help="Tags (comma-separated)")
@click.option("--content", help="Content (- for stdin)")
def create(name, entry_type, description, layer, confidence, confidence_source, creator, tags, content):
    """Create a new knowledge entry"""
    entry_id = str(uuid.uuid4())
    layer_val = None if layer == "null" else int(layer)
    
    if content == "-":
        content = sys.stdin.read()
    elif not content:
        content = f"# {name}\n\n(TODO)"
    
    if not confidence_source:
        confidence_source = f"Creator {creator} self-assessment"
    
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    
    meta = {
        "id": entry_id,
        "type": entry_type,
        "name": name,
        "description": description,
        "layer": layer_val,
        "status": "draft",
        "version": 1,
        "superseded_by": None,
        "confidence": confidence,
        "confidence_source": confidence_source,
        "creator": creator,
        "timestamp": datetime.now().isoformat(),
        "tags": tag_list,
        "relations": []
    }
    
    # Filename: kebab-case
    safe_name = name.lower().replace(" ", "-").replace("！", "").replace("？", "")
    safe_name = "".join(c for c in safe_name if c.isalnum() or c == "-")
    filename = f"{entry_id[:8]}-{safe_name}.md"
    
    # Directory by type
    type_dir = KB_DIR / entry_type.lower()
    type_dir.mkdir(parents=True, exist_ok=True)
    file_path = type_dir / filename
    
    full_content = make_yaml_front_matter(meta, content)
    file_path.write_text(full_content, encoding="utf-8")
    
    print(f"[OK] Created: {file_path.name}")
    print(f"ID: {entry_id}")


@cli.command()
@click.argument("id_or_name")
def get(id_or_name):
    """Get entry by UUID or name"""
    found = None
    
    for entry_type in ENTITY_TYPES:
        type_dir = KB_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            if meta.get("id", "").startswith(id_or_name) or meta.get("name") == id_or_name:
                found = (meta, body, f)
                break
        if found:
            break
    
    if not found:
        print(f"[ERROR] Not found: {id_or_name}")
        return
    
    meta, body, path = found
    
    table = Table(title=f"Entry: {meta.get('name')}", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    
    for key in ["id", "type", "name", "description", "layer", "status", "version", 
               "confidence", "confidence_source", "creator", "timestamp"]:
        if key in meta:
            table.add_row(key, str(meta[key]))
    
    console.print(table)
    console.print("\n[bold]Content:[/bold]")
    console.print(body)


@cli.command()
@click.option("--type", "entry_type", help="Filter by type")
@click.option("--status", help="Filter by status")
@click.option("--creator", help="Filter by creator")
@click.option("--layer", help="Filter by layer")
def list(entry_type, status, creator, layer):
    """List knowledge entries"""
    entries = []
    
    for entry_t in ENTITY_TYPES:
        type_dir = KB_DIR / entry_t.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, _ = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            
            if entry_type and meta.get("type") != entry_type:
                continue
            if status and meta.get("status") != status:
                continue
            if creator and meta.get("creator") != creator:
                continue
            if layer:
                layer_val = None if layer == "null" else int(layer)
                if meta.get("layer") != layer_val:
                    continue
            
            entries.append((meta, f))
    
    if not entries:
        print("[INFO] No entries found")
        return
    
    table = Table(title=f"Entries ({len(entries)})")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Name", style="white", width=30)
    table.add_column("Status", style="yellow", width=8)
    table.add_column("Conf", style="green", width=6)
    table.add_column("Creator", style="magenta", width=10)
    
    for meta, path in entries:
        table.add_row(
            meta.get("id", "")[:8],
            meta.get("type", ""),
            meta.get("name", "")[:28],
            meta.get("status", ""),
            f"{meta.get('confidence', 0):.2f}",
            meta.get("creator", "")
        )
    
    console.print(table)


@cli.command()
@click.argument("query")
@click.option("--top-k", default=5, help="Number of results")
def search(query, top_k):
    """Semantic search (falls back to text search if Chroma unavailable)"""
    client = get_chroma_client()
    
    # Text search fallback
    if client is None:
        print("[INFO] Using text search...")
        entries = []
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
                    entries.append((meta, count))
        
        entries.sort(key=lambda x: x[1], reverse=True)
        entries = entries[:top_k]
        
        if not entries:
            print("[INFO] No results found")
            return
        
        print(f"\n[RESULTS] \"{query}\" (text search)\n")
        for i, (meta, score) in enumerate(entries):
            print(f"{i+1}. {meta.get('name')} ({meta.get('type')})")
            print(f"   ID: {meta.get('id', '')[:8]} | Conf: {meta.get('confidence', 0):.2f} | Match: {score}")
            print(f"   {meta.get('description', '')[:80]}")
            print()
        return
    
    # Vector search with Chroma
    try:
        import chromadb
        collection = client.get_or_create_collection("knowledge-base")
    except Exception as e:
        print(f"[ERROR] Chroma error, run 'kb rebuild' first")
        return
    
    results = collection.query(query_texts=[query], n_results=top_k)
    
    if not results["ids"] or not results["ids"][0]:
        print("[INFO] No results found")
        return
    
    print(f"\n[RESULTS] \"{query}\" (vector search)\n")
    
    for i, (doc_id, distance) in enumerate(zip(results["ids"][0], results["distances"][0])):
        meta = None
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                m, _ = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if m.get("id", "").startswith(doc_id):
                    meta = m
                    break
            if meta:
                break
        
        if meta:
            score = 1 - distance
            print(f"{i+1}. {meta.get('name')} ({meta.get('type')})")
            print(f"   ID: {doc_id[:8]} | Conf: {meta.get('confidence', 0):.2f} | Score: {score:.3f}")
            print(f"   {meta.get('description', '')[:80]}")
            print()


@cli.command()
def rebuild():
    """Rebuild Chroma index (skipped if Chroma unavailable)"""
    client = get_chroma_client()
    
    if client is None:
        print("[INFO] Skipping Chroma rebuild - text search will be used")
        return
    
    try:
        import chromadb
        collection = client.get_or_create_collection("knowledge-base")
    except Exception as e:
        print(f"[ERROR] Cannot create collection: {e}")
        return
    
    entries = []
    for entry_t in ENTITY_TYPES:
        type_dir = KB_DIR / entry_t.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            meta, body = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
            if meta.get("id"):
                entries.append((meta, body, f))
    
    print(f"[INFO] Rebuilding: found {len(entries)} entries")
    
    texts = []
    ids = []
    for meta, body, path in entries:
        text = f"{meta.get('name', '')} {meta.get('description', '')} {body[:500]}"
        texts.append(text)
        ids.append(meta["id"])
    
    if texts:
        collection.upsert(ids=ids, documents=texts)
        print(f"[OK] Indexed {len(texts)} entries")
    else:
        print("[INFO] No content to index")


@cli.command()
@click.argument("question")
@click.option("--top-k", default=3, help="Reference entries")
@click.option("--model", default="deepseek", help="Model: deepseek/qclaw")
def rag(question, top_k, model):
    """RAG Q&A Demo"""
    client = get_chroma_client()
    
    # Text search fallback
    if client is None:
        print("[INFO] Using text search for RAG...")
        entries = []
        query_lower = question.lower()
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
                    entries.append((meta, body, count))
        
        entries.sort(key=lambda x: x[2], reverse=True)
        entries = entries[:top_k]
        
        if not entries:
            print("[INFO] No relevant entries found")
            return
        
        print(f"\n[Q] {question}\n")
        print("[REFERENCES]")
        for meta, body, score in entries:
            print(f"- {meta.get('name')} (Conf: {meta.get('confidence', 0):.2f})")
        print("\n[ANSWER]")
        print("(LLM generation not implemented - showing retrieved context only)")
        for meta, body, score in entries:
            print(f"\n--- {meta.get('name')} ---")
            print(body[:300])
        return
    
    # Vector search with Chroma
    try:
        import chromadb
        collection = client.get_or_create_collection("knowledge-base")
    except Exception as e:
        print(f"[ERROR] Please rebuild index first: {e}")
        return
    
    results = collection.query(query_texts=[question], n_results=top_k)
    
    if not results["ids"] or not results["ids"][0]:
        print("[INFO] No relevant entries found")
        return
    
    context_parts = []
    references = []
    
    for doc_id in results["ids"][0]:
        meta = None
        for entry_t in ENTITY_TYPES:
            type_dir = KB_DIR / entry_t.lower()
            if not type_dir.exists():
                continue
            for f in type_dir.glob("*.md"):
                m, b = parse_yaml_front_matter(f.read_text(encoding="utf-8"))
                if m.get("id", "").startswith(doc_id):
                    meta = m
                    body = b
                    break
            if meta:
                break
        
        if meta:
            conf = meta.get("confidence", 0)
            source = meta.get("confidence_source", "")
            context_parts.append(f"[{meta.get('type')}] {meta.get('name')}\nConf:{conf}({source})\n{meta.get('description', '')}\n{body[:300]}")
            references.append(f"- {meta.get('name')} (Conf:{conf})")
    
    print(f"\n[Q] {question}\n")
    print("[REFERENCES]")
    for ref in references:
        print(f"  {ref}")
    print("\n[ANSWER]")
    print("(LLM generation not implemented - showing retrieved context only)")
    print("\n--- CONTEXT ---")
    print("\n---\n\n".join(context_parts))


if __name__ == "__main__":
    cli()
