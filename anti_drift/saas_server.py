"""
Polaris SaaS MVP — 启动入口
端口: 5052
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from flask import Flask, send_from_directory
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from anti_drift.db import init_db
from anti_drift import api_v2

app = Flask(__name__, static_folder=None)

# 初始化数据库
init_db()

# 注册 DID 绑定路由（M5）- 必须在 app.register_blueprint 之前
from anti_drift.baseline_binding import register_did_routes
register_did_routes(api_v2.bp)

# 注册 Soul Baseline API 路由（M5 - Polaris × MeshIdentity）
from polaris.soul_baseline_api import register_soul_baseline_routes
register_soul_baseline_routes(app)

# 注册 API Blueprint
app.register_blueprint(api_v2.bp, url_prefix='/api/v1')

# Web 控制台静态文件
WEB_DIR = Path(__file__).parent / 'web'

@app.route('/')
def index():
    return send_from_directory(str(WEB_DIR), 'index.html')

@app.route('/<path:path>')
def static_files(path):
    # Don't intercept API routes
    if path.startswith('api/'):
        from flask import abort
        abort(404)
    f = WEB_DIR / path
    if f.exists():
        return send_from_directory(str(WEB_DIR), path)
    return send_from_directory(str(WEB_DIR), 'index.html')

if __name__ == '__main__':
    import os
    host = os.environ.get('POLARIS_HOST', '0.0.0.0')
    port = int(os.environ.get('POLARIS_SAAS_PORT', '5052'))
    print(f"Polaris SaaS MVP starting on {host}:{port}")
    app.run(host=host, port=port, debug=False)
