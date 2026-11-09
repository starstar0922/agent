"""输出解析测试：思考 / 工具调用 / 最终答案的提取与容错。"""
from agent.parser import OutputParser

parser = OutputParser()


def test_parse_tool_call():
    action = parser.parse(
        '{"thinking": "先算一下", "tool_calls": [{"name": "calculator", "arguments": {"expression": "1+1"}}]}'
    )
    assert action.has_tool_calls
    assert action.thinking == "先算一下"
    assert action.tool_calls[0].name == "calculator"
    assert action.tool_calls[0].arguments == {"expression": "1+1"}


def test_parse_final_answer():
    action = parser.parse('{"thinking": "直接回答", "final_answer": "你好"}')
    assert action.final_answer == "你好"
    assert not action.has_tool_calls


def test_parse_code_fence():
    action = parser.parse('```json\n{"thinking": "t", "final_answer": "hi"}\n```')
    assert action.final_answer == "hi"


def test_parse_text_with_json_inside():
    action = parser.parse('好的，结果如下：{"thinking": "t", "final_answer": "ok"}')
    assert action.final_answer == "ok"


def test_parse_malformed_falls_back_to_text():
    action = parser.parse("抱歉，我无法理解这个问题。")
    assert action.final_answer == "抱歉，我无法理解这个问题。"
    assert not action.has_tool_calls


def test_parse_both_prefers_tool_calls():
    raw = '{"thinking": "t", "tool_calls": [{"name": "weather", "arguments": {"city": "北京"}}], "final_answer": "x"}'
    action = parser.parse(raw)
    assert action.has_tool_calls
    assert not action.final_answer


def test_parse_invalid_tool_call_entry_filtered():
    action = parser.parse('{"thinking": "t", "tool_calls": [{"name": 123}]}')
    assert not action.has_tool_calls
    assert action.final_answer == "t"  # 兜底：思考内容当答案


def test_parse_empty_input():
    action = parser.parse("")
    assert not action.has_tool_calls
    assert action.final_answer
