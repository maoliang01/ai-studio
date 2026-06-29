from fastapi import APIRouter, HTTPException
from typing import List
import logging

logger = logging.getLogger("ai-studio")

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
    """同步前端模型配置到后端（覆盖模式）"""
    logger.info(f"=== 收到同步模型请求 ===")
    logger.info(f"待同步模型数量: {len(models)}")

    from app.core.config import ModelConfig, get_llm_config, save_config_to_file
    import re

    # 获取当前配置
    config = get_llm_config()
    logger.info(f"同步前模型数量: {len(config.models)}")

    # 构建新模型字典
    new_models = {}
    for req in models:
        # 生成简洁的 ID
        model_id = re.sub(r'\s+', '-', req.name.lower())
        logger.info(f"同步模型: {req.name} -> id={model_id}")
        model = ModelConfig(
            id=model_id,
            name=req.name,
            type=req.type,
            base_url=req.base_url,
            api_key=req.api_key,
            model_name=req.model_name,
        )
        new_models[model_id] = model

    # 覆盖模式：替换所有模型
    config.models = new_models
    save_config_to_file(config)
    logger.info(f"同步后模型数量: {len(config.models)}")

    return {"message": f"已同步 {len(models)} 个模型"}


@router.get("", response_model=List[ModelInfo])
async def list_models():
    """获取所有已配置的模型"""
    import re
    config = get_llm_config()
    models = []
    for model_id, model in config.models.items():
        # 使用 name 生成一致的 ID
        display_id = re.sub(r'\s+', '-', model.name.lower())
        models.append(ModelInfo(
            id=display_id,  # 使用 name 生成一致的 ID
            name=model.name,
            type=model.type,
            base_url=model.base_url,
            api_key=model.api_key,
            model_name=model.model_name,
            is_connected=model.is_connected,
            latency=model.latency,
            last_tested_at=model.last_tested_at,
        ))
    return models


@router.post("", response_model=ModelInfo)
async def create_model(config_request: ModelConfigRequest):
    """添加新模型（如果同名模型已存在则更新）"""
    logger.info(f"=== 收到添加模型请求 ===")
    logger.info(f"请求数据: name={config_request.name}, type={config_request.type}, base_url={config_request.base_url}")

    import re
    # 使用名称生成 ID（与 sync 端点保持一致）
    model_id = re.sub(r'\s+', '-', config_request.name.lower())
    logger.info(f"生成模型ID: {model_id}")

    from app.core.config import ModelConfig, get_llm_config

    model = ModelConfig(
        id=model_id,
        name=config_request.name,
        type=config_request.type,
        base_url=config_request.base_url,
        api_key=config_request.api_key,
        model_name=config_request.model_name,
    )

    add_model_config(model)

    # 获取当前模型列表
    config = get_llm_config()
    logger.info(f"添加后共有 {len(config.models)} 个模型: {list(config.models.keys())}")

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
    import re
    config = get_llm_config()
    if model_id not in config.models:
        raise HTTPException(status_code=404, detail="模型不存在")

    model = config.models[model_id]
    display_id = re.sub(r'\s+', '-', model.name.lower())
    return ModelInfo(
        id=display_id,
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