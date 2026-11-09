"""calculator 工具：基于 AST 白名单的安全表达式求值，杜绝 eval 注入。"""
import ast
import operator

from .registry import Tool

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


class CalculatorError(ValueError):
    pass


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise CalculatorError(f"不支持的值: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise CalculatorError(f"不支持的语法: {type(node).__name__}")


def calculate(expression: str) -> float:
    tree = ast.parse(expression.strip(), mode="eval")
    return round(_eval_node(tree), 10)


def calculator_fn(arguments: dict, ctx) -> str:
    return str(calculate(str(arguments.get("expression", ""))))


TOOL = Tool(
    name="calculator",
    description="安全计算数学表达式，支持 + - * / // % ** 与括号，例如 (3+5)*2",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式"},
        },
        "required": ["expression"],
    },
    fn=calculator_fn,
)
