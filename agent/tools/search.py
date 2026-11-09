"""search 工具（mock）：在内置文档库上做关键词检索（英文词 + 中文二元组打分）。"""
import re

from .registry import Tool

_DOCS = [
    {
        "title": "MiniAgent 架构",
        "content": "MiniAgent 由四个部分组成：LLM 客户端负责调用大模型；OutputParser 解析模型输出中的思考、工具调用和最终答案；ToolRegistry 管理工具注册与执行；AgentRuntime 驱动 loop：接收用户输入，模型决策，执行工具，根据工具结果继续或返回答案。",
    },
    {
        "title": "Session 管理",
        "content": "每个窗口是一个独立 session，拥有自己的对话历史、待办状态和 trace 日志。SessionManager 以 session_id 为键管理所有会话，并支持 JSON 文件持久化，重启后仍可继续对话。",
    },
    {
        "title": "Context 与压缩",
        "content": "上下文由系统提示词、历史摘要和最近若干轮对话组成。当对话轮数超过 max_history_turns 时，最早的轮次会被 LLM 压缩成摘要，注入到系统消息区域。工具结果和思考过程都会保留在上下文中。",
    },
    {
        "title": "工具注册机制",
        "content": "每个工具包含名称 name、描述 description、参数 Schema parameters 和执行函数 fn。系统提示词会列出全部工具的 Schema，LLM 根据 Schema 自主决策调用哪个工具、传什么参数。参数在执行前会做必填与类型校验。",
    },
    {
        "title": "异常处理",
        "content": "工具执行有 try/except 兜底，参数校验失败、工具未注册、运行时异常都会转成错误消息回传给 LLM，由模型自行修正重试或向用户说明。单轮工具调用次数有上限，防止死循环。",
    },
    {
        "title": "Python 异常体系",
        "content": "Python 的异常体系以 BaseException 为根，常见的有 ValueError、TypeError、KeyError、IndexError。用 try/except 捕获异常，用 raise 抛出异常。",
    },
]


def _tokens(text: str) -> list[str]:
    en = re.findall(r"[a-zA-Z0-9]+", text.lower())
    cjk = re.findall(r"[一-鿿]", text)
    bigrams = [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    return en + bigrams


def search_fn(arguments: dict, ctx) -> str:
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ValueError("query 不能为空")
    query_tokens = set(_tokens(query))
    scored = []
    for doc in _DOCS:
        doc_tokens = _tokens(doc["title"] + doc["content"])
        score = sum(1 for t in query_tokens if t in doc_tokens)
        if score:
            scored.append((score, doc))
    if not scored:
        return f"未找到与 {query!r} 相关的文档"
    scored.sort(key=lambda x: -x[0])
    lines = []
    for score, doc in scored[:3]:
        lines.append(f"[{doc['title']}] (相关度 {score})\n{doc['content'][:120]}")
    return "\n\n".join(lines)


TOOL = Tool(
    name="search",
    description="在内置文档库中检索资料（mock 实现），返回最相关的文档片段",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词"},
        },
        "required": ["query"],
    },
    fn=search_fn,
)
