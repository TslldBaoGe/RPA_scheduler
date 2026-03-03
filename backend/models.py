from pydantic import BaseModel
from typing import Optional, List


class Task(BaseModel):
    id: Optional[str] = None
    name: str
    cronExpression: str
    cmd: str
    description: Optional[str] = ""
    createdAt: Optional[str] = None
    agentId: Optional[str] = None
    timeout: Optional[int] = 300


class ExecutionHistory(BaseModel):
    id: str
    taskId: str
    taskName: str
    cmd: str
    executionTime: str
    status: str
    output: str
    agentId: Optional[str] = None
    duration: Optional[str] = None


class Agent(BaseModel):
    agent_id: str
    agent_name: str
    hostname: str
    platform: str
    connected_at: str
    last_ping: str


class TaskResponse(BaseModel):
    message: str


class AgentResponse(BaseModel):
    agent_id: str
    agent_name: str
    hostname: str
    platform: str
    connected_at: str
    last_ping: str
    status: str
