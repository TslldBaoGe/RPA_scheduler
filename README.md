# RPA Scheduler - 定时任务调度系统

一个基于 Web 的定时任务调度系统，支持 Cron 表达式、Agent 分布式执行和实时任务监控。

## 功能特性

- **定时任务管理**：支持 Cron 表达式，可视化配置任务
- **Agent 分布式执行**：任务可在多个 Agent 上分布式执行
- **实时执行历史**：查看任务执行结果和日志
- **Web 管理界面**：基于 Vue3 + Element Plus 的现代化 UI
- **任务超时控制**：支持自定义任务超时时间
- **持久化存储**：任务和历史记录本地存储

## 技术栈

- **后端**：Python 3.12.12 + FastAPI + APScheduler
- **前端**：Node.js 24.13.0 + Vue 3 + Element Plus + Vite
- **部署**：Docker + Docker Compose + Nginx

## 快速部署（Ubuntu 22.04）

### 1. 安装 Docker

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 添加用户到 docker 组
sudo usermod -aG docker $USER
newgrp docker

# 验证安装
docker --version
docker-compose --version
```

**注意**：如果 Docker 拉取镜像很慢，可以在服务器上配置镜像加速器：

```bash
# 创建 Docker 配置文件
sudo mkdir -p /etc/docker

# 写入镜像加速配置（使用多个镜像源）
sudo tee /etc/docker/daemon.json > /dev/null <<'JSONEOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
JSONEOF

# 重启 Docker
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 1.1 安装 Docker Compose

```bash
# 安装 Docker Compose（Ubuntu 22.04 需要单独安装 v2 版本）
sudo curl -SL https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose

# 添加执行权限
sudo chmod +x /usr/local/bin/docker-compose

# 创建软链接（可选，让 docker-compose 命令可用）
sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# 验证安装
docker-compose --version
```

### 1.2 关于 Nginx

本项目使用 **Docker 容器内的 Nginx**，无需在宿主机上单独安装 Nginx。

- Nginx 作为反向代理，将前端请求转发到后端服务
- 同时处理 WebSocket 连接（用于 Agent 通信）
- 配置文件位于 `./nginx.conf`，会在容器启动时自动加载
- 如需自定义配置，修改 `nginx.conf` 后重启容器即可：`docker-compose restart nginx`

### 1.3 安装 Node.js 和 NPM

```bash
# 安装 Node.js 24.x 和 NPM
# 使用 nvm 安装（推荐）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# 重新加载环境变量
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# 安装 Node.js 24.13.0
nvm install 24.13.0

# 使用 Node.js 24.13.0
nvm use 24.13.0

# 验证安装
node --version
npm --version
```

或者使用官方二进制方式安装：

```bash
# 下载 Node.js 24.x 二进制文件
curl -fsSL https://nodejs.org/dist/v24.13.0/node-v24.13.0-linux-x64.tar.xz -o node.tar.xz

# 解压
sudo tar -xJf node.tar.xz -C /usr/local --strip-components=1
rm node.tar.xz

# 验证安装
node --version
npm --version
```

### 2. 克隆代码

```bash
# 创建应用目录
mkdir -p /opt/apps
cd /opt/apps

# 克隆代码
git clone https://github.com/TslldBaoGe/RPA_scheduler.git
cd RPA_scheduler
```

### 3. 配置 Nginx（可选）

默认配置已满足大部分需求，如需修改：

```bash
# 编辑 nginx.conf
vim nginx.conf

# 常用配置项：
# - 修改监听端口（默认 80）
# - 配置 HTTPS/SSL
# - 调整代理超时时间
```

### 4. 一键部署

```bash
# 赋予执行权限
chmod +x deploy.sh

# 执行部署脚本
./deploy.sh
```

部署脚本会自动：
- 安装前端依赖并构建
- 构建 Docker 镜像
- 启动后端服务和 Nginx

### 5. 访问系统

```
http://服务器IP地址
```

**Nginx 服务说明：**
- Nginx 容器已自动启动，监听 80 端口
- 前端静态文件通过 Nginx 提供
- API 请求通过 Nginx 反向代理到后端（8000 端口）
- WebSocket 连接通过 Nginx 代理（用于 Agent 通信）

## 手动部署（不使用 Docker）

**注意：** 手动部署需要在宿主机上安装 Nginx。

### 安装 Nginx（Ubuntu）

```bash
# 更新软件包
sudo apt update

# 安装 Nginx
sudo apt install nginx -y

# 启动 Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# 验证安装
nginx -v
```

### Nginx 配置

创建配置文件：

```bash
sudo vim /etc/nginx/sites-available/rpa-scheduler
```

添加以下内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或IP

    # 前端静态文件
    location / {
        root /path/to/RPA_scheduler/frontend/dist;  # 替换为实际路径
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket (Agent 连接)
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

启用配置：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/rpa-scheduler /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```
 
 ### 后端部署

```bash
cd backend

# 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

### 前端部署

```bash
cd frontend

# 安装依赖（需要 Node.js 24.13.0）
npm install

# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

## 配置 Agent

在客户端机器上运行 Agent：

```bash
cd RPA_scheduler_agent

# 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install websockets

# 配置服务器地址（修改 agent.py 中的 SERVER_URL）
# SERVER_URL = "ws://服务器IP:8000/ws/agent"

# 启动 Agent
python agent.py
```

## 常用命令

```bash
# 查看容器日志
docker-compose logs -f

# 查看后端日志
docker-compose logs -f rpa-scheduler

# 查看 Nginx 日志
docker-compose logs -f nginx

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 更新代码并重新部署
git pull
./deploy.sh
```

## 代码更新

当代码有更新时，可以通过以下方式更新服务器：

### 方式一：Git Pull 更新（推荐）

```bash
cd /opt/apps/RPA_scheduler

# 拉取最新代码
git pull origin master

# 重新部署
./deploy.sh
```

### 方式二：手动上传更新

如果无法使用 Git，可以手动上传代码：

```bash
# 1. 在本地打包代码（排除 node_modules 和 .venv）
# 2. 上传到服务器 /opt/apps/RPA_scheduler 目录
# 3. 覆盖原有文件

# 4. 重新部署
./deploy.sh
```

### 方式三：使用 SCP 上传

```bash
# 从本地上传到服务器
scp -r backend/ frontend/ deploy.sh docker-compose.yml Dockerfile nginx.conf user@服务器IP:/opt/apps/RPA_scheduler/

# 然后在服务器上执行
ssh user@服务器IP "cd /opt/apps/RPA_scheduler && ./deploy.sh"
```

### 更新注意事项

1. **数据备份**：更新前建议备份 `./data/` 目录
2. **服务中断**：更新过程中服务会有短暂中断（约 1-2 分钟）
3. **版本回滚**：如果更新失败，可以使用 `git reset --hard HEAD~1` 回滚

## 目录结构

```
RPA_scheduler/
├── backend/              # 后端代码
│   ├── main.py          # FastAPI 主程序
│   ├── requirements.txt # Python 依赖
│   └── ...
├── frontend/            # 前端代码
│   ├── src/
│   │   └── App.vue     # 主组件
│   ├── package.json    # Node.js 依赖
│   └── ...
├── Dockerfile          # Docker 镜像构建
├── docker-compose.yml  # Docker Compose 配置
├── nginx.conf          # Nginx 配置
├── deploy.sh           # 一键部署脚本
└── README.md           # 本文件
```

## 环境要求

- **操作系统**：Ubuntu 22.04 LTS
- **Docker**：20.10+
- **Docker Compose**：2.0+
- **Python**：3.12.12（开发/Agent）
- **Node.js**：24.13.0（开发/构建）
- **NPM**：11.6.2（开发/构建）

## 端口说明

- **80**：Web 界面（Nginx）
- **8000**：后端 API（容器内部）

## 数据持久化

- **任务数据**：`./data/tasks.json`
- **执行历史**：`./data/execution_history.json`
- **日志文件**：`./logs/`

## 注意事项

1. 首次部署需要构建前端，可能需要几分钟时间
2. Agent 连接需要服务器 8000 端口可访问（或 80 端口通过 Nginx 代理）
3. 建议配置防火墙，只开放 80/443 端口
4. 生产环境建议配置 HTTPS

## 更新日志

### v1.0.0
- 初始版本发布
- 支持定时任务管理
- 支持 Agent 分布式执行
- 支持执行历史查看
- Docker 一键部署

## License

MIT License

## 联系方式

如有问题，请提交 GitHub Issue。
