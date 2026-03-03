# 使用 Python 3.12.12 作为基础镜像（使用 Docker 官方镜像）
FROM python:3.12.12-slim

# 设置工作目录
WORKDIR /app

# 更换国内镜像源，加速 apt 安装
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制后端代码
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]
