from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

from app.schemas.chat import ChatResponse
from app.core.llm import llm_service
from app.core.config import get_llm_config

router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("", response_model=ChatResponse)
async def chat(request: Request):
    """发送对话请求（非流式）"""
    # 直接读取原始 JSON
    body = await request.json()

    model_id = body.get("model_id") or get_llm_config().default_llm
    messages = body.get("messages", [])
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens")
    model_config = body.get("model_config")

    print(f"[DEBUG] chat API 收到请求:")
    print(f"  model_id: {model_id}")
    print(f"  messages count: {len(messages)}")
    print(f"  model_config: {model_config}")

    content = await llm_service.non_stream_chat(
        model_id=model_id,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model_config=model_config,
    )

    return ChatResponse(content=content)


async def chat_stream_generator(body: dict):
    """流式对话生成器"""
    model_id = body.get("model_id") or get_llm_config().default_llm
    messages = body.get("messages", [])
    temperature = body.get("temperature", 0.7)
    max_tokens = body.get("max_tokens")
    model_config = body.get("model_config")

    try:
        async for chunk in llm_service.chat(
            model_id=model_id,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            model_config=model_config,
        ):
            yield {
                "event": "message",
                "data": json.dumps({"content": chunk, "done": False}),
            }
            await asyncio.sleep(0)  # 允许其他任务运行
    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }
    finally:
        yield {
            "event": "message",
            "data": json.dumps({"content": "", "done": True}),
        }


@router.post("/stream")
async def chat_stream(request: Request):
    """流式对话（SSE）"""
    body = await request.json()
    return EventSourceResponse(chat_stream_generator(body))