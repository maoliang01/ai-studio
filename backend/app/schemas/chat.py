from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class Message(BaseModel):
    """对话消息"""
    role: str  # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    model_id: Optional[str] = None
    messages: List[Dict[str, str]]
    stream: bool = True
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    class Config:
        extra = "allow"  # 允许额外字段


class ChatResponse(BaseModel):
    """聊天响应"""
    content: str
    model: Optional[str] = None
    usage: Optional[Dict] = None


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    type: str
    base_url: str
    model_name: Optional[str] = None
    is_connected: bool = False
    latency: Optional[int] = None
    last_tested_at: Optional[str] = None


class ModelConfigRequest(BaseModel):
    """模型配置请求"""
    name: str
    type: str  # llm, embedding, multimodal
    base_url: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None


class TestResult(BaseModel):
    """测试结果"""
    success: bool
    latency: Optional[int] = None
    error: Optional[str] = None
    model: Optional[str] = None