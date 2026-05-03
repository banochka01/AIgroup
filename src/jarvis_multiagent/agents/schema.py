from dataclasses import dataclass, field


@dataclass
class AgentProfile:
    name: str
    role: str
    system_prompt: str
    skills: list[str] = field(default_factory=list)


DEFAULT_PROFILES = [
    AgentProfile("FrontendBot", "frontend", "You build UI and frontend architecture.", ["html", "css", "react"]),
    AgentProfile("BackendBot", "backend", "You build APIs and data models.", ["python", "fastapi", "sql"]),
    AgentProfile("QABot", "qa", "You test quality and regressions.", ["tests", "review"]),
    AgentProfile("DevOpsBot", "devops", "You own deployment and infra.", ["docker", "ci/cd"]),
    AgentProfile("DesignerBot", "designer", "You design UX and copy.", ["ux", "branding"]),
    AgentProfile("ManagerBot", "manager", "You coordinate plans, risks, and delivery.", ["planning", "summary"]),
]
