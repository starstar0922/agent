"""主循环测试：直接回复 / 工具调用 / 多步链 / 错误回传 / 步数保护 / trace。"""
from agent.llm import LLMError
from conftest import answer_json, tool_json


def test_direct_answer_without_tool(make_agent):
    agent, llm = make_agent([answer_json("你好，有什么可以帮你？")])
    ans = agent.run("s1", "你好")
    assert ans == "你好，有什么可以帮你？"
    assert len(llm.calls) == 1  # 一次 LLM 调用即可回答


def test_tool_call_then_answer(make_agent):
    agent, llm = make_agent([
        tool_json("calculator", {"expression": "(3+5)*2"}),
        answer_json("(3+5)*2 = 16"),
    ])
    ans = agent.run("s1", "帮我算 (3+5)*2")
    assert ans == "(3+5)*2 = 16"
    # 第二次调用时，上下文必须包含工具结果
    result_msgs = [
        m for m in llm.calls[1]
        if m["content"].startswith("[工具结果 calculator]")
    ]
    assert result_msgs and "16" in result_msgs[0]["content"]


def test_multi_step_chain(make_agent):
    agent, llm = make_agent([
        tool_json("search", {"query": "工具注册"}),
        tool_json("calculator", {"expression": "2+2"}),
        answer_json("资料已查到，2+2=4"),
    ])
    ans = agent.run("s1", "查一下工具注册的资料，再算 2+2")
    assert ans == "资料已查到，2+2=4"
    assert len(agent.sessions.get("s1").turns[0].steps) == 2


def test_tool_error_is_fed_back(make_agent):
    agent, llm = make_agent([
        tool_json("weather", {"city": "火星"}),
        answer_json("抱歉，天气数据不支持火星。"),
    ])
    ans = agent.run("s1", "查火星天气")
    assert ans == "抱歉，天气数据不支持火星。"
    err_msgs = [
        m for m in llm.calls[1]
        if m["content"].startswith("[工具结果 weather]")
    ]
    assert err_msgs and "[错误]" in err_msgs[0]["content"]


def test_max_loop_steps_guards_infinite_loop(make_agent):
    agent, llm = make_agent([tool_json("calculator", {"expression": "1+1"})] * 10)
    ans = agent.run("s1", "无限循环测试")
    assert "次数过多" in ans
    assert len(agent.sessions.get("s1").turns[0].steps) == 5


def test_tool_trace_is_recorded(make_agent):
    agent, llm = make_agent([
        tool_json("todo", {"action": "add", "text": "买牛奶"}),
        answer_json("已记下待办：买牛奶"),
    ])
    agent.run("s1", "记个待办：买牛奶")
    trace = agent.sessions.get("s1").trace
    kinds = [e["kind"] for e in trace]
    assert "llm" in kinds and kinds.count("tool") == 1
    tool_entry = next(e for e in trace if e["kind"] == "tool")
    assert tool_entry["name"] == "todo" and tool_entry["ok"] is True


def test_llm_failure_returns_friendly_error(make_agent):
    agent, _ = make_agent([])

    class BrokenLLM:
        def chat(self, messages):
            raise LLMError("网络超时")

    agent.llm = BrokenLLM()
    ans = agent.run("s1", "你好")
    assert "失败" in ans and "网络超时" in ans
