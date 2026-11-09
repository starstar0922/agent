"""上下文测试：信息放置、轮次上限与基础压缩、追问所需的记忆保留。"""
from conftest import answer_json, tool_json


def test_max_turns_triggers_compression(make_agent):
    agent, llm = make_agent([answer_json(f"回答{i}") for i in range(6)])
    for i in range(6):
        agent.run("s1", f"问题{i}")

    session = agent.sessions.get("s1")
    assert len(session.turns) == 4          # max_history_turns=4
    assert session.summary == "（历史摘要）"
    summarize_calls = [
        c for c in llm.calls
        if any(m["role"] == "system" and "压缩" in m["content"] for m in c)
    ]
    assert summarize_calls


def test_compression_keeps_latest_and_in_progress_turn(make_agent):
    agent, llm = make_agent([answer_json(f"回答{i}") for i in range(5)])
    for i in range(5):
        agent.run("s1", f"问题{i}")

    # 第 6 轮：先调工具再回答，压缩不能吃掉进行中的轮次
    llm.script = [tool_json("calculator", {"expression": "1+1"}), answer_json("2")]
    agent.run("s1", "问题5")

    session = agent.sessions.get("s1")
    assert len(session.turns) == 4
    assert session.turns[-1].user_input == "问题5"
    assert session.turns[-1].final_answer == "2"


def test_context_contains_tool_schemas_and_summary(make_agent):
    agent, llm = make_agent([answer_json("ok")])
    agent.sessions.get_or_create("s1").summary = "之前用户问过北京天气"
    agent.run("s1", "你好")

    messages = llm.calls[-1]
    sys_content = "\n".join(m["content"] for m in messages if m["role"] == "system")
    # 工具 Schema 与历史摘要都放在 system 区域
    assert "calculator" in sys_content and "todo" in sys_content
    assert "之前用户问过北京天气" in sys_content


def test_thinking_tool_call_and_result_all_in_context(make_agent):
    agent, llm = make_agent([
        tool_json("calculator", {"expression": "1+2"}, thinking="需要先计算"),
        answer_json("3"),
    ])
    agent.run("s1", "1+2 等于几？")

    second_call = llm.calls[1]
    joined = "\n".join(m["content"] for m in second_call)
    assert "[思考] 需要先计算" in joined
    assert "[工具调用] calculator" in joined
    assert "[工具结果 calculator] 3" in joined
