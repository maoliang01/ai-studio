import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("ai-studio")

load_dotenv()

# 配置数据文件路径
CONFIG_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = CONFIG_DIR / "models_config.json"


class ModelConfig(BaseModel):
    """模型配置"""
    id: str
    name: str
    type: str  # llm, embedding, multimodal
    base_url: str
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_connected: bool = False
    latency: Optional[int] = None
    last_tested_at: Optional[str] = None


class LLMConfig(BaseModel):
    """LLM 服务配置"""
    models: Dict[str, ModelConfig] = {}
    default_llm: str = ""


def load_config_from_file() -> Dict[str, Any]:
    """从文件加载配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
    return {}


def save_config_to_file(config: LLMConfig) -> None:
    """保存配置到文件"""
    try:
        data = {
            "models": {
                k: v.model_dump() for k, v in config.models.items()
            },
            "default_llm": config.default_llm,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置文件失败: {e}")


def init_llm_config() -> LLMConfig:
    """初始化 LLM 配置"""
    logger.info("正在初始化 LLM 配置...")
    # 默认模型
    default_models = {
        "default-gpt-4o": ModelConfig(
            id="default-gpt-4o",
            name="GPT-4o",
            type="llm",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY", ""),
        ),
        "default-embedding": ModelConfig(
            id="default-embedding",
            name="text-embedding-3-small",
            type="embedding",
            base_url="https://api.openai.com/v1",
            model_name="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY", ""),
        ),
    }

    data = load_config_from_file()

    config = LLMConfig()
    # 优先加载文件中的模型
    if data.get("models"):
        for k, v in data["models"].items():
            config.models[k] = ModelConfig(**v)
        logger.info(f"从文件加载了 {len(data['models'])} 个模型")
    # 如果没有，加载默认模型
    if not config.models:
        config.models = default_models
        logger.info("使用默认模型")
    # 设置默认模型
    config.default_llm = data.get("default_llm") or "default-gpt-4o"

    return config


# 全局配置实例
llm_config = init_llm_config()


def get_llm_config() -> LLMConfig:
    """获取 LLM 配置"""
    return llm_config


def update_model_config(model_id: str, config: ModelConfig) -> None:
    """更新模型配置"""
    llm_config.models[model_id] = config
    save_config_to_file(llm_config)


def add_model_config(config: ModelConfig) -> None:
    """添加模型配置（如果已存在则覆盖）"""
    logger.info(f"添加/更新模型: id={config.id}, name={config.name}, type={config.type}")
    llm_config.models[config.id] = config
    save_config_to_file(llm_config)
    logger.info(f"当前模型列表: {list(llm_config.models.keys())}")


def delete_model_config(model_id: str) -> bool:
    """删除模型配置"""
    if model_id in llm_config.models:
        del llm_config.models[model_id]
        save_config_to_file(llm_config)
        return True
    return False


def set_default_model(model_id: str) -> bool:
    """设置默认模型"""
    if model_id in llm_config.models:
        llm_config.default_llm = model_id
        save_config_to_file(llm_config)
        return True
    return False


def check_config_consistency() -> bool:
    """
    检测配置文件一致性
    - 确认 models_config.json 存在且可读
    - 确认模型列表非空
    - 检查模型配置完整性
    返回 True 表示检测通过，False 表示有问题
    """
    logger.info("========== 配置一致性检测 ==========")
    issues = []

    # 检查配置文件是否存在
    if not CONFIG_FILE.exists():
        issues.append(f"配置文件不存在: {CONFIG_FILE}")
        logger.error(f"❌ {issues[-1]}")
    else:
        logger.info(f"✅ 配置文件存在: {CONFIG_FILE}")

        # 检查文件是否可读
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            issues.append(f"配置文件读取失败: {e}")
            logger.error(f"❌ {issues[-1]}")
            data = {}

        # 检查模型列表
        if data.get("models"):
            model_count = len(data["models"])
            logger.info(f"✅ 模型配置数量: {model_count}")

            # 检查每个模型的完整性
            for model_id, model_data in data["models"].items():
                required_fields = ["id", "name", "type", "base_url"]
                missing = [f for f in required_fields if f not in model_data]
                if missing:
                    issues.append(f"模型 {model_id} 缺少字段: {missing}")
                    logger.warning(f"⚠️ {issues[-1]}")
        else:
            issues.append("模型列表为空")
            logger.warning(f"⚠️ {issues[-1]}")

    # 检查默认模型
    default_llm = data.get("default_llm") if data else None
    if default_llm:
        logger.info(f"✅ 默认模型: {default_llm}")
    else:
        logger.warning("⚠️ 未设置默认模型")

    # 汇总结果
    if issues:
        logger.warning(f"========== 配置检测完成，发现 {len(issues)} 个问题 ==========")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return False
    else:
        logger.info("========== 配置检测通过 ==========")
        return True