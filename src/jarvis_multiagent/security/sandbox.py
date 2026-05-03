from dataclasses import dataclass


ALLOWED_COMMAND_PREFIXES = [
    "python", "pytest", "npm", "node", "uvicorn", "pip", "ls", "cat", "echo", "mkdir", "touch"
]
BLOCKED_TOKENS = ["rm -rf", "sudo", "passwd", "~/.ssh", "/etc/shadow", "cookie", "credential"]


@dataclass
class CommandPolicyResult:
    allowed: bool
    reason: str


def validate_command(cmd: str) -> CommandPolicyResult:
    lowered = cmd.lower().strip()
    if any(token in lowered for token in BLOCKED_TOKENS):
        return CommandPolicyResult(False, "Blocked dangerous command token.")
    if not any(lowered.startswith(prefix) for prefix in ALLOWED_COMMAND_PREFIXES):
        return CommandPolicyResult(False, "Command not in whitelist.")
    return CommandPolicyResult(True, "Allowed")
