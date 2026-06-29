#!/usr/bin/env python3
"""
知识库索引构建脚本
Knowledge Base Index Builder

文档编号: LY-20260622-KI01
版本: v1.0
作者: Nyx 🖤

功能:
1. 扫描 NAS knowledge-base/ 目录
2. 提取文件摘要和关键词
3. 建立可检索索引
4. 支持关键词/概念检索
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 配置
NAS_PATH = os.environ.get("NYX_NAS_PATH", "/tmp/nas_mount")
KNOWLEDGE_BASE = Path(NAS_PATH) / "qclaw/knowledge-base"
INDEX_FILE = Path(os.environ.get("NYX_WORKSPACE", "/Users/apple/.qclaw/workspace-agent-1a681d03")) / "knowledge_index.json"

# 需要索引的子目录
INDEX_DIRS = [
    "concept",    # 概念定义
    "entity",     # 实体（人物/组织/地点）
    "rule",       # 规则（G001-G007铁律等）
    "artifact",   # 文档产物
    "value",      # 价值观
    "event",      # 事件记录
]

# 排除的目录
EXCLUDE_DIRS = ["$Recycle.Bin", "360SANDBOX", "Documents and Settings", "data", "docs", "nyx", "topics", "archives"]


def extract_title(content: str, filename: str) -> str:
    """从文件内容提取标题"""
    # 尝试匹配 # 标题
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # 尝试匹配文件名
    return Path(filename).stem


def extract_summary(content: str, max_length: int = 200) -> str:
    """提取文件摘要（前N个字符，跳过标题）"""
    # 移除标题
    content = re.sub(r'^#\s+.+$', '', content, count=1, flags=re.MULTILINE)
    # 移除空白
    content = re.sub(r'\s+', ' ', content).strip()
    
    if len(content) <= max_length:
        return content
    
    return content[:max_length] + "..."


def extract_keywords(content: str) -> List[str]:
    """提取关键词（基于规则）"""
    keywords = []
    
    # 匹配 [[内部链接]] 格式
    links = re.findall(r'\[\[([^\]]+)\]\]', content)
    keywords.extend(links)
    
    # 匹配 **粗体** 关键词
    bolds = re.findall(r'\*\*([^*]+)\*\*', content)
    keywords.extend(bolds[:5])  # 最多5个
    
    # 匹配规则编号（G001, G002等）
    rules = re.findall(r'\b(G\d{3})\b', content)
    keywords.extend(rules)
    
    # 匹配文档编号（LY-20260425-GN01等）
    doc_ids = re.findall(r'\b(LY-\d{8}-[A-Z]+\d+)\b', content)
    keywords.extend(doc_ids)
    
    # 去重
    return list(set(keywords))[:10]


def extract_tags_from_path(file_path: Path) -> List[str]:
    """从路径提取标签"""
    tags = []
    
    # 父目录名作为标签
    parent = file_path.parent.name
    if parent not in INDEX_DIRS:
        tags.append(parent)
    
    # 祖父目录
    grandparent = file_path.parent.parent.name
    if grandparent not in INDEX_DIRS and grandparent != "knowledge-base":
        tags.append(grandparent)
    
    return tags


def index_file(file_path: Path) -> Optional[Dict]:
    """索引单个文件"""
    if not file_path.exists():
        return None
    
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"读取失败: {file_path} - {e}")
        return None
    
    # 提取元数据
    title = extract_title(content, file_path.name)
    summary = extract_summary(content)
    keywords = extract_keywords(content)
    tags = extract_tags_from_path(file_path)
    
    # 统计
    word_count = len(content)
    line_count = content.count('\n') + 1
    
    return {
        "path": str(file_path.relative_to(KNOWLEDGE_BASE.parent)),
        "filename": file_path.name,
        "title": title,
        "summary": summary,
        "keywords": keywords,
        "tags": tags,
        "category": file_path.parent.name,
        "stats": {
            "word_count": word_count,
            "line_count": line_count
        },
        "mtime": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
    }


def build_index() -> Dict:
    """构建完整索引"""
    index = {
        "build_time": datetime.now().isoformat(),
        "base_path": str(KNOWLEDGE_BASE),
        "total_files": 0,
        "categories": {},
        "files": [],
        "search_index": {}  # 关键词 -> 文件路径列表
    }
    
    if not KNOWLEDGE_BASE.exists():
        print(f"知识库路径不存在: {KNOWLEDGE_BASE}")
        return index
    
    # 遍历目录
    for subdir in INDEX_DIRS:
        subdir_path = KNOWLEDGE_BASE / subdir
        if not subdir_path.exists():
            continue
        
        category_files = []
        
        for md_file in subdir_path.rglob("*.md"):
            # 跳过排除目录
            if any(excluded in str(md_file) for excluded in EXCLUDE_DIRS):
                continue
            
            file_index = index_file(md_file)
            if file_index:
                index["files"].append(file_index)
                category_files.append(file_index["filename"])
                
                # 构建搜索索引
                all_keywords = file_index["keywords"] + file_index["tags"]
                all_keywords.append(file_index["title"])
                
                for keyword in all_keywords:
                    keyword = keyword.lower()
                    if keyword not in index["search_index"]:
                        index["search_index"][keyword] = []
                    index["search_index"][keyword].append(file_index["path"])
        
        index["categories"][subdir] = {
            "count": len(category_files),
            "files": category_files
        }
    
    index["total_files"] = len(index["files"])
    
    return index


def search_index(index: Dict, query: str) -> List[Dict]:
    """搜索索引"""
    query = query.lower()
    results = []
    
    # 搜索关键词索引
    matched_paths = set()
    for keyword, paths in index["search_index"].items():
        if query in keyword:
            matched_paths.update(paths)
    
    # 搜索标题和摘要
    for file_info in index["files"]:
        if query in file_info["title"].lower():
            matched_paths.add(file_info["path"])
        if query in file_info["summary"].lower():
            matched_paths.add(file_info["path"])
    
    # 返回匹配的文件信息
    for file_info in index["files"]:
        if file_info["path"] in matched_paths:
            results.append(file_info)
    
    return results


def save_index(index: Dict):
    """保存索引到文件"""
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"✅ 索引已保存到 {INDEX_FILE}")


def load_index() -> Dict:
    """加载索引"""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nyx 知识库索引构建")
    parser.add_argument("action", choices=["build", "search", "stats"],
                        help="执行的操作")
    parser.add_argument("--query", "-q", help="搜索关键词")
    args = parser.parse_args()
    
    if args.action == "build":
        print("🔨 构建知识库索引...")
        index = build_index()
        save_index(index)
        print(f"\n📊 索引统计:")
        print(f"   总文件数: {index['total_files']}")
        for category, info in index["categories"].items():
            print(f"   {category}: {info['count']} 文件")
        
    elif args.action == "search":
        if not args.query:
            print("请提供搜索关键词: --query '关键词'")
            return
        
        index = load_index()
        if not index:
            print("索引不存在，请先运行 build")
            return
        
        results = search_index(index, args.query)
        print(f"\n🔍 搜索 '{args.query}' 找到 {len(results)} 个结果:\n")
        
        for i, result in enumerate(results[:10], 1):
            print(f"{i}. {result['title']}")
            print(f"   路径: {result['path']}")
            print(f"   摘要: {result['summary'][:100]}...")
            print()
        
    elif args.action == "stats":
        index = load_index()
        if not index:
            print("索引不存在，请先运行 build")
            return
        
        print(f"📊 知识库索引统计:")
        print(f"   构建时间: {index['build_time']}")
        print(f"   总文件数: {index['total_files']}")
        print(f"\n   分类统计:")
        for category, info in index["categories"].items():
            print(f"   - {category}: {info['count']} 文件")


if __name__ == "__main__":
    main()
