# MiniAgent —— 从零实现的最小可用 Agent

不依赖任何 agent 框架（langgraph / openhands / openclaw 等），核心 Agent Runtime 完全自研：
LLM 调用（`requests` 直连 OpenAI 兼容接口）、输出解析、工具注册、Session 管理、上下文压缩均为自写代码。

## 特性对照

| 要求 | 实现 |
| --- | --- |
| 基本 loop（输入 → 判断 → 工具 → 继续/返回） | `agent/runtime.py` 的 `Agent.run` |
| 至少 3 个工具（todo 必须） | calculator、search（mock）、todo、weather（mock） |
| 工具注册机制（名称/描述/Schema） | `agent/tools/registry.py`，含必填与类型校验 |
| LLM 输出解析（思考/工具调用/最终答案） | `agent/parser.py`，多层容错回退 |
| 多窗口独立 session、随时接着聊 | `agent/session.py` + JSON 文件持久化 |
| context 有效管理、最大轮次、记住状态、支持追问 | `agent/context.py`，轮次超限自动压缩 |
| 基础异常处理 | LLM/工具/解析/持久化全链路兜底，单轮步数上限防死循环 |
| 工具调用 trace / 执行日志 | 每会话 trace 环形缓冲 + logging + CLI `/trace` |
| 测试用例 | `tests/`，35 个用例，FakeLLM 离线运行 |
| 不泄漏 API Key | 密钥只读环境变量；`test_security.py` 扫描代码防硬编码 |

## 快速开始

```bash
pip install -r requirements.txt

# 配置密钥（二选一，密钥绝不写入代码）
# 方式一：.env 文件（推荐）——复制 .env.example 为 .env 并填入密钥，
#         启动时自动加载项目根目录的 .env（python-dotenv，路径由 config.py 定位）
AGENT_API_KEY=sk-xxxx
# 方式二：系统环境变量（优先级高于 .env）
# Windows CMD:
set AGENT_API_KEY=sk-xxxx
# PowerShell:
$env:AGENT_API_KEY="sk-xxxx"

# 可选配置（默认值）：
# AGENT_BASE_URL   https://api.openai.com/v1   （DeepSeek: https://api.deepseek.com/v1；Ollama: http://localhost:11434/v1）
# AGENT_MODEL      gpt-4o-mini                 （DeepSeek: deepseek-chat；Qwen: qwen-plus）
# AGENT_MAX_LOOP_STEPS        5   单轮最多工具迭代次数
# AGENT_MAX_HISTORY_TURNS     10  上下文保留轮数上限（超出触发压缩）
# AGENT_SESSION_FILE          data/sessions.json  会话持久化文件

# 启动交互式 CLI（多窗口演示）
python -m examples.chat_cli
```

### 多窗口演示（题目场景）

```
MiniAgent CLI 已启动（多窗口会话演示）
[default] 你: /new 窗口1
已切换到窗口: 窗口1
[窗口1] 你: 查一下北京天气，并记个待办：明天带伞
[窗口1] Agent: 北京今天晴，22°C，已记下待办：明天带伞。

[窗口1] 你: /new 窗口2
已切换到窗口: 窗口2
[窗口2] 你: 提醒我周五前交周报
[窗口2] Agent: 已记下待办：周五前交周报。

[窗口2] 你: /switch 窗口1        ← 随时切回窗口 1 接着聊
已切换到窗口: 窗口1
[窗口1] 你: 明天用带伞吗？
[窗口1] Agent: 你记的待办就是"明天带伞"，北京明天 20°C 多云，建议带上。
```

命令：`/new <id>`、`/switch <id>`、`/list`、`/trace [n]`、`/quit`（退出自动保存会话，重启后 `/switch` 继续聊）。

## 运行测试

```bash
python -m pytest tests -q    # 35 个用例，FakeLLM 脚本化模型，全程离线、无需 API Key
```

## 系统设计

### 总体架构

```
┌─────────────────────────────────────────────────────────┐
│ Agent Runtime（agent/runtime.py）                         │
│   for step in 1..max_loop_steps:                        │
│     messages = ContextBuilder.build(session)  ← 上下文   │
│     raw      = LLMClient.chat(messages)        ← 模型   │
│     action   = OutputParser.parse(raw)         ← 解析   │
│     action.tool_calls? ──有──> ToolRegistry.execute()   │
│         │                          │  (校验+异常兜底)    │
│         └──无──> 返回 final_answer  │                    │
│                          ↓                              │
│              结果写入 session（Turn/Step/trace），继续 loop│
└─────────────────────────────────────────────────────────┘
        SessionManager（每窗口一个 Session：turns/summary/state/trace，JSON 持久化）
```

### Agent Loop 与题目四步的对应

| 题目步骤 | 实现位置 |
| --- | --- |
| Step one 接收用户输入 | `Agent.run(session_id, user_input)`，追加为新 `Turn` |
| Step two 判断直接回复还是调用工具 | LLM 的 JSON 输出本身即决策：有 `tool_calls` → 调工具；有 `final_answer` → 返回 |
| Step three 调用工具 | `ToolRegistry.execute`：参数校验 → 执行 → 异常兜底 → 记录 trace |
| Step four 继续 loop 还是返回 | 工具结果以消息形式进入上下文后 `continue` 循环；`final_answer` 直接返回给用户；步数超限返回兜底话术 |

### 工具注册机制

每个工具是一个 `Tool(name, description, parameters, fn)` 数据类：
- `name` + `description` + `parameters`（JSON Schema）在系统提示词中全量列出，**LLM 基于 Schema 自主决策**调用哪个工具、传什么参数；
- 执行前做必填/类型校验，执行中 try/except 兜底——**任何失败都会转成错误消息回传给 LLM**，由模型自行修正重试或向用户说明；
- `fn(arguments, ctx)` 中的 `ctx` 携带 `session_id` 与会话级 `state`，供 todo 这类有状态工具使用。

内置 4 个工具：

| 工具 | 说明 |
| --- | --- |
| `calculator` | AST 白名单安全求值（拒绝任何调用/名称节点，防注入），支持 `+ - * / // % **` 与括号 |
| `search` | mock：内置 6 篇项目文档，英文词 + 中文二元组打分检索，返回 Top3 片段 |
| `todo` | add / list / complete，**状态存在会话级 `state` 中，窗口之间天然隔离** |
| `weather` | mock：内置 8 个城市，未知城市返回错误（演示错误回传链路） |

### Session 管理

- `Session` 持有：`turns`（对话轮次）、`summary`（压缩摘要）、`state`（会话级工具状态）、`trace`（执行日志环形缓冲）；
- `SessionManager` 以 `session_id` 为键；窗口 1 / 窗口 2 是两个完全独立的 Session，历史、待办、trace 互不可见；
- 每次回答后自动 JSON 落盘（`data/sessions.json`），启动时自动加载——**随时接着任何窗口继续聊**。

### Context 与 memory：召回时机与放置方式

**上下文里放什么（按放置顺序）：**

| 位置 | 角色 | 内容 | 理由 |
| --- | --- | --- | --- |
| 1 | system | 主系统提示词：角色、输出 JSON 格式规范、行为规则、全部工具 Schema | 规则与工具目录是每步决策的依据 |
| 2 | system | 历史对话摘要（压缩产物，可选） | 背景知识，不是需要回应的消息 |
| 3 | user | 用户原始输入 | 用户意图 |
| 4 | assistant | `[思考] … [工具调用] name(args)` | 保留思考链，模型多步推理不中断 |
| 5 | user | `[工具结果 name] …` | 工具反馈，模型据此决定下一步 |
| 6 | assistant | 最终回答 | 对话记忆，支撑追问 |

**召回时机：**
- **每次 loop 迭代前**全量重建消息列表——最近 `max_history_turns` 轮完整召回（含用户输入、思考、工具调用、工具结果、最终回答），这是"记住之前状态、支持追问"的基础；
- **当轮数超过上限时**（构建上下文那一刻）触发压缩：把最老的完整轮次交给 LLM 压缩成要点摘要，摘要存入 `session.summary`，**之后每次构建都随 system 区召回**；压缩失败自动降级为直接丢弃旧轮次，不阻塞主流程；
- **会话级工具状态**（如 todo）不进入文本上下文，而是由模型通过 `todo list` 工具调用**按需召回**，避免上下文膨胀；
- **跨进程召回**：会话 JSON 落盘，重启后自动恢复。

**为什么工具结果用 `user` 角色 + 前缀标签回传**：在非原生 function-calling 的 JSON 输出方案下，OpenAI 兼容接口不接受没有 `tool_call_id` 的 `tool` 角色消息；用 `user` 角色 + 明确的 `[工具结果 <name>]` 前缀是最通用的做法，任何兼容服务都可用。

### 异常处理

| 场景 | 处理 |
| --- | --- |
| LLM 网络/HTTP/响应格式错误 | `LLMError` → 直接向用户返回友好错误 |
| 模型输出非 JSON | 解析器回退：整段文本当最终答案，循环永不卡死 |
| 工具未注册 / 参数缺失 / 类型错误 | 转成错误消息回传 LLM，由模型修正 |
| 工具运行时异常（除零、未知城市…） | registry 兜底捕获，同上 |
| 模型无限调工具 | `max_loop_steps` 上限，超限返回兜底话术 |
| 压缩 LLM 调用失败 | 丢弃旧轮次继续，不影响主流程 |
| 会话文件损坏 | 忽略并从空会话重新开始 |

### 执行日志 / trace

- 每个 Session 维护 100 条 trace 环形缓冲：每次 LLM 调用（thinking 摘要、tool_calls、是否最终回答）与每次工具执行（名称、参数、ok、耗时、输出摘要）；
- 同时通过标准 `logging` 输出到 stderr（CLI 下可实时看到工具调用过程）；
- CLI 内 `/trace [n]` 查看当前窗口最近 n 条 trace。

## 目录结构

```
agent/
├── README.md
├── requirements.txt
├── agent/                     # 核心包（全部自研）
│   ├── config.py              # 环境变量配置
│   ├── llm.py                 # LLM 客户端（OpenAI 兼容接口）
│   ├── parser.py              # 输出解析：思考/工具调用/最终答案
│   ├── context.py             # 上下文构建 + 压缩 + 系统提示词
│   ├── session.py             # Session / SessionManager（多窗口 + 持久化）
│   ├── runtime.py             # Agent Runtime 主循环
│   └── tools/
│       ├── registry.py        # 工具注册机制（校验 + 异常兜底）
│       ├── calculator.py      # AST 安全计算器
│       ├── search.py          # mock 检索
│       ├── todo.py            # 待办（会话级状态）
│       └── weather.py         # mock 天气
├── examples/chat_cli.py       # 多窗口交互式 CLI
├── tests/                     # 35 个 pytest 用例（离线）
│   ├── conftest.py            # FakeLLM 脚本化模型
│   ├── test_parser.py         # 解析与容错
│   ├── test_tools.py          # 工具/校验/注入防护/状态隔离
│   ├── test_loop.py           # 主循环/多步链/错误回传/步数保护/trace
│   ├── test_session.py        # 窗口隔离/恢复/追问/持久化
│   ├── test_context.py        # 信息放置/压缩/进行中轮次保护
│   └── test_security.py       # 代码中无硬编码密钥
└── docs/ai_prompts_and_problem_solving.md   # AI Prompt 与问题解决记录
```

## 关键设计决策

1. **JSON 结构化输出而非原生 function calling**：题目要求自研"LLM 输出解析逻辑"，且 JSON 方案能拿到 `thinking` 字段（原生 tool_calls 没有思考过程），跨服务商通用；
2. **Turn/Step 双层结构**：一轮对话 = 一个 Turn，内含多个 Step（一次"思考+工具调用+结果"迭代），便于渲染、计数与压缩；
3. **todo 状态放会话级 `state`**：既天然实现窗口隔离，又随会话文件持久化；
4. **压缩只作用于完整历史轮次**：进行中的最后一轮永不进入压缩，避免"边对话边丢信息"。

## 安全说明

- API Key 只从环境变量 `AGENT_API_KEY` 读取，代码与测试中不出现任何密钥（`test_security.py` 自动扫描把关）；
- `calculator` 用 AST 白名单求值，`__import__('os').system(...)` 等注入全部被拒；
- 建议将 `data/` 与 `.env` 加入 `.gitignore`（已配置）。
