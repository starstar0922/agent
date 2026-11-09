""".env 加载测试：基于 python-dotenv。"""
import os

from dotenv import load_dotenv


def test_load_dotenv_parses_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# 注释行\n"
        "AGENT_API_KEY=sk-test-123\n"
        'AGENT_MODEL="deepseek-chat"\n'
        "export AGENT_TEMPERATURE=0.5\n"
        "没有等号的行\n",
        encoding="utf-8",
    )
    for name in ("AGENT_API_KEY", "AGENT_MODEL", "AGENT_TEMPERATURE"):
        monkeypatch.delenv(name, raising=False)

    load_dotenv(str(env_file))

    assert os.environ["AGENT_API_KEY"] == "sk-test-123"
    assert os.environ["AGENT_MODEL"] == "deepseek-chat"
    assert os.environ["AGENT_TEMPERATURE"] == "0.5"


def test_load_dotenv_does_not_override_existing_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("AGENT_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("AGENT_API_KEY", "from-env")

    load_dotenv(str(env_file))

    assert os.environ["AGENT_API_KEY"] == "from-env"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    result = load_dotenv(str(tmp_path / "not_exists.env"))
    assert result is False  # 文件不存在：返回 False，不抛异常


def test_config_from_env_loads_project_root_dotenv(monkeypatch):
    import os

    from agent import config as config_module

    seen = []
    monkeypatch.setattr(config_module, "load_dotenv", lambda *a, **k: seen.append(a))
    config_module.Config.from_env()

    assert seen, "from_env 应调用 load_dotenv"
    path = seen[0][0]
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(config_module.__file__)))
    assert path == os.path.join(project_root, ".env")
