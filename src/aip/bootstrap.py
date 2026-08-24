"""Guided, project-agnostic foundation interview and durable brief rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BRIEF_PATH = ".context/product/PROJECT_BRIEF.md"


@dataclass(frozen=True)
class ProjectAnswers:
    name: str
    objective: str
    users: str
    scope: str
    out_of_scope: str
    stack: str
    deployment: str
    data_classification: str
    quality_gates: str
    human_approvals: str


def render_project_brief(answers: ProjectAnswers) -> str:
    return f"""# Project Brief — {answers.name}

Status: **INITIALIZED — review and ratify before implementation**

## 1. Objective
{answers.objective}

## 2. Users and stakeholders
{answers.users}

## 3. Initial scope
{answers.scope}

## 4. Explicitly out of scope
{answers.out_of_scope}

## 5. Technology and existing assets
{answers.stack}

## 6. Deployment target
{answers.deployment}

## 7. Data classification and confidentiality
{answers.data_classification}

## 8. Quality and acceptance gates
{answers.quality_gates}

## 9. Human authority and approvals
{answers.human_approvals}

## 10. First delivery instruction
The Product Owner converts this brief into `CORE.md`, `REQUIREMENTS.md`, and `ACCEPTANCE.md`.
The Architect then records boundaries in `ARCHITECTURE.md` and a bounded first slice in `PLAN.md`.
No implementation begins until contradictions and required human decisions are visible.
"""


def write_project_brief(root: Path, answers: ProjectAnswers) -> Path:
    path = root / BRIEF_PATH
    if path.is_file() and "Status: **NOT INITIALIZED**" not in path.read_text():
        raise FileExistsError(
            f"{BRIEF_PATH} is already initialized; preserve it or edit it explicitly"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_project_brief(answers))
    return path
