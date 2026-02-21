from pydantic import BaseModel
from typing import Optional


class McpVoice(BaseModel):
    id: str
    name: str
    category: str
    fine_tuning_status: Optional[str] = None


class ConvAiAgentListItem(BaseModel):
    name: str
    agent_id: str


class ConvAiAgent(BaseModel):
    name: str
    agent_id: str
    system_prompt: str
    voice_id: str | None
    language: str
    llm: str
