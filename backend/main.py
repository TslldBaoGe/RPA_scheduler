from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from datetime import datetime

from storage import init_storage, load_tasks, load_history, save_history
from scheduler_manager import scheduler_manager
from api_routes import router
from connection_manager import manager
from task_executor import update_execution_record
from config import MAX_HISTORY_SIZE


app = FastAPI(
    title="定时任务调度系统 API",
    description="用于管理和执行定时任务的后端 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    agent_id = None
    try:
        await websocket.accept()
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "register":
                    agent_id = message.get("agent", {}).get("agent_id")
                    agent_info = message.get("agent", {})
                    
                    if agent_id:
                        manager.active_connections[agent_id] = websocket
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
                        if len(history) > MAX_HISTORY_SIZE:
                            history = history[:MAX_HISTORY_SIZE]
                        save_history(history)
                    
                    print(f"[Agent] Execution result received for task {task_id}, status: {result.get('status')}")
                
                elif msg_type == "pong":
                    agent_id = message.get("agent_id")
                    if agent_id:
                        manager.update_ping(agent_id)
                        
            except asyncio.TimeoutError:
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


@app.on_event("shutdown")
def shutdown_event():
    scheduler_manager.shutdown()


if __name__ == "__main__":
    import uvicorn
    import logging
    
    init_storage()
    scheduler_manager.start()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cron_scheduler.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_config=None,
        access_log=False
    )
