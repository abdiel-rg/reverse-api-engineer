"""Oh My Pi CLI integration for API reverse engineering."""

from __future__ import annotations

import asyncio
import shutil
from typing import Any

from .base_engineer import BaseEngineer


class OMPEngineer(BaseEngineer):
    """Run code generation through the user's configured Oh My Pi CLI."""

    def __init__(self, *args: Any, omp_model: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.omp_model = omp_model.strip() if isinstance(omp_model, str) else ""

    async def _run_omp(self, system_prompt: str, user_message: str) -> bool:
        executable = shutil.which("omp")
        if executable is None:
            self.ui.error("Oh My Pi CLI not found in PATH. Install OMP and configure its provider credentials first.")
            return False

        args = [
            executable,
            "--print",
            "--no-session",
            "--cwd",
            str(self.scripts_dir.parent.parent),
            "--system-prompt",
            system_prompt,
        ]
        if self.omp_model:
            args.extend(["--model", self.omp_model])
        args.append(user_message)

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(self.scripts_dir.parent.parent),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
        except TimeoutError:
            process.kill()
            await process.wait()
            self.ui.error("OMP session timed out after 10 minutes")
            self.message_store.save_error("OMP session timed out")
            return False
        except OSError as exc:
            error_message = str(exc)
            self.ui.error(f"Could not start OMP: {error_message}")
            self.message_store.save_error(error_message)
            return False

        output = stdout.decode("utf-8", errors="replace").strip()
        if output:
            self.ui.thinking(output)
            self.message_store.save_thinking(output)
        if process.returncode:
            error = stderr.decode("utf-8", errors="replace").strip() or f"OMP exited with status {process.returncode}"
            self.ui.error(error)
            self.message_store.save_error(error)
            return False
        return True

    async def analyze_and_generate(self) -> dict[str, Any] | None:
        self.ui.header(self.run_id, self.prompt, self.omp_model or "OMP configured model", self.sdk, mode="engineer")
        self.ui.start_analysis()
        system_prompt, user_message = self._build_prompts()
        self.message_store.save_prompt(user_message)
        if not await self._run_omp(system_prompt, user_message):
            return None

        script_path = str(self.scripts_dir / self._get_client_filename())
        result = {"script_path": script_path, "usage": self.usage_metadata}
        self.ui.success(script_path, str(self.local_scripts_dir / self._get_client_filename()) if self.local_scripts_dir else None)
        self.message_store.save_result(result)
        return result
