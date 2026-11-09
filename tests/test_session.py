"""Session 测试：多窗口隔离、随时恢复、追问（纯对话 + 带工具）、文件持久化。"""
from conftest import answer_json, tool_json


def test_two_windows_are_isolated(make_agent):
    # 窗口 1：查天气 + 记待办
    agent, llm = make_agent([
        tool_json("weather", {"city": "北京"}),
        tool_json("todo", {"action": "add", "text": "明天带伞"}),
        answer_json("北京今天晴，已记下待办：明天带伞。"),
    ])
    agent.run("window_1", "查北京天气，并记待办：明天带伞")

    # 窗口 2：写周报 + 记待办（同一用户、不同窗口）
    llm.script = [
        tool_json("todo", {"action": "add", "text": "周五前交周报"}),
        answer_json("已记下待办：周五前交周报。"),
    ]
    agent.run("window_2", "提醒我周五前交周报")

    s1 = agent.sessions.get("window_1")
    s2 = agent.sessions.get("window_2")
    # 待办状态彼此隔离
    assert [t["text"] for t in s1.state["todos"]] == ["明天带伞"]
    assert [t["text"] for t in s2.state["todos"]] == ["周五前交周报"]
    # 对话历史彼此隔离
    assert "写周报" not in "\n".join(t.user_input for t in s1.turns)
    assert "查北京天气" not in "\n".join(t.user_input for t in s2.turns)


def test_resume_session_keeps_history(make_agent):
    """随时接着窗口继续聊：新回复能看到之前的完整上下文。"""
    agent, llm = make_agent([
        answer_json("北京今天 22°C，晴。"),
        answer_json("不会下雨，不需要带伞。"),
    ])
    agent.run("w1", "北京天气怎么样？")
    agent.run("w1", "那会下雨吗？")  # 纯对话追问

    last_messages = llm.calls[-1]
    joined = "\n".join(m["content"] for m in last_messages)
    assert "北京今天 22°C" in joined
    assert "北京天气怎么样" in joined


def test_followup_with_tool_uses_prior_context(make_agent):
    """带工具的追问：第二轮调用工具时，上下文包含第一轮的结果。"""
    agent, llm = make_agent([
        tool_json("calculator", {"expression": "(3+5)*2"}),
        answer_json("(3+5)*2 = 16"),
        tool_json("calculator", {"expression": "16*3"}),
        answer_json("16*3 = 48"),
    ])
    agent.run("w1", "帮我算 (3+5)*2")
    ans = agent.run("w1", "那再乘以 3 呢？")

    assert ans == "16*3 = 48"
    joined = "\n".join(m["content"] for c in llm.calls for m in c)
    assert "(3+5)*2 = 16" in joined
    assert "[工具结果 calculator] 16" in joined


def test_session_file_persistence_roundtrip(make_agent, tmp_path):
    from agent.session import SessionManager

    file = str(tmp_path / "sessions.json")
    agent, llm = make_agent([
        tool_json("todo", {"action": "add", "text": "买牛奶"}),
        answer_json("已记下待办"),
    ])
    agent.sessions.file_path = file
    agent.run("w1", "记待办：买牛奶")

    # 模拟重启：从文件重新加载
    restored = SessionManager(file).get("w1")
    assert restored is not None
    assert restored.state["todos"][0]["text"] == "买牛奶"
    assert restored.turns[0].user_input == "记待办：买牛奶"
    assert restored.turns[0].steps[0].tool_results[0].ok is True
