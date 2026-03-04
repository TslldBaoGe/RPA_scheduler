from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

from models import Task, ExecutionHistory, AgentResponse
from storage import load_tasks, save_tasks, load_history
from task_executor import execute_task
from connection_manager import manager
from scheduler_manager import scheduler_manager
from task_tracker import task_tracker


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


@router.post("/executions/{execution_id}/terminate", tags=["executions"])
async def terminate_execution(execution_id: str):
    """终止正在执行的任务"""
    from storage import load_history, save_history
    
    # 检查任务是否在运行
    execution = task_tracker.get_execution(execution_id)
    
    if not execution:
        # 检查历史记录中是否存在
        history = load_history()
        record = next((h for h in history if h["id"] == execution_id), None)
        if not record:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        if record["status"] != "running":
            raise HTTPException(status_code=400, detail=f"任务状态为 {record['status']}，无法终止")
        raise HTTPException(status_code=404, detail="执行记录不存在或已完成")
    
    execution_type = execution.get("type")
    
    if execution_type == "local":
        # 终止本地任务
        success = task_tracker.terminate_local(execution_id)
        if success:
            # 更新历史记录
            history = load_history()
            for record in history:
                if record["id"] == execution_id:
                    record["status"] = "terminated"
                    record["output"] = f"{record.get('output', '')}\n\n[系统] 任务已被用户终止"
                    break
            save_history(history)
            return {"message": "本地任务已终止", "executionId": execution_id}
        else:
            raise HTTPException(status_code=500, detail="终止本地任务失败")
    
    elif execution_type == "remote":
        # 终止远程任务
        agent_id = execution.get("agent_id")
        if agent_id and manager.is_agent_online(agent_id):
            await manager.send_command(agent_id, {
                "type": "terminate",
                "execution_id": execution_id
            })
            
            # 不在这里更新历史记录，等 Agent 返回结果时更新
            task_tracker.unregister_execution(execution_id)
            return {"message": f"已向 Agent {agent_id} 发送终止命令", "executionId": execution_id}
        else:
            raise HTTPException(status_code=400, detail="Agent 不在线，无法终止远程任务")
    
    raise HTTPException(status_code=500, detail="未知的执行类型")


@router.get("/executions/running", tags=["executions"])
def get_running_executions():
    """获取所有正在执行的任务"""
    return task_tracker.get_all_running()
