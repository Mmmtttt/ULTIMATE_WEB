from __future__ import annotations

from typing import Any, Dict, List

# 常用多模态服务商的 OpenAI 兼容预设。
# 说明：
# - base_url 填到版本号为止（如 https://api.openai.com/v1），后端会拼 /chat/completions。
# - 模型名会随厂商更新，这里给的是常用档位；选到不存在的模型会由接口返回 4xx，按提示改成控制台里的名字即可。
# - vision=False 表示该服务商当前**没有**图片输入能力，只列出以免误选。
VISION_PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "vision": True,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
        "note": "官方接口，需要海外网络与计费账号",
    },
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "vision": True,
        "models": [
            "Qwen/Qwen2.5-VL-72B-Instruct",
            "Qwen/Qwen2.5-VL-32B-Instruct",
            "Qwen/Qwen2-VL-72B-Instruct",
        ],
        "note": "国内直连，聚合多家中外模型，模型名带厂商前缀",
    },
    {
        "id": "dashscope",
        "name": "阿里云百炼 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "vision": True,
        "models": ["qwen-vl-max", "qwen-vl-plus", "qwen2.5-vl-72b-instruct"],
        "note": "通义千问视觉系列，OpenAI 兼容模式端点",
    },
    {
        "id": "zhipu",
        "name": "智谱 AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "vision": True,
        "models": ["glm-4v-plus", "glm-4v", "glm-4v-flash"],
        "note": "glm-4v-flash 有免费额度，适合先试跑",
    },
    {
        "id": "moonshot",
        "name": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "vision": True,
        "models": ["moonshot-v1-8k-vision-preview", "moonshot-v1-32k-vision-preview"],
        "note": "视觉预览模型，上下文越长越贵",
    },
    {
        "id": "doubao",
        "name": "火山方舟 豆包",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "vision": True,
        "models": ["doubao-vision-pro-32k", "doubao-vision-lite-32k"],
        "note": "方舟里通常要填「推理接入点 ID」而不是模型名，按控制台为准",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "vision": True,
        "models": ["openai/gpt-4o", "google/gemini-2.5-flash", "qwen/qwen2.5-vl-72b-instruct"],
        "note": "聚合网关，一个 key 调多家；按美元计费",
    },
    {
        "id": "ollama",
        "name": "本地 Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "vision": True,
        "models": ["qwen2.5vl:7b", "llama3.2-vision:11b"],
        "note": "完全本地、不出网；显存/内存要够，速度看显卡",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "vision": True,
        "models": ["deepseek-flash", "deepseek-v4-pro"],
        "note": "图像理解仅在 deepseek-flash（V4.1-Flash）上支持；v4-pro 是纯文本模型",
    },
]


def list_vision_providers() -> List[Dict[str, Any]]:
    return [dict(item) for item in VISION_PROVIDERS]
