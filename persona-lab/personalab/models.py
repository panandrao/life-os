"""Data models: personas and run configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Persona(BaseModel):
    """A persona card. Core fields are typed; any extra fields supplied in
    YAML are preserved and rendered onto the card, so richer personas need
    no code changes."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    role: str
    department: str
    category: str = "faculty"  # faculty | staff | student | external ...
    pronouns: Optional[str] = None
    age: Optional[int] = None
    years_at_institution: Optional[int] = None
    education: Optional[str] = None
    background: Optional[str] = None
    personality: Optional[dict[str, Any]] = None
    values: Optional[list[str]] = None
    viewpoints: Optional[str] = None
    quirks: Optional[str] = None

    def card(self) -> str:
        """Render the persona as a markdown card for the prompt."""
        lines = [f"# Persona: {self.name}"]
        if self.pronouns:
            lines.append(f"Pronouns: {self.pronouns}")
        lines.append(f"Role: {self.role} — {self.department}")
        lines.append(f"Category: {self.category}")
        if self.age is not None:
            lines.append(f"Age: {self.age}")
        if self.years_at_institution is not None:
            lines.append(f"Years at the institution: {self.years_at_institution}")
        if self.education:
            lines.append(f"Education: {self.education}")
        if self.background:
            lines.append(f"\n## Background\n{self.background.strip()}")
        if self.personality:
            lines.append("\n## Personality")
            for k, v in self.personality.items():
                lines.append(f"- {k.replace('_', ' ').capitalize()}: {v}")
        if self.values:
            lines.append("\n## Core values\n" + "\n".join(f"- {v}" for v in self.values))
        if self.viewpoints:
            lines.append(f"\n## Viewpoints and concerns\n{self.viewpoints.strip()}")
        if self.quirks:
            lines.append(f"\n## Quirks\n{self.quirks.strip()}")
        extras = self.model_extra or {}
        for k, v in extras.items():
            lines.append(f"\n## {k.replace('_', ' ').capitalize()}\n{v}")
        return "\n".join(lines)


class PersonasConfig(BaseModel):
    path: str  # file or directory of YAML persona files
    include: Optional[list[str]] = None  # persona ids to include
    exclude: Optional[list[str]] = None
    sample: Optional[int] = None  # random sample of N (after include/exclude)
    seed: int = 7


class MaterialConfig(BaseModel):
    path: str
    label: Optional[str] = None


class ResponseFormat(BaseModel):
    """JSON schema the personas must answer in (enforced via forced tool use)."""

    schema_: dict[str, Any] = Field(alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class GroupsConfig(BaseModel):
    enabled: bool = False
    size: int = 5  # used for auto-assignment
    rounds: int = 2
    assignments: Optional[dict[str, list[str]]] = None  # group name -> persona ids
    moderator_prompt: Optional[str] = None  # scripted moderator framing
    summarize: bool = True  # per-group LLM summary after discussion


class RunConfig(BaseModel):
    name: str = "persona-lab-run"
    personas: PersonasConfig
    materials: list[MaterialConfig]
    instructions: str  # what the personas are asked to do individually
    group_instructions: Optional[str] = None  # task framing for the group phase
    response_format: ResponseFormat
    groups: GroupsConfig = GroupsConfig()
    resurvey: bool = False  # re-ask the individual questions after discussion

    individual_model: str = "claude-haiku-4-5"
    group_model: str = "claude-sonnet-5"
    synthesis_model: str = "claude-sonnet-5"
    max_output_tokens: int = 2000
    concurrency: int = 8
    temperature: float = 1.0

    @field_validator("materials")
    @classmethod
    def _at_least_one_material(cls, v):
        if not v:
            raise ValueError("at least one material is required")
        return v

    @classmethod
    def load(cls, path: str | Path) -> "RunConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


# Rough $/MTok pricing used only for post-run cost reporting.
PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0, "cache_read": 0.10, "cache_write": 1.25},
    "claude-sonnet-5": {"in": 2.0, "out": 10.0, "cache_read": 0.20, "cache_write": 2.50},
    "claude-opus-5": {"in": 5.0, "out": 25.0, "cache_read": 0.50, "cache_write": 6.25},
}


def price_for(model: str) -> dict[str, float]:
    for key, p in PRICING.items():
        if model.startswith(key):
            return p
    return {"in": 0.0, "out": 0.0, "cache_read": 0.0, "cache_write": 0.0}
