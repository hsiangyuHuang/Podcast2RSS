FROM mcr.microsoft.com/devcontainers/python:3.11

# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
# 确保 Python 输出直接打印到终端
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置中文环境
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
