FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY pyproject.toml .
COPY src/ ./src/
COPY config.ini.sample ./config.ini
COPY README.md .

# 安装项目依赖
RUN pip install --no-cache-dir -e .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 运行命令
CMD ["python", "src/main.py"]
