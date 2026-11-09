"""weather 工具（mock）：内置少数城市的模拟天气数据。"""

from .registry import Tool

_WEATHER = {
    "北京": {"condition": "晴", "temp": 22, "humidity": 40, "wind": "东北风 3 级"},
    "上海": {"condition": "多云", "temp": 26, "humidity": 65, "wind": "东南风 2 级"},
    "广州": {"condition": "阵雨", "temp": 29, "humidity": 82, "wind": "南风 3 级"},
    "深圳": {"condition": "阴", "temp": 28, "humidity": 78, "wind": "东南风 3 级"},
    "杭州": {"condition": "小雨", "temp": 24, "humidity": 75, "wind": "东风 2 级"},
    "成都": {"condition": "阴", "temp": 21, "humidity": 70, "wind": "北风 1 级"},
    "武汉": {"condition": "晴", "temp": 27, "humidity": 55, "wind": "西南风 2 级"},
    "西安": {"condition": "晴", "temp": 23, "humidity": 35, "wind": "东风 2 级"},
}


def weather_fn(arguments: dict, ctx) -> str:
    city = str(arguments.get("city", "")).strip()
    info = _WEATHER.get(city)
    if info is None:
        raise ValueError(
            f"暂不支持城市 {city!r}（mock 数据），支持: {', '.join(_WEATHER)}"
        )
    return (
        f"{city}: {info['condition']}，{info['temp']}°C，"
        f"湿度 {info['humidity']}%，{info['wind']}"
    )


TOOL = Tool(
    name="weather",
    description="查询城市天气（mock 数据，仅支持内置城市列表）",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，如 北京"},
        },
        "required": ["city"],
    },
    fn=weather_fn,
)
