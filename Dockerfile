FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# 复制项目文件
COPY pyproject.toml .
COPY src/ ./src/
COPY config.ini.sample ./config.ini

# 使用 uv 安装依赖
RUN uv pip install --system -e .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1





# 运行命令
CMD ["python", "src/main.py"]
