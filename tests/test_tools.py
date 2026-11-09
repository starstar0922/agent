"""工具测试：注册机制、参数校验、异常兜底、会话级状态隔离。"""
import pytest

from agent.tools import ToolContext, build_default_registry


@pytest.fixture
def reg():
    return build_default_registry()


def ctx(state=None):
    return ToolContext(session_id="s1", state=state or {})


def test_calculator_basic(reg):
    result = reg.execute("calculator", {"expression": "(3+5)*2"}, ctx())
    assert result.ok and result.output == "16"


def test_calculator_rejects_code_injection(reg):
    result = reg.execute(
        "calculator", {"expression": "__import__('os').system('dir')"}, ctx()
    )
    assert not result.ok
    assert "不支持的语法" in result.error


def test_calculator_division_by_zero(reg):
    result = reg.execute("calculator", {"expression": "1/0"}, ctx())
    assert not result.ok
    assert "ZeroDivisionError" in result.error


def test_calculator_float_precision(reg):
    result = reg.execute("calculator", {"expression": "0.1+0.2"}, ctx())
    assert result.output == "0.3"


def test_todo_add_list_complete(reg):
    state = {}
    c = ToolContext("s1", state)
    reg.execute("todo", {"action": "add", "text": "买牛奶"}, c)
    reg.execute("todo", {"action": "add", "text": "写周报"}, c)
    listed = reg.execute("todo", {"action": "list"}, c)
    assert "买牛奶" in listed.output and "写周报" in listed.output
    done = reg.execute("todo", {"action": "complete", "id": 1}, c)
    assert done.ok
    listed = reg.execute("todo", {"action": "list"}, c)
    assert "✓" in listed.output


def test_todo_state_isolated_by_session(reg):
    reg.execute("todo", {"action": "add", "text": "A 窗口待办"}, ToolContext("win1", {}))
    result = reg.execute("todo", {"action": "list"}, ToolContext("win2", {}))
    assert "待办列表为空" in result.output


def test_weather_known_and_unknown(reg):
    assert reg.execute("weather", {"city": "北京"}, ctx()).ok
    result = reg.execute("weather", {"city": "火星"}, ctx())
    assert not result.ok and "暂不支持" in result.error


def test_search_hit_and_miss(reg):
    hit = reg.execute("search", {"query": "工具注册"}, ctx())
    assert hit.ok and "[工具注册机制]" in hit.output
    miss = reg.execute("search", {"query": "火星文 zzzz"}, ctx())
    assert miss.ok and "未找到" in miss.output


def test_unknown_tool(reg):
    result = reg.execute("no_such_tool", {}, ctx())
    assert not result.ok and "未注册" in result.error


def test_missing_required_arg(reg):
    result = reg.execute("calculator", {}, ctx())
    assert not result.ok and "必填" in result.error


def test_wrong_type_arg(reg):
    result = reg.execute("calculator", {"expression": 123}, ctx())
    assert not result.ok and "字符串" in result.error
