# 使用 Python 3.12.12 作为基础镜像
# 使用 DaoCloud 镜像源（国内可访问）
FROM m.daocloud.io/docker.io/library/python:3.12.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（使用国内镜像源加速 apt）
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    else \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 Python 依赖（使用国内 PyPI 镜像）
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制后端代码
COPY backend/ .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]
