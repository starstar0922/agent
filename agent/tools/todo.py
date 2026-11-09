"""todo 工具：待办事项。状态保存在会话级 state 中，不同窗口互不影响。"""

from .registry import Tool


def _todos(ctx):
    return ctx.state.setdefault("todos", [])


def _render(items):
    if not items:
        return "待办列表为空"
    lines = []
    for it in items:
        mark = "✓" if it["done"] else "○"
        lines.append(f"{it['id']}. [{mark}] {it['text']}")
    return "\n".join(lines)


def todo_fn(arguments: dict, ctx) -> str:
    action = arguments.get("action")
    items = _todos(ctx)
    if action == "add":
        new_id = max((i["id"] for i in items), default=0) + 1
        items.append({"id": new_id, "text": arguments.get("text"), "done": False})
        return f"已添加待办 #{new_id}: {arguments.get('text')}"
    if action == "list":
        return _render(items)
    if action == "complete":
        for it in items:
            if it["id"] == arguments.get("id"):
                it["done"] = True
                return f"待办 #{it['id']} 已完成: {it['text']}"
        return f"未找到 id={arguments.get('id')} 的待办"
    raise ValueError(f"不支持的 action: {action!r}")


TOOL = Tool(
    name="todo",
    description="管理当前会话的待办事项：action=add 添加（需 text）、list 列出、complete 标记完成（需 id）",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list", "complete"]},
            "text": {"type": "string", "description": "待办内容，action=add 时必填"},
            "id": {"type": "integer", "description": "待办编号，action=complete 时必填"},
        },
        "required": ["action"],
    },
    fn=todo_fn,
)
