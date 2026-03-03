from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

from models import Task, ExecutionHistory, AgentResponse
from storage import load_tasks, save_tasks, load_history
from task_executor import execute_task
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
