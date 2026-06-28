from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas.chat import ModelConfigRequest, ModelInfo, TestResult
from app.core.config import (
    get_llm_config,
    update_model_config,
    add_model_config,
    delete_model_config,
)
from app.core.llm import llm_service

router = APIRouter(prefix="/models", tags=["模型配置"])


@router.post("/sync")
async def sync_models(models: List[ModelConfigRequest]):
    """同步前端模型配置到后端"""
    from app.core.config import ModelConfig
    import re
    for req in models:
        # 生成简洁的 ID
        model_id = re.sub(r'\s+', '-', req.name.lower())
        model = ModelConfig(
            id=model_id,
            name=req.name,
            type=req.type,
            base_url=req.base_url,
            api_key=req.api_key,
            model_name=req.model_name,
        )
        add_model_config(model)
    return {"message": f"已同步 {len(models)} 个模型"}


@router.get("", response_model=List[ModelInfo])
async def list_models():
    """获取所有已配置的模型"""
    config = get_llm_config()
    models = []
    for model_id, model in config.models.items():
        models.append(ModelInfo(
            id=model.id,
            name=model.name,
            type=model.type,
            base_url=model.base_url,
            model_name=model.model_name,
            is_connected=model.is_connected,
            latency=model.latency,
            last_tested_at=model.last_tested_at,
        ))
    return models


@router.post("", response_model=ModelInfo)
async def create_model(config_request: ModelConfigRequest):
    """添加新模型"""
    import uuid
    model_id = f"model-{uuid.uuid4().hex[:8]}"

    from app.core.config import ModelConfig
    model = ModelConfig(
        id=model_id,
        name=config_request.name,
        type=config_request.type,
        base_url=config_request.base_url,
        api_key=config_request.api_key,
        model_name=config_request.model_name,
    )

    add_model_config(model)
    return ModelInfo(
        id=model.id,
        name=model.name,
        type=model.type,
        base_url=model.base_url,
        model_name=model.model_name,
    )


@router.get("/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str):
    """获取指定模型信息"""
    config = get_llm_config()
    if model_id not in config.models:
        raise HTTPException(status_code=404, detail="模型不存在")

    model = config.models[model_id]
    return ModelInfo(
        id=model.id,
        name=model.name,
        type=model.type,
        base_url=model.base_url,
        model_name=model.model_name,
        is_connected=model.is_connected,
        latency=model.latency,
        last_tested_at=model.last_tested_at,
    )


@router.put("/{model_id}", response_model=ModelInfo)
async def update_model(model_id: str, config_request: ModelConfigRequest):
    """更新模型配置"""
    config = get_llm_config()
    if model_id not in config.models:
        raise HTTPException(status_code=404, detail="模型不存在")

    from app.core.config import ModelConfig
    model = ModelConfig(
        id=model_id,
        name=config_request.name,
        type=config_request.type,
        base_url=config_request.base_url,
        api_key=config_request.api_key,
        model_name=config_request.model_name,
    )

    update_model_config(model_id, model)
    return ModelInfo(
        id=model.id,
        name=model.name,
        type=model.type,
        base_url=model.base_url,
        model_name=model.model_name,
    )


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    """删除模型"""
    if not delete_model_config(model_id):
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"message": "模型已删除"}


@router.post("/{model_id}/test", response_model=TestResult)
async def test_model(model_id: str):
    """测试模型连接"""
    result = await llm_service.test_connection(model_id)
    return TestResult(
        success=result.get("success", False),
        latency=result.get("latency"),
        error=result.get("error"),
        model=result.get("model"),
    )