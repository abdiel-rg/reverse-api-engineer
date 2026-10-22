"""Regression tests for OMP agent mode MCP workspace setup."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from reverse_api.auto_engineer import OMPAutoEngineer


@pytest.mark.asyncio
async def test_omp_agent_registers_browser_mcp_and_cleans_temporary_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "output"
    engineer = OMPAutoEngineer(
        run_id="run-1",
        prompt="Inspect the site",
        output_dir=str(output_dir),
        verbose=False,
    )
    assert engineer.sdk == "omp"

    browser_config = {
        "type": "stdio",
        "command": "npx",
        "args": ["rae-playwright-mcp@latest", "run-mcp-server", "--run-id", "run-1"],
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr("reverse_api.omp_engineer.shutil.which", lambda _: "/usr/bin/omp")

    async def fake_create_subprocess_exec(*args: str, **kwargs: Any) -> SimpleNamespace:
        captured["args"] = args
        captured["kwargs"] = kwargs
        workspace = Path(kwargs["cwd"])
        config_path = workspace / ".omp" / "mcp.json"
        captured["config_text"] = config_path.read_text(encoding="utf-8")
        captured["config_path"] = config_path
        return SimpleNamespace(
            communicate=lambda: asyncio.sleep(0, result=(b"", b"")),
            returncode=0,
        )

    monkeypatch.setattr(
        "reverse_api.omp_engineer.asyncio.create_subprocess_exec", fake_create_subprocess_exec
    )

    assert await engineer._run_omp("system", "user", {"playwright": browser_config})

    args = captured["args"]
    workspace = Path(captured["kwargs"]["cwd"])
    assert captured["config_text"] == json.dumps({"mcpServers": {"playwright": browser_config}})
    assert args[args.index("--add-dir") + 1] == str(engineer.scripts_dir.parent.parent)
    assert captured["kwargs"]["cwd"] == str(workspace)
    assert not workspace.exists()


@pytest.mark.asyncio
async def test_omp_auto_uses_native_browser_and_rejects_success_without_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engineer = OMPAutoEngineer(
        run_id="run-3",
        prompt="Inspect https://example.com",
        output_dir=str(tmp_path / "output"),
        verbose=False,
    )
    captured: dict[str, Any] = {}

    async def fake_run_omp(
        system_prompt: str,
        user_message: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> bool:
        captured["system_prompt"] = system_prompt
        captured["user_message"] = user_message
        captured["mcp_servers"] = mcp_servers
        return True

    monkeypatch.setattr(engineer, "_run_omp", fake_run_omp)

    assert await engineer.analyze_and_generate() is None
    assert captured["mcp_servers"] is None
    assert "OMP Eval browser facade" in captured["system_prompt"]
    assert "app: { relay: false, tern: false }" in captured["user_message"]
    assert "timeout: 120" in captured["user_message"]
    assert "tab.harStart" in captured["user_message"]
    assert "tab.harStop" in captured["user_message"]
    assert str(engineer.har_path) in captured["user_message"]


@pytest.mark.parametrize(
    ("agent_provider", "har_content", "accepted"),
    [
        ("auto", "not json", False),
        ("auto", '{"log":{"entries":[]}}', False),
        ("auto", '{"log":{"entries":[{"request":{"url":"https://example.com/"}}]}}', True),
        ("chrome-mcp", None, True),
    ],
)
@pytest.mark.asyncio
async def test_omp_auto_accepts_only_valid_capture_except_chrome(
    agent_provider: str,
    har_content: str | None,
    accepted: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engineer = OMPAutoEngineer(
        run_id="run-4",
        prompt="Inspect the site",
        output_dir=str(tmp_path / "output"),
        agent_provider=agent_provider,
        verbose=False,
    )

    async def fake_run_omp(
        system_prompt: str,
        user_message: str,
        mcp_servers: dict[str, dict[str, Any]] | None = None,
    ) -> bool:
        script = engineer.scripts_dir / "api_client.py"
        script.write_text("print('ok')", encoding="utf-8")
        if har_content is not None:
            engineer.har_path.parent.mkdir(parents=True, exist_ok=True)
            engineer.har_path.write_text(har_content, encoding="utf-8")
        return True

    monkeypatch.setattr(engineer, "_run_omp", fake_run_omp)

    result = await engineer.analyze_and_generate()

    assert (result is not None) is accepted


def test_omp_engineer_without_mcp_uses_output_workspace_without_add_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reverse_api.omp_engineer import OMPEngineer

    engineer = OMPEngineer(
        run_id="run-2",
        har_path=tmp_path / "recording.har",
        prompt="Inspect the site",
        output_dir=str(tmp_path / "output"),
        verbose=False,
    )
    captured: dict[str, Any] = {}

    monkeypatch.setattr("reverse_api.omp_engineer.shutil.which", lambda _: "/usr/bin/omp")

    async def fake_create_subprocess_exec(*args: str, **kwargs: Any) -> SimpleNamespace:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            communicate=lambda: asyncio.sleep(0, result=(b"", b"")),
            returncode=0,
        )

    monkeypatch.setattr(
        "reverse_api.omp_engineer.asyncio.create_subprocess_exec", fake_create_subprocess_exec
    )

    assert asyncio.run(engineer._run_omp("system", "user"))

    args = captured["args"]
    output_workspace = engineer.scripts_dir.parent.parent
    assert args[args.index("--cwd") + 1] == str(output_workspace)
    assert captured["kwargs"]["cwd"] == str(output_workspace)
    assert "--add-dir" not in args
