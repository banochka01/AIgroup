from dataclasses import dataclass
from pathlib import Path
import shlex


ALLOWED_COMMANDS = {"python", "pytest", "npm", "node", "uvicorn", "pip", "ls", "cat", "echo", "mkdir", "touch"}
RISKY_COMMANDS = {"pip", "npm"}
BLOCKED_PATHS = {"/etc", "/root", "/home"}


@dataclass
class CommandPolicyResult:
    allowed: bool
    reason: str
    requires_approval: bool = False


def validate_command(cmd: str, workspace: str = "/workspace") -> CommandPolicyResult:
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return CommandPolicyResult(False, "Invalid shell syntax")
    if not parts:
        return CommandPolicyResult(False, "Empty command")

    base = parts[0]
    if base not in ALLOWED_COMMANDS:
        return CommandPolicyResult(False, "Command not in strict allowlist")

    for token in parts[1:]:
        if token.startswith("/") or token.startswith(".."):
            resolved = str((Path(workspace) / token).resolve()) if not token.startswith("/") else token
            if any(resolved.startswith(p) for p in BLOCKED_PATHS) or ".." in token:
                return CommandPolicyResult(False, "Path traversal or protected path blocked")

    return CommandPolicyResult(True, "Allowed", requires_approval=base in RISKY_COMMANDS)
