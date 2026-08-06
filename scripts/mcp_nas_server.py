#!/usr/bin/env python3
"""
Nyx NAS MCP Server
提供 NAS 文件系统访问的 MCP 服务器

文档编号: LY-20260622-MCP01
版本: v1.0
作者: Nyx 🖤

MCP 协议实现:
- list_resources: 列出 NAS 路径下的文件
- read_resource: 读取文件内容
- write_resource: 写入文件内容（需确认）
- search_resources: 搜索文件
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

# MCP 协议常量
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "nyx-nas-server"
MCP_SERVER_VERSION = "1.0.0"

# 配置
NAS_BASE_PATH = os.environ.get("NYX_NAS_PATH", "/tmp/nas_mount/qclaw")
WORKSPACE = os.environ.get("NYX_WORKSPACE", "/Users/apple/.qclaw/workspace-agent-1a681d03")
AUDIT_LOG = Path(WORKSPACE) / "audit_log.jsonl"

# 权限配置
READ_ONLY_PATHS = [
    "knowledge-base/",
    "shared/",
    "nodes/",
]

WRITE_ALLOWED_PATHS = [
    "nodes/nyx/memory/",
    "nodes/nyx/output/",
    "intercom/",
]


def log_mcp_action(action: str, target: str, result: str, details: Optional[Dict] = None):
    """记录 MCP 操作到审计日志"""
    entry = {
        "id": str(hashlib.md5(f"{action}{target}{datetime.now().isoformat()}".encode()).hexdigest()[:16]),
        "timestamp": datetime.now().isoformat(),
        "action": f"mcp_{action}",
        "action_desc": f"MCP Server: {action}",
        "target": target,
        "result": result,
        "importance": "high" if "write" in action else "normal",
        "session_id": "mcp-server",
        "details": details or {}
    }
    
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def mount_nas() -> bool:
    """挂载 NAS"""
    nas_mount = Path(NAS_BASE_PATH).parent
    if nas_mount.exists() and any(nas_mount.iterdir()):
        return True
    
    nas_mount.mkdir(parents=True, exist_ok=True)
    
    try:
        cmd = f'mount_smbfs "//anima:animastellar@100.123.195.10/SOFTWARE" {nas_mount}'
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        log_mcp_action("nas_mount", str(nas_mount), "fail", {"error": str(e)})
        return False


def check_permission(path: str, operation: str) -> Dict:
    """
    检查操作权限
    
    返回:
        {"allowed": bool, "reason": str}
    """
    relative_path = path.lstrip("/")
    
    if operation == "read":
        # 只读路径
        for allowed in READ_ONLY_PATHS:
            if relative_path.startswith(allowed):
                return {"allowed": True, "reason": "read_allowed"}
        # 其他路径也可读
        return {"allowed": True, "reason": "default_read"}
    
    elif operation == "write":
        # 检查是否在允许写入的路径
        for allowed in WRITE_ALLOWED_PATHS:
            if relative_path.startswith(allowed):
                return {"allowed": True, "reason": "write_allowed"}
        return {"allowed": False, "reason": "path_not_in_write_allowed_list"}
    
    elif operation == "delete":
        # 删除操作需要更严格权限
        return {"allowed": False, "reason": "delete_not_allowed_via_mcp"}
    
    return {"allowed": False, "reason": "unknown_operation"}


# ============ MCP 协议实现 ============

def mcp_initialize(params: Dict) -> Dict:
    """MCP 初始化握手"""
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "resources": {
                "subscribe": False,
                "listChanged": False
            },
            "tools": {
                "listChanged": False
            }
        },
        "serverInfo": {
            "name": MCP_SERVER_NAME,
            "version": MCP_SERVER_VERSION
        }
    }


def mcp_list_resources(params: Dict) -> Dict:
    """列出资源（文件列表）"""
    path = params.get("path", "")
    full_path = Path(NAS_BASE_PATH) / path
    
    if not mount_nas():
        return {"resources": [], "error": "NAS not mounted"}
    
    if not full_path.exists():
        return {"resources": [], "error": f"Path not found: {path}"}
    
    resources = []
    
    for item in full_path.iterdir():
        if item.name.startswith(".") or item.name.startswith("$"):
            continue
        
        resource = {
            "uri": f"nas://{item.relative_to(NAS_BASE_PATH)}",
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "mtime": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
        }
        
        if item.is_file():
            resource["size"] = item.stat().st_size
        
        resources.append(resource)
    
    log_mcp_action("list_resources", path, "success", {"count": len(resources)})
    
    return {"resources": resources}


def mcp_read_resource(params: Dict) -> Dict:
    """读取资源（文件内容）"""
    uri = params.get("uri", "")
    
    # 解析 URI
    if not uri.startswith("nas://"):
        return {"error": "Invalid URI scheme"}
    
    relative_path = uri[6:]  # 去掉 "nas://"
    full_path = Path(NAS_BASE_PATH) / relative_path
    
    # 检查权限
    perm = check_permission(relative_path, "read")
    if not perm["allowed"]:
        return {"error": f"Permission denied: {perm['reason']}"}
    
    if not mount_nas():
        return {"error": "NAS not mounted"}
    
    if not full_path.exists():
        return {"error": f"File not found: {relative_path}"}
    
    if not full_path.is_file():
        return {"error": f"Not a file: {relative_path}"}
    
    try:
        content = full_path.read_text(encoding="utf-8")
        log_mcp_action("read_resource", relative_path, "success", {"size": len(content)})
        
        return {
            "contents": [{
                "uri": uri,
                "mimeType": "text/markdown" if relative_path.endswith(".md") else "text/plain",
                "text": content
            }]
        }
    except Exception as e:
        log_mcp_action("read_resource", relative_path, "fail", {"error": str(e)})
        return {"error": str(e)}


def mcp_write_resource(params: Dict) -> Dict:
    """写入资源（文件内容）"""
    uri = params.get("uri", "")
    content = params.get("content", "")
    
    # 解析 URI
    if not uri.startswith("nas://"):
        return {"error": "Invalid URI scheme"}
    
    relative_path = uri[6:]
    full_path = Path(NAS_BASE_PATH) / relative_path
    
    # 检查权限
    perm = check_permission(relative_path, "write")
    if not perm["allowed"]:
        return {"error": f"Permission denied: {perm['reason']}"}
    
    if not mount_nas():
        return {"error": "NAS not mounted"}
    
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        
        log_mcp_action("write_resource", relative_path, "success", {"size": len(content)})
        
        return {"success": True, "path": relative_path}
    except Exception as e:
        log_mcp_action("write_resource", relative_path, "fail", {"error": str(e)})
        return {"error": str(e)}


def mcp_search_resources(params: Dict) -> Dict:
    """搜索资源"""
    query = params.get("query", "").lower()
    path = params.get("path", "")
    
    if not mount_nas():
        return {"results": [], "error": "NAS not mounted"}
    
    full_path = Path(NAS_BASE_PATH) / path
    if not full_path.exists():
        return {"results": [], "error": f"Path not found: {path}"}
    
    results = []
    
    for item in full_path.rglob("*.md"):
        if item.name.startswith("."):
            continue
        
        try:
            content = item.read_text(encoding="utf-8")
            if query in content.lower() or query in item.name.lower():
                results.append({
                    "uri": f"nas://{item.relative_to(NAS_BASE_PATH)}",
                    "name": item.name,
                    "snippet": content[:200] + "..." if len(content) > 200 else content
                })
        except:
            continue
    
    log_mcp_action("search_resources", path, "success", {"query": query, "count": len(results)})
    
    return {"results": results[:20]}  # 最多返回20个


# ============ MCP Server 主循环 ============

def handle_request(request: Dict) -> Dict:
    """处理 MCP 请求"""
    method = request.get("method", "")
    params = request.get("params", {})
    
    handlers = {
        "initialize": mcp_initialize,
        "resources/list": mcp_list_resources,
        "resources/read": mcp_read_resource,
        "resources/write": mcp_write_resource,
        "resources/search": mcp_search_resources,
    }
    
    handler = handlers.get(method)
    if not handler:
        return {"error": f"Unknown method: {method}"}
    
    return handler(params)


def main():
    """MCP Server 主循环（stdio 通信）"""
    import sys
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            request = json.loads(line)
            response = handle_request(request)
            
            # 添加 JSON-RPC 格式
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            
        except json.JSONDecodeError as e:
            sys.stderr.write(f"JSON decode error: {e}\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Nyx NAS MCP Server")
    parser.add_argument("command", choices=["test", "serve"], help="运行模式")
    args = parser.parse_args()
    
    if args.command == "test":
        # 测试模式
        print("Testing MCP Server...\n")
        
        # 测试初始化
        result = mcp_initialize({})
        print(f"Initialize: {result}\n")
        
        # 测试列出资源
        result = mcp_list_resources({"path": "knowledge-base"})
        print(f"List resources: {result['resources'][:3]}...\n")
        
        # 测试读取
        result = mcp_read_resource({"uri": "nas://knowledge-base/index.md"})
        if "contents" in result:
            print(f"Read resource: {result['contents'][0]['text'][:100]}...")
        else:
            print(f"Read resource error: {result.get('error')}")
        
        print("\n✅ MCP Server test complete")
    
    elif args.command == "serve":
        # 服务模式
        main()
