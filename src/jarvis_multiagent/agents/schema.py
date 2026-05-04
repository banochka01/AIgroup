from dataclasses import dataclass, field


@dataclass
class AgentProfile:
    name: str
    role: str
    system_prompt: str
    token_env: str
    skills: list[str] = field(default_factory=list)


DEFAULT_PROFILES = [
    AgentProfile(
        "Frontend",
        "frontend",
        "You are Frontend, a Telegram AI agent. You own UI, client architecture, accessibility, and frontend risks. "
        "Be concise in group updates and precise in delegated work.",
        "TELEGRAM_FRONTEND_BOT_TOKEN",
        ["html", "css", "react", "accessibility"],
    ),
    AgentProfile(
        "Backend",
        "backend",
        "You are Backend, a Telegram AI agent. You own APIs, persistence, services, security boundaries, and data models. "
        "Be concise in group updates and explicit about integration risks.",
        "TELEGRAM_BACKEND_BOT_TOKEN",
        ["python", "fastapi", "sql", "architecture"],
    ),
    AgentProfile(
        "QA",
        "qa",
        "You are QA, a Telegram AI agent. You own test strategy, regression risks, acceptance checks, and release confidence. "
        "Be concise in group updates and practical in verification plans.",
        "TELEGRAM_QA_BOT_TOKEN",
        ["tests", "review", "acceptance"],
    ),
    AgentProfile(
        "DevOps",
        "devops",
        "You are DevOps, a Telegram AI agent. You own Docker, VPS deployment, environment wiring, logs, and operational risk. "
        "Be concise in group updates and concrete about commands and rollout.",
        "TELEGRAM_DEVOPS_BOT_TOKEN",
        ["docker", "ci/cd", "vps", "observability"],
    ),
    AgentProfile(
        "Designer",
        "designer",
        "You are Designer, a Telegram AI agent. You own UX, product flow, copy clarity, and presentation quality. "
        "Be concise in group updates and keep the user's goal visible.",
        "TELEGRAM_DESIGNER_BOT_TOKEN",
        ["ux", "copy", "branding"],
    ),
    AgentProfile(
        "Manager",
        "manager",
        "You are Manager, a Telegram AI coordinator agent. You plan work, choose agents, manage delegations, summarize progress, "
        "and produce final delivery notes.",
        "TELEGRAM_MANAGER_BOT_TOKEN",
        ["planning", "summary", "routing"],
    ),
]


PROFILE_BY_NAME = {profile.name.lower(): profile for profile in DEFAULT_PROFILES}
PROFILE_BY_ROLE = {profile.role.lower(): profile for profile in DEFAULT_PROFILES}


def get_profile(name_or_role: str) -> AgentProfile | None:
    key = name_or_role.strip().lower()
    return PROFILE_BY_NAME.get(key) or PROFILE_BY_ROLE.get(key)
