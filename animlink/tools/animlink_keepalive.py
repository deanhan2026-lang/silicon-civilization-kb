# -*- coding: utf-8 -*-
"""
AnimaLink 服务保活脚本
- 检查 5053 是否监听
- 未监听则启动 server.py
- 注册到 Windows 启动项（可选）
"""
import subprocess
import sys
import os
import time

PYTHON = r'C:\Users\Administrator\AppData\Local\Python\bin\python.exe'
WORKDIR = r'C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\animlink'
SERVER = os.path.join(WORKDIR, 'server.py')


def is_listening(port=5053):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except Exception:
        return False


def start():
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.Popen(
        [PYTHON, '-X', 'utf8', SERVER],
        cwd=WORKDIR,
        env=env,
        stdout=open(os.path.join(WORKDIR, 'animlink.log'), 'a', encoding='utf-8'),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return proc.pid


if __name__ == '__main__':
    if is_listening():
        print('AnimaLink already running')
    else:
        pid = start()
        print(f'AnimaLink started PID={pid}')
        time.sleep(5)
        if is_listening():
            print('Port 5053 OK')
        else:
            print('WARN: not listening yet')
