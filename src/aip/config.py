"""Read the non-secret role, provider, tool and workflow configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = ".aip/config.yml"
REQUIRED_ROLES = (
    "lead_orchestrator",
    "product_owner",
    "architect",
    "developer",
    "independent_reviewer",
)


@dataclass(frozen=True)
class Config:
    standard_version: int
    architect_reviewer_agent: str | None
    developer_agent: str | None
    github_project: bool
    independent_review_required: bool
    roles: dict
    providers: dict
    tools: dict
    notifications: dict
    raw: dict


def read_config(root: Path) -> Config:
    path = root / CONFIG_PATH
    data = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text())
        if isinstance(loaded, dict):
            data = loaded
    roles = data.get("roles") or {}
    return Config(
        standard_version=data.get("standard_version", 0),
        architect_reviewer_agent=(roles.get("architect_reviewer") or {}).get("agent"),
        developer_agent=(roles.get("developer") or {}).get("agent"),
        github_project=bool((data.get("github") or {}).get("project", True)),
        independent_review_required=bool(
            (data.get("workflow") or {}).get("independent_review_required", True)
        ),
        roles=roles,
        providers=data.get("providers") or {},
        tools=data.get("tools") or {},
        notifications=data.get("notifications") or {},
        raw=data,
    )


def set_standard_version(root: Path, version: int) -> None:
    """Update standard_version in .aip/config.yml, preserving comments and layout."""
    path = root / CONFIG_PATH
    text = path.read_text() if path.is_file() else ""
    line = f"standard_version: {version}"
    if re.search(r"(?m)^standard_version:.*$", text):
        text = re.sub(r"(?m)^standard_version:.*$", line, text)
    else:
        text = line + "\n" + text
    path.write_text(text)


def validate_config(config: Config) -> list[str]:
    """Return actionable configuration defects without resolving any secret."""
    defects = [f"missing role: {role}" for role in REQUIRED_ROLES if role not in config.roles]
    for name, provider in config.providers.items():
        if not isinstance(provider, dict):
            defects.append(f"provider {name} must be a mapping")
            continue
        secret_ref = provider.get("secret_ref")
        if secret_ref and not str(secret_ref).startswith(("env:", "keychain:", "vault:")):
            defects.append(f"provider {name} secret_ref must use env:, keychain:, or vault:")
        forbidden = {"api_key", "token", "secret", "password"}.intersection(provider)
        if forbidden:
            defects.append(f"provider {name} contains inline secret field(s): {', '.join(sorted(forbidden))}")
    return defects
