from fastapi import WebSocket
from datetime import datetime
from typing import Dict
from models import Agent


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
    
    async def send_command(self, agent_id: str, message: dict) -> bool:
        if agent_id in self.active_connections:
            await self.active_connections[agent_id].send_json(message)
            return True
        return False
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)
    
    def get_agent(self, agent_id: str) -> Agent:
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
    
    def is_agent_online(self, agent_id: str) -> bool:
        return agent_id in self.active_connections
    
    def get_all_agents(self) -> list:
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
            for agent in self.agents.values()
        ]


manager = ConnectionManager()
