import asyncio
import subprocess
from typing import Dict, Optional
from datetime import datetime


class TaskExecutionTracker:
    def __init__(self):
        self.running_tasks: Dict[str, dict] = {}
        self.local_processes: Dict[str, subprocess.Popen] = {}
    
    def register_local_execution(self, execution_id: str, process: subprocess.Popen, task_info: dict):
        self.running_tasks[execution_id] = {
            "type": "local",
            "task_id": task_info.get("id"),
            "task_name": task_info.get("name"),
            "agent_id": None,
            "started_at": datetime.now().isoformat()
        }
        self.local_processes[execution_id] = process
    
    def register_remote_execution(self, execution_id: str, agent_id: str, task_info: dict):
        self.running_tasks[execution_id] = {
            "type": "remote",
            "task_id": task_info.get("id"),
            "task_name": task_info.get("name"),
            "agent_id": agent_id,
            "started_at": datetime.now().isoformat()
        }
    
    def unregister_execution(self, execution_id: str):
        if execution_id in self.running_tasks:
            del self.running_tasks[execution_id]
        if execution_id in self.local_processes:
            del self.local_processes[execution_id]
    
    def is_running(self, execution_id: str) -> bool:
        return execution_id in self.running_tasks
    
    def get_execution(self, execution_id: str) -> Optional[dict]:
        return self.running_tasks.get(execution_id)
    
    def get_all_running(self) -> Dict[str, dict]:
        return self.running_tasks.copy()
    
    def get_agent_for_execution(self, execution_id: str) -> Optional[str]:
        execution = self.running_tasks.get(execution_id)
        if execution and execution.get("type") == "remote":
            return execution.get("agent_id")
        return None
    
    def terminate_local(self, execution_id: str) -> bool:
        """终止本地执行的任务"""
        if execution_id in self.local_processes:
            try:
                process = self.local_processes[execution_id]
                # Windows 使用 taskkill 终止进程树
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    timeout=10
                )
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                self.unregister_execution(execution_id)
                return True
            except Exception as e:
                print(f"[TaskTracker] Error terminating local task {execution_id}: {e}")
                return False
        return False


task_tracker = TaskExecutionTracker()
