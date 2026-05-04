from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import shlex

from sqlalchemy import select

from jarvis_multiagent.core.config import settings
from jarvis_multiagent.db.models import Approval, ExecutionLog, Task
from jarvis_multiagent.db.session import SessionLocal


ALLOWED_COMMANDS = {"python", "pytest", "npm", "node", "uvicorn", "pip", "ls", "cat", "echo", "mkdir", "touch"}
RISKY_COMMANDS = {"pip", "npm"}
RISKY_PATTERNS = {
    ("python", "-m", "pip"),
    ("npm", "install"),
    ("npm", "i"),
    ("pip", "install"),
}
SHELL_META = {"|", "&", ";", "<", ">", "`", "$", "\n", "\r"}
SAFE_ENV_KEYS = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "PYTHONPATH"}


@dataclass
class CommandPolicyResult:
    allowed: bool
    reason: str
    requires_approval: bool = False
    parts: list[str] | None = None


@dataclass
class CommandExecutionResult:
    allowed: bool
    status: str
    reason: str
    requires_approval: bool = False
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""


def validate_command(cmd: str, workspace: str = "/workspace") -> CommandPolicyResult:
    if not cmd or not cmd.strip():
        return CommandPolicyResult(False, "Empty command")
    if any(token in cmd for token in SHELL_META) or "&&" in cmd or "||" in cmd:
        return CommandPolicyResult(False, "Shell operators are blocked")

    try:
        parts = shlex.split(cmd, posix=os.name != "nt")
    except ValueError:
        return CommandPolicyResult(False, "Invalid shell syntax")
    if not parts:
        return CommandPolicyResult(False, "Empty command")

    base = _base_command(parts[0])
    if base not in ALLOWED_COMMANDS:
        return CommandPolicyResult(False, "Command not in strict allowlist", parts=parts)

    workspace_path = Path(workspace).resolve()
    for token in parts[1:]:
        if _looks_like_path(token):
            if not _path_stays_in_workspace(token, workspace_path):
                return CommandPolicyResult(False, "Path traversal or path outside workspace blocked", parts=parts)

    return CommandPolicyResult(True, "Allowed", requires_approval=_requires_approval(parts), parts=parts)


class SandboxExecutor:
    async def execute(
        self,
        command: str,
        *,
        workspace: str = "/workspace",
        task_public_id: str | None = None,
        approved: bool = False,
    ) -> CommandExecutionResult:
        policy = validate_command(command, workspace)
        if not policy.allowed:
            await self._log(command, workspace, "blocked", policy.reason, policy.requires_approval)
            return CommandExecutionResult(False, "blocked", policy.reason, policy.requires_approval)

        task_db_id = await self._task_db_id(task_public_id)
        if policy.requires_approval and not approved:
            await self._create_approval(task_db_id, command)
            await self._log(command, workspace, "approval_required", policy.reason, True, task_db_id)
            return CommandExecutionResult(True, "approval_required", "Approval required before execution", True)

        workspace_path = Path(workspace).resolve()
        if not workspace_path.exists() or not workspace_path.is_dir():
            await self._log(command, workspace, "blocked", "Workspace does not exist", policy.requires_approval, task_db_id)
            return CommandExecutionResult(False, "blocked", "Workspace does not exist", policy.requires_approval)

        try:
            process = await asyncio.create_subprocess_exec(
                *(policy.parts or []),
                cwd=str(workspace_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_safe_env(),
            )
            stdout_raw, stderr_raw = await asyncio.wait_for(process.communicate(), timeout=settings.sandbox_timeout_seconds)
            stdout = _truncate(stdout_raw.decode("utf-8", errors="replace"))
            stderr = _truncate(stderr_raw.decode("utf-8", errors="replace"))
            status = "completed" if process.returncode == 0 else "failed"
            await self._log(command, workspace, status, "Executed", policy.requires_approval, task_db_id, process.returncode, stdout, stderr)
            return CommandExecutionResult(True, status, "Executed", policy.requires_approval, process.returncode, stdout, stderr)
        except asyncio.TimeoutError:
            await self._log(command, workspace, "timeout", "Execution timed out", policy.requires_approval, task_db_id)
            return CommandExecutionResult(True, "timeout", "Execution timed out", policy.requires_approval)
        except Exception as exc:
            await self._log(command, workspace, "failed", str(exc), policy.requires_approval, task_db_id)
            return CommandExecutionResult(True, "failed", str(exc), policy.requires_approval)

    async def _task_db_id(self, public_id: str | None) -> int | None:
        if not public_id:
            return None
        async with SessionLocal() as session:
            task = await session.scalar(select(Task).where(Task.public_id == public_id))
            return task.id if task else None

    async def _create_approval(self, task_id: int | None, action: str) -> None:
        if task_id is None:
            return
        async with SessionLocal() as session:
            session.add(Approval(task_id=task_id, action=action, approved=False))
            await session.commit()

    async def _log(
        self,
        command: str,
        workspace: str,
        status: str,
        reason: str,
        requires_approval: bool,
        task_id: int | None = None,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        async with SessionLocal() as session:
            session.add(
                ExecutionLog(
                    task_id=task_id,
                    command=command,
                    cwd=workspace,
                    status=status,
                    reason=reason,
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                    requires_approval=requires_approval,
                )
            )
            await session.commit()


def _base_command(command: str) -> str:
    return Path(command).name.lower().removesuffix(".exe")


def _requires_approval(parts: list[str]) -> bool:
    normalized = tuple(_base_command(part) if index == 0 else part.lower() for index, part in enumerate(parts[:3]))
    base = normalized[0]
    return base in RISKY_COMMANDS or any(normalized[: len(pattern)] == pattern for pattern in RISKY_PATTERNS)


def _looks_like_path(token: str) -> bool:
    if token.startswith(("-", "http://", "https://")):
        return False
    return (
        token.startswith((".", "/", "\\", "~"))
        or ":" in token[:3]
        or "/" in token
        or "\\" in token
    )


def _path_stays_in_workspace(token: str, workspace: Path) -> bool:
    if ".." in Path(token).parts:
        return False
    raw = Path(token).expanduser()
    candidate = raw.resolve() if raw.is_absolute() else (workspace / raw).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError:
        return False
    return True


def _safe_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key.upper() in SAFE_ENV_KEYS}


def _truncate(text: str) -> str:
    limit = settings.sandbox_max_output_chars
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"
