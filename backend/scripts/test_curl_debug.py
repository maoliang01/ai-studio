# -*- coding: utf-8 -*-
"""
调试curl请求
"""

import subprocess
import json

# 测试URL
url = "https://mp.weixin.qq.com/s/test123"

# 构建curl命令
cmd = [
    "curl",
    "--noproxy", "localhost",
    "-s",
    "-X", "POST",
    f"http://localhost:8084/api/wechat/crawl/article?url={url}"
]

print(f"执行命令: {' '.join(cmd)}")

# 执行curl
result = subprocess.run(cmd, capture_output=True, text=True)

print(f"返回码: {result.returncode}")
print(f"标准输出: {result.stdout}")
print(f"标准错误: {result.stderr}")

# 尝试解析JSON
try:
    data = json.loads(result.stdout)
    print(f"解析结果: {data}")
    print(f"错误字段: '{data.get('error', 'N/A')}'")
except Exception as e:
    print(f"JSON解析失败: {e}")
