from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class ToolStep:
    name: str
    status: str
    message: Optional[str] = None


@dataclass
class AgentTrace:
    question: str
    mode: str
    intent: Optional[str]
    selected_tool: Optional[str]
    tool_kind: Optional[str]
    live_api_used: bool = False
    evidence_files: list[str] = field(default_factory=list)
    steps: list[ToolStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    result_preview: Optional[dict[str, Any]] = None

    def add_step(self, name: str, status: str = "ok", message: Optional[str] = None) -> None:
        self.steps.append(ToolStep(name=name, status=status, message=message))

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
