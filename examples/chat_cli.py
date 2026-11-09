"""交互式 CLI：演示多窗口 session 隔离、恢复与工具调用 trace。

运行方式（项目根目录）：
  python -m examples.chat_cli
  python examples/chat_cli.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import Agent, Config, LLMClient, SessionManager, build_default_registry

HELP = """命令：
  /new <id>      创建并切换到一个新的会话窗口
  /switch <id>   切换到已有的会话窗口（随时接着聊）
  /list          列出所有窗口
  /trace [n]     查看当前窗口最近 n 条执行 trace（默认 10）
  /help          显示帮助
  /quit          退出（自动保存会话）"""


def main():
    config = Config.from_env()
    if not config.api_key:
        print("错误：未设置环境变量 AGENT_API_KEY（密钥绝不写入代码），示例：")
        print('  Windows CMD : set AGENT_API_KEY=sk-xxxx')
        print('  PowerShell  : $env:AGENT_API_KEY="sk-xxxx"')
        print(f"  可选：AGENT_BASE_URL（默认 {config.base_url}）、AGENT_MODEL（默认 {config.model}）")
        return

    sessions = SessionManager(config.session_file)
    agent = Agent(LLMClient(config), build_default_registry(), sessions, config)

    current = "default"
    print("MiniAgent CLI 已启动（多窗口会话演示）")
    print(HELP)
    print(f"当前窗口: {current}")

    while True:
        try:
            line = input(f"[{current}] 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not line:
            continue
        if line == "/quit":
            break
        if line == "/help":
            print(HELP)
            continue
        if line == "/list":
            for s in sessions.list_sessions():
                print(f"  - {s.session_id}（{len(s.turns)} 轮对话）")
            continue
        if line.startswith("/new ") or line.startswith("/switch "):
            current = line.split(maxsplit=1)[1].strip()
            sessions.get_or_create(current)
            print(f"已切换到窗口: {current}")
            continue
        if line.startswith("/trace"):
            parts = line.split()
            n = int(parts[1]) if len(parts) > 1 else 10
            for entry in sessions.get_or_create(current).trace[-n:]:
                print(" ", json.dumps(entry, ensure_ascii=False))
            continue

        try:
            answer = agent.run(current, line)
        except Exception as exc:
            answer = f"运行出错: {exc}"
        print(f"[{current}] Agent: {answer}")

    sessions.save()
    print(f"会话已保存到 {config.session_file}")


if __name__ == "__main__":
    main()
