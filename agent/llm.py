"""LLM 客户端：OpenAI 兼容的 /chat/completions 接口。

DeepSeek / Qwen(DashScope 兼容模式) / OpenAI / Ollama 均可用，
API Key 只从环境变量读取，绝不出现在代码中。
"""
import json

import requests

from .config import Config


class LLMError(Exception):
    """LLM 调用失败。"""


class LLMClient:
    def __init__(self, config: Config):
        self.config = config

    def chat(self, messages: list[dict]) -> str:
        """发送消息列表，返回模型回复的纯文本。"""
        cfg = self.config
        if not cfg.api_key:
            raise LLMError("未设置环境变量 AGENT_API_KEY，无法调用 LLM")
        url = cfg.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": cfg.model,
            "messages": messages,
            "temperature": cfg.temperature,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=cfg.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"网络请求失败: {exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"LLM 返回 {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            raise LLMError(f"LLM 响应格式异常: {resp.text[:300]}") from exc
