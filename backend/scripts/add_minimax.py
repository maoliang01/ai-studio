#!/usr/bin/env python3
"""添加 MiniMax 模型配置"""

import json
import os
from pathlib import Path

# MiniMax 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
if not MINIMAX_API_KEY:
    print("请设置环境变量 MINIMAX_API_KEY")
    print("export MINIMAX_API_KEY=your-key-here")
    exit(1)

CONFIG_FILE = Path(__file__).parent / "models_config.json"

# MiniMax 模型配置
minimax_models = {
    "minimax-abab6-chat": {
        "id": "minimax-abab6-chat",
        "name": "MiniMax-abab6-chat",
        "type": "llm",
        "base_url": "https://api.minimax.chat/v1",
        "api_key": MINIMAX_API_KEY,
        "model_name": "abab6-chat",
        "is_connected": False,
        "latency": None,
        "last_tested_at": None
    },
    "minimax-embedding": {
        "id": "minimax-embedding",
        "name": "MiniMax-embedding",
        "type": "embedding",
        "base_url": "https://api.minimax.chat/v1",
        "api_key": MINIMAX_API_KEY,
        "model_name": "embo-01",
        "is_connected": False,
        "latency": None,
        "last_tested_at": None
    }
}

# 读取现有配置
if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {"models": {}, "default_llm": ""}

# 添加 MiniMax 模型
config["models"].update(minimax_models)

# 如果没有默认模型，设为 minimax
if not config.get("default_llm"):
    config["default_llm"] = "minimax-abab6-chat"

# 保存
with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"✅ MiniMax 模型配置已保存到 {CONFIG_FILE}")
print(f"已配置的模型: {list(config['models'].keys())}")
print(f"默认模型: {config['default_llm']}")
print("\n请重启后端服务使配置生效")