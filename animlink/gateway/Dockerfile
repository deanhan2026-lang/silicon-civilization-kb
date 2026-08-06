FROM python:3.12-slim

WORKDIR /app

# 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码
COPY gateway/ ./gateway/
COPY app.py .

# 环境
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# gevent WSGI server
CMD ["python", "-u", "app.py"]
