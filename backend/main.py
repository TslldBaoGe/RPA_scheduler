from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import json
import os
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# 任务模型
class Task(BaseModel):
    id: Optional[str] = None
    name: str
    cronExpression: str
    cmd: str
    description: Optional[str] = ""
    createdAt: Optional[str] = None
    agentId: Optional[str] = None  # 指定执行的 Agent ID
    timeout: Optional[int] = 300  # 超时时间（秒）

# 执行历史模型
class ExecutionHistory(BaseModel):
    id: str
    taskId: str
    taskName: str
    cmd: str
    executionTime: str
    status: str
    output: str
    agentId: Optional[str] = None  # 执行的 Agent ID
    duration: Optional[str] = None  # 执行时长（格式：x时x分x秒）

# Agent 模型
class Agent(BaseModel):
    agent_id: str
    agent_name: str
    hostname: str
    platform: str
    connected_at: str
    last_ping: str

# 数据目录
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

# 任务存储文件
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "execution_history.json")
AGENTS_FILE = os.path.join(DATA_DIR, "agents.json")  # Agent 存储文件

# 命令执行超时时间（秒）
CMD_TIMEOUT = 300  # 默认 5 分钟

# 格式化执行时长
def format_duration(seconds):
    """将秒数格式化为 x时x分x秒"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}时")
    if minutes > 0:
        parts.append(f"{minutes}分")
    if secs > 0 or (hours == 0 and minutes == 0):
        parts.append(f"{secs}秒")
    
    return "".join(parts) if parts else "0秒"

# Agent 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.agents: Dict[str, Agent] = {}
    
    async def connect(self, websocket: WebSocket, agent_id: str):
        await websocket.accept()
        self.active_connections[agent_id] = websocket
    
    def disconnect(self, agent_id: str):
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    async def send_command(self, agent_id: str, message: dict):
        if agent_id in self.active_connections:
            await self.active_connections[agent_id].send_json(message)
            return True
        return False
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)
    
    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)
    
    def register_agent(self, agent_id: str, agent_info: dict):
        self.agents[agent_id] = Agent(
            agent_id=agent_id,
            agent_name=agent_info.get("agent_name", "Unknown"),
            hostname=agent_info.get("hostname", "Unknown"),
            platform=agent_info.get("platform", "Unknown"),
            connected_at=datetime.now().isoformat(),
            last_ping=datetime.now().isoformat()
        )
    
    def update_ping(self, agent_id: str):
        if agent_id in self.agents:
            self.agents[agent_id].last_ping = datetime.now().isoformat()

manager = ConnectionManager()

# 初始化任务存储
if not os.path.exists(TASKS_FILE):
    with open(TASKS_FILE, "w") as f:
        json.dump([], f)

# 初始化执行历史存储
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)

# 初始化 Agent 存储
if not os.path.exists(AGENTS_FILE):
    with open(AGENTS_FILE, "w") as f:
        json.dump([], f)

# 加载任务
def load_tasks():
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# 保存任务
def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

# 加载执行历史
def load_history():
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# 保存执行历史
def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

# 生成唯一执行ID
import uuid
def generate_execution_id():
    return str(uuid.uuid4())

# 创建执行记录
def create_execution_record(task, agent_id=None):
    """创建执行中状态的历史记录"""
    execution_id = generate_execution_id()
    record = {
        "id": execution_id,
        "taskId": task["id"],
        "taskName": task["name"],
        "cmd": task["cmd"],
        "executionTime": datetime.now().isoformat(),
        "status": "running",
        "output": "任务正在执行中...",
        "agentId": agent_id,
        "duration": None
    }
    
    # 添加到执行历史
    history = load_history()
    history.insert(0, record)
    if len(history) > 100:
        history = history[:100]
    save_history(history)
    
    return execution_id

# 更新执行记录
def update_execution_record(execution_id, status, output, duration=None):
    """更新执行记录的状态和输出"""
    history = load_history()
    for record in history:
        if record["id"] == execution_id:
            record["status"] = status
            record["output"] = output
            if duration:
                record["duration"] = duration
            save_history(history)
            return True
    return False

# 执行任务
def execute_task(task):
    """执行任务，根据 agentId 判断在本地执行还是发送到 Agent"""
    agent_id = task.get("agentId")
    
    if agent_id:
        # 发送到 Agent 执行
        try:
            # 先创建执行记录
            execution_id = create_execution_record(task, agent_id)
            
            # 使用 asyncio 运行异步函数
            asyncio.run(send_task_to_agent(task, agent_id, execution_id))
            
            # 返回执行记录信息
            return {
                "id": execution_id,
                "taskId": task["id"],
                "taskName": task["name"],
                "cmd": task["cmd"],
                "executionTime": datetime.now().isoformat(),
                "status": "running",
                "output": f"任务已发送到 Agent {agent_id} 执行",
                "agentId": agent_id
            }
        except Exception as e:
            # 记录错误
            execution_result = {
                "id": str(datetime.now().timestamp()),
                "taskId": task["id"],
                "taskName": task["name"],
                "cmd": task["cmd"],
                "executionTime": datetime.now().isoformat(),
                "status": "error",
                "output": f"执行命令: {task['cmd']}\n执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n错误: 发送到 Agent 失败 - {str(e)}",
                "agentId": agent_id
            }
            
            # 添加到执行历史
            history = load_history()
            history.insert(0, execution_result)
            if len(history) > 100:
                history = history[:100]
            save_history(history)
            
            return execution_result
    else:
        # 在本地执行
        return execute_task_local(task)

def execute_task_local(task):
    """在本地执行任务"""
    # 先创建执行中记录
    execution_id = create_execution_record(task)
    
    # 记录开始时间
    start_time = datetime.now()
    
    try:
        # 执行 CMD 命令
        # 获取超时时间，默认使用 CMD_TIMEOUT
        timeout = task.get("timeout", CMD_TIMEOUT)
        
        # 尝试从命令中提取工作目录
        work_dir = None
        cmd = task["cmd"]
        
        # 如果是 Python 脚本，提取脚本路径并设置工作目录
        import re
        # 匹配 python 后面的脚本路径
        python_match = re.search(r'(?:python|python\.exe)\s+["\']?([^\s"\']+\.py)["\']?', cmd, re.IGNORECASE)
        if python_match:
            script_path = python_match.group(1)
            # 去除可能的引号
            script_path = script_path.strip('"\'')
            # 获取脚本所在目录
            if os.path.exists(script_path):
                work_dir = os.path.dirname(os.path.abspath(script_path))
        
        result = subprocess.run(
            task["cmd"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir  # 设置工作目录
        )
        
        # 计算执行时长
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration_seconds)
        
        # 构建输出
        output = f"执行命令: {task['cmd']}\n工作目录: {work_dir or '默认'}\n执行时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n返回码: {result.returncode}\n\n标准输出:\n{result.stdout}\n\n标准错误:\n{result.stderr}"
        status = "success" if result.returncode == 0 else "error"
        
        # 更新执行记录
        update_execution_record(execution_id, status, output, duration_str)
        
        return {
            "id": execution_id,
            "taskId": task["id"],
            "taskName": task["name"],
            "cmd": task["cmd"],
            "executionTime": end_time.isoformat(),
            "status": status,
            "output": output,
            "duration": duration_str
        }
    except subprocess.TimeoutExpired:
        # 计算执行时长
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration_seconds)
        
        # 构建输出
        output = f"执行命令: {task['cmd']}\n执行时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n错误: 命令执行超时（超过 {timeout} 秒）"
        
        # 更新执行记录
        update_execution_record(execution_id, "error", output, duration_str)
        
        return {
            "id": execution_id,
            "taskId": task["id"],
            "taskName": task["name"],
            "cmd": task["cmd"],
            "executionTime": end_time.isoformat(),
            "status": "error",
            "output": output,
            "duration": duration_str
        }
    except Exception as e:
        # 计算执行时长
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration_seconds)
        
        # 构建输出
        output = f"执行命令: {task['cmd']}\n执行时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n错误: {str(e)}"
        
        # 更新执行记录
        update_execution_record(execution_id, "error", output, duration_str)
        
        return {
            "id": execution_id,
            "taskId": task["id"],
            "taskName": task["name"],
            "cmd": task["cmd"],
            "executionTime": end_time.isoformat(),
            "status": "error",
            "output": output,
            "duration": duration_str
        }

async def send_task_to_agent(task, agent_id, execution_id):
    """发送任务到 Agent 执行"""
    if agent_id not in manager.active_connections:
        raise Exception(f"Agent {agent_id} 不在线")
    
    # 发送执行命令到 Agent
    await manager.send_command(agent_id, {
        "type": "execute",
        "task_id": task["id"],
        "execution_id": execution_id,
        "cmd": task["cmd"],
        "timeout": task.get("timeout", 300)
    })

# 初始化 FastAPI 应用
app = FastAPI(
    title="定时任务调度系统 API",
    description="用于管理和执行定时任务的后端 API",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 根路由返回 API 信息
@app.get("/")
async def root():
    return {
        "name": "RPA Scheduler API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "tasks": "/tasks",
            "agents": "/agents",
            "execution_history": "/execution-history"
        }
    }

# 初始化调度器
scheduler = BackgroundScheduler()
scheduler.start()

# 启动所有任务的调度
def start_all_tasks():
    # 清除所有现有任务
    scheduler.remove_all_jobs()
    
    # 加载任务并启动调度
    tasks = load_tasks()
    for task in tasks:
        try:
            # 解析 cron 表达式
            trigger = CronTrigger.from_crontab(task["cronExpression"])
            # 添加任务到调度器
            scheduler.add_job(
                execute_task,
                trigger,
                args=[task],
                id=task["id"],
                replace_existing=True
            )
        except Exception as e:
            print(f"启动任务 {task['name']} 失败: {str(e)}")

# 启动所有任务
start_all_tasks()

# API 端点

# 获取任务列表
@app.get("/tasks", response_model=List[Task])
def get_tasks():
    return load_tasks()

# 获取单个任务
@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str):
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

# 添加任务
@app.post("/tasks", response_model=Task)
def create_task(task: Task):
    tasks = load_tasks()
    
    # 生成任务 ID
    # 去除 Cron 表达式中的首尾空格
    cron_expr = task.cronExpression.strip()
    new_task = {
        "id": str(datetime.now().timestamp()),
        "name": task.name,
        "cronExpression": cron_expr,
        "cmd": task.cmd,
        "description": task.description,
        "createdAt": datetime.now().isoformat(),
        "agentId": task.agentId,  # 保存 Agent ID
        "timeout": task.timeout or 300  # 保存超时时间
    }
    
    # 添加任务
    tasks.append(new_task)
    save_tasks(tasks)
    
    # 启动任务调度
    try:
        # 去除 Cron 表达式中的首尾空格
        cron_expr = new_task["cronExpression"].strip()
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            execute_task,
            trigger,
            args=[new_task],
            id=new_task["id"],
            replace_existing=True
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cron表达式无效: {str(e)}")
    
    return new_task

# 更新任务
@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: str, task: Task):
    tasks = load_tasks()
    index = next((i for i, t in enumerate(tasks) if t["id"] == task_id), None)
    
    if index is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新任务
    # 去除 Cron 表达式中的首尾空格
    cron_expr = task.cronExpression.strip()
    updated_task = {
        "id": task_id,
        "name": task.name,
        "cronExpression": cron_expr,
        "cmd": task.cmd,
        "description": task.description,
        "createdAt": tasks[index]["createdAt"],
        "agentId": task.agentId,  # 保存 Agent ID
        "timeout": task.timeout or 300  # 保存超时时间
    }
    
    tasks[index] = updated_task
    save_tasks(tasks)
    
    # 更新任务调度
    try:
        # 去除 Cron 表达式中的首尾空格
        cron_expr = updated_task["cronExpression"].strip()
        trigger = CronTrigger.from_crontab(cron_expr)
        scheduler.add_job(
            execute_task,
            trigger,
            args=[updated_task],
            id=updated_task["id"],
            replace_existing=True
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cron表达式无效: {str(e)}")
    
    return updated_task

# 删除任务
@app.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    
    if len(new_tasks) == len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 删除任务
    save_tasks(new_tasks)
    
    # 移除任务调度
    scheduler.remove_job(task_id)
    
    return {"message": "任务删除成功"}

# 手动执行任务
@app.post("/tasks/{task_id}/execute", response_model=ExecutionHistory)
def manual_execute_task(task_id: str):
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 执行任务
    result = execute_task(task)
    return result

# 获取执行历史
@app.get("/execution-history", response_model=List[ExecutionHistory])
def get_execution_history():
    return load_history()

# 获取任务的执行历史
@app.get("/tasks/{task_id}/execution-history", response_model=List[ExecutionHistory])
def get_task_execution_history(task_id: str):
    history = load_history()
    return [h for h in history if h["taskId"] == task_id]

# ==================== Agent 管理 API ====================

# 获取所有在线 Agent
@app.get("/agents")
def get_agents():
    return [
        {
            "agent_id": agent.agent_id,
            "agent_name": agent.agent_name,
            "hostname": agent.hostname,
            "platform": agent.platform,
            "connected_at": agent.connected_at,
            "last_ping": agent.last_ping,
            "status": "online"
        }
        for agent in manager.agents.values()
    ]

# WebSocket 端点 - Agent 连接
@app.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    agent_id = None
    try:
        # 等待 Agent 注册消息
        await websocket.accept()
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "register":
                    # Agent 注册
                    agent_id = message.get("agent", {}).get("agent_id")
                    agent_info = message.get("agent", {})
                    
                    if agent_id:
                        manager.active_connections[agent_id] = websocket
                        manager.register_agent(agent_id, agent_info)
                        print(f"[Agent] Registered: {agent_info.get('agent_name')} ({agent_id})")
                        
                        # 发送确认
                        await websocket.send_json({
                            "type": "register_ack",
                            "status": "success",
                            "agent_id": agent_id
                        })
                
                elif msg_type == "execution_result":
                    # 收到执行结果
                    result = message.get("result", {})
                    task_id = message.get("task_id")
                    execution_id = message.get("execution_id")
                    
                    # 查找任务信息
                    tasks = load_tasks()
                    task = next((t for t in tasks if t["id"] == task_id), None)
                    task_name = task["name"] if task else f"Task-{task_id}"
                    task_cmd = task["cmd"] if task else result.get("cmd", "")
                    
                    # 构建输出信息
                    if result.get("status") == "error" and result.get("error"):
                        # 执行出错（如超时）
                        output = f"Error: {result.get('error')}\n\nReturn code: {result.get('returncode', 'N/A')}\n\nStdout:\n{result.get('stdout', '')}\n\nStderr:\n{result.get('stderr', '')}"
                    else:
                        # 正常执行
                        output = f"Return code: {result.get('returncode', 'N/A')}\n\nStdout:\n{result.get('stdout', '')}\n\nStderr:\n{result.get('stderr', '')}"
                    
                    # 如果有 execution_id，更新现有记录
                    if execution_id:
                        update_execution_record(
                            execution_id,
                            result.get("status", "unknown"),
                            output,
                            result.get("duration")
                        )
                    else:
                        # 兼容旧版本，创建新记录
                        history = load_history()
                        history.insert(0, {
                            "id": str(datetime.now().timestamp()),
                            "taskId": task_id,
                            "taskName": task_name,
                            "cmd": task_cmd,
                            "executionTime": result.get("execution_time", datetime.now().isoformat()),
                            "status": result.get("status", "unknown"),
                            "output": output,
                            "agentId": message.get("agent_id"),
                            "duration": result.get("duration", "未知")
                        })
                        if len(history) > 100:
                            history = history[:100]
                        save_history(history)
                    
                    print(f"[Agent] Execution result received for task {task_id}, status: {result.get('status')}")
                
                elif msg_type == "pong":
                    # 心跳响应
                    agent_id = message.get("agent_id")
                    if agent_id:
                        manager.update_ping(agent_id)
                        
            except asyncio.TimeoutError:
                # 发送心跳检测
                if agent_id and agent_id in manager.active_connections:
                    await websocket.send_json({"type": "ping"})
                    
    except WebSocketDisconnect:
        if agent_id:
            manager.disconnect(agent_id)
            print(f"[Agent] Disconnected: {agent_id}")
    except Exception as e:
        print(f"[Agent] WebSocket error: {e}")
        if agent_id:
            manager.disconnect(agent_id)

# 通过 Agent 执行任务
@app.post("/tasks/{task_id}/execute-on-agent")
async def execute_task_on_agent(task_id: str, agent_id: str):
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if agent_id not in manager.active_connections:
        raise HTTPException(status_code=400, detail="Agent 不在线")
    
    # 发送执行命令到 Agent
    await manager.send_command(agent_id, {
        "type": "execute",
        "task_id": task_id,
        "cmd": task["cmd"],
        "timeout": task.get("timeout", 300)
    })
    
    return {"message": f"任务已发送到 Agent {agent_id}"}

# 关闭应用时停止调度器
@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    import logging
    # 配置基本日志，避免终端检测问题
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cron_scheduler.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    # 禁用 uvicorn 的默认日志配置
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_config=None,  # 完全禁用默认日志配置
        access_log=False
    )
