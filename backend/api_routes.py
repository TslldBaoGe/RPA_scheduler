from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio
from datetime import datetime

from models import Task, ExecutionHistory, AgentResponse
from storage import load_tasks, save_tasks, load_history
from task_executor import execute_task, update_execution_record
from connection_manager import manager
from scheduler_manager import scheduler_manager


router = APIRouter()


@router.get("/", tags=["root"])
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


@router.get("/tasks", response_model=List[Task], tags=["tasks"])
def get_tasks():
    return load_tasks()


@router.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(task_id: str):
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks", response_model=Task, tags=["tasks"])
def create_task(task: Task):
    tasks = load_tasks()
    
    cron_expr = task.cronExpression.strip()
    new_task = {
        "id": str(datetime.now().timestamp()),
        "name": task.name,
        "cronExpression": cron_expr,
        "cmd": task.cmd,
        "description": task.description,
        "createdAt": datetime.now().isoformat(),
        "agentId": task.agentId,
        "timeout": task.timeout or 300
    }
    
    tasks.append(new_task)
    save_tasks(tasks)
    
    try:
        scheduler_manager.add_task(new_task)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cron表达式无效: {str(e)}")
    
    return new_task


@router.put("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def update_task(task_id: str, task: Task):
    tasks = load_tasks()
    index = next((i for i, t in enumerate(tasks) if t["id"] == task_id), None)
    
    if index is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    cron_expr = task.cronExpression.strip()
    updated_task = {
        "id": task_id,
        "name": task.name,
        "cronExpression": cron_expr,
        "cmd": task.cmd,
        "description": task.description,
        "createdAt": tasks[index]["createdAt"],
        "agentId": task.agentId,
        "timeout": task.timeout or 300
    }
    
    tasks[index] = updated_task
    save_tasks(tasks)
    
    try:
        scheduler_manager.update_task(updated_task)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cron表达式无效: {str(e)}")
    
    return updated_task


@router.delete("/tasks/{task_id}", tags=["tasks"])
def delete_task(task_id: str):
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t["id"] != task_id]
    
    if len(new_tasks) == len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    save_tasks(new_tasks)
    scheduler_manager.remove_task(task_id)
    
    return {"message": "任务删除成功"}


@router.post("/tasks/{task_id}/execute", response_model=ExecutionHistory, tags=["tasks"])
def manual_execute_task(task_id: str):
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return execute_task(task)


@router.get("/execution-history", response_model=List[ExecutionHistory], tags=["history"])
def get_execution_history():
    return load_history()


@router.get("/tasks/{task_id}/execution-history", response_model=List[ExecutionHistory], tags=["history"])
def get_task_execution_history(task_id: str):
    history = load_history()
    return [h for h in history if h["taskId"] == task_id]


@router.get("/agents", tags=["agents"])
def get_agents():
    return manager.get_all_agents()


@router.post("/tasks/{task_id}/execute-on-agent", tags=["agents"])
async def execute_task_on_agent(task_id: str, agent_id: str):
    tasks = load_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if not manager.is_agent_online(agent_id):
        raise HTTPException(status_code=400, detail="Agent 不在线")
    
    await manager.send_command(agent_id, {
        "type": "execute",
        "task_id": task_id,
        "cmd": task["cmd"],
        "timeout": task.get("timeout", 300)
    })
    
    return {"message": f"任务已发送到 Agent {agent_id}"}


@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    agent_id = None
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "register":
                    agent_id = message.get("agent", {}).get("agent_id")
                    agent_info = message.get("agent", {})
                    
                    if agent_id:
                        await manager.connect(websocket, agent_id)
                        manager.register_agent(agent_id, agent_info)
                        print(f"[Agent] Registered: {agent_info.get('agent_name')} ({agent_id})")
                        
                        await websocket.send_json({
                            "type": "register_ack",
                            "status": "success",
                            "agent_id": agent_id
                        })
                
                elif msg_type == "execution_result":
                    result = message.get("result", {})
                    task_id = message.get("task_id")
                    execution_id = message.get("execution_id")
                    
                    tasks = load_tasks()
                    task = next((t for t in tasks if t["id"] == task_id), None)
                    task_name = task["name"] if task else f"Task-{task_id}"
                    task_cmd = task["cmd"] if task else result.get("cmd", "")
                    
                    if result.get("status") == "error" and result.get("error"):
                        output = f"Error: {result.get('error')}\n\nReturn code: {result.get('returncode', 'N/A')}\n\nStdout:\n{result.get('stdout', '')}\n\nStderr:\n{result.get('stderr', '')}"
                    else:
                        output = f"Return code: {result.get('returncode', 'N/A')}\n\nStdout:\n{result.get('stdout', '')}\n\nStderr:\n{result.get('stderr', '')}"
                    
                    if execution_id:
                        update_execution_record(
                            execution_id,
                            result.get("status", "unknown"),
                            output,
                            result.get("duration")
                        )
                    else:
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
                        from config import MAX_HISTORY_SIZE
                        if len(history) > MAX_HISTORY_SIZE:
                            history = history[:MAX_HISTORY_SIZE]
                        from storage import save_history
                        save_history(history)
                    
                    print(f"[Agent] Execution result received for task {task_id}, status: {result.get('status')}")
                
                elif msg_type == "pong":
                    agent_id = message.get("agent_id")
                    if agent_id:
                        manager.update_ping(agent_id)
                        
            except asyncio.TimeoutError:
                if agent_id and manager.is_agent_online(agent_id):
                    await websocket.send_json({"type": "ping"})
                    
    except WebSocketDisconnect:
        if agent_id:
            manager.disconnect(agent_id)
            print(f"[Agent] Disconnected: {agent_id}")
    except Exception as e:
        print(f"[Agent] WebSocket error: {e}")
        if agent_id:
            manager.disconnect(agent_id)
