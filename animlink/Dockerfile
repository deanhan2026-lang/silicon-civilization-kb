FROM python:3.12-slim

WORKDIR /app

# 安装 gevent 编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/ ./gateway/

# 环境变量
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# 启动 gevent WSGI 服务器（同时处理 HTTP + WebSocket）
CMD ["python", "-u", "gateway/app.py"]
