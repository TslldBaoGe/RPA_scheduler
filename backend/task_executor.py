import uuid
import subprocess
import re
import os
from datetime import datetime
from config import CMD_TIMEOUT, MAX_HISTORY_SIZE
from storage import load_history, save_history
from connection_manager import manager
from task_tracker import task_tracker


def format_duration(seconds: float) -> str:
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


def generate_execution_id() -> str:
    return str(uuid.uuid4())


def create_execution_record(task: dict, agent_id: str = None) -> str:
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
    
    history = load_history()
    history.insert(0, record)
    if len(history) > MAX_HISTORY_SIZE:
        history = history[:MAX_HISTORY_SIZE]
    save_history(history)
    
    return execution_id


def update_execution_record(execution_id: str, status: str, output: str, duration: str = None) -> bool:
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


def _extract_work_dir(cmd: str) -> str:
    python_match = re.search(r'(?:python|python\.exe)\s+["\']?([^\s"\']+\.py)["\']?', cmd, re.IGNORECASE)
    if python_match:
        script_path = python_match.group(1).strip('"\'')
        if os.path.exists(script_path):
            return os.path.dirname(os.path.abspath(script_path))
    return None


def _build_output(task: dict, work_dir: str, end_time: datetime, returncode: int, stdout: str, stderr: str) -> str:
    return f"执行命令: {task['cmd']}\n工作目录: {work_dir or '默认'}\n执行时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n返回码: {returncode}\n\n标准输出:\n{stdout}\n\n标准错误:\n{stderr}"


def _build_error_output(task: dict, end_time: datetime, error: str) -> str:
    return f"执行命令: {task['cmd']}\n执行时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n错误: {error}"


import os


def execute_task_local(task: dict) -> dict:
    print(f"[DEBUG] Starting task: {task['name']}, cmd: {task['cmd']}")
    execution_id = create_execution_record(task)
    print(f"[DEBUG] Created execution record: {execution_id}")
    start_time = datetime.now()
    timeout = task.get("timeout", CMD_TIMEOUT)
    
    process = None
    try:
        work_dir = _extract_work_dir(task["cmd"])
        
        # 使用 Popen 以支持终止
        process = subprocess.Popen(
            task["cmd"],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=work_dir
        )
        
        # 注册到跟踪器
        task_tracker.register_local_execution(execution_id, process, task)
        
        # 等待完成或超时
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            returncode = -1
        
        # 从跟踪器移除
        task_tracker.unregister_execution(execution_id)
        
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration_seconds)
        
        output = _build_output(task, work_dir, end_time, returncode, stdout, stderr)
        status = "success" if returncode == 0 else "error"
        
        update_execution_record(execution_id, status, output, duration_str)
        print(f"[DEBUG] Updated execution record: {execution_id}, status: {status}")
        
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
        
    except Exception as e:
        if process:
            task_tracker.unregister_execution(execution_id)
        
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()
        duration_str = format_duration(duration_seconds)
        
        output = _build_error_output(task, end_time, str(e))
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


async def send_task_to_agent(task: dict, agent_id: str, execution_id: str):
    if not manager.is_agent_online(agent_id):
        raise Exception(f"Agent {agent_id} 不在线")
    
    # 注册到跟踪器
    task_tracker.register_remote_execution(execution_id, agent_id, task)
    
    await manager.send_command(agent_id, {
        "type": "execute",
        "task_id": task["id"],
        "execution_id": execution_id,
        "cmd": task["cmd"],
        "timeout": task.get("timeout", CMD_TIMEOUT)
    })


def execute_task(task: dict) -> dict:
    agent_id = task.get("agentId")
    
    if agent_id:
        try:
            execution_id = create_execution_record(task, agent_id)
            
            import asyncio
            asyncio.run(send_task_to_agent(task, agent_id, execution_id))
            
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
            
            history = load_history()
            history.insert(0, execution_result)
            if len(history) > MAX_HISTORY_SIZE:
                history = history[:MAX_HISTORY_SIZE]
            save_history(history)
            
            return execution_result
    else:
        return execute_task_local(task)
