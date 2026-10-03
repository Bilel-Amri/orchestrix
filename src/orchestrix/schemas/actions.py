"""Schemas de paramètres par action Jira (Lot B — ActionGuard, règle 1).

`ActionProposal.params` est un `dict` non typé : il accepte n'importe quoi.
Chaque action Jira a une forme différente et obligatoire, donc on lui donne
un modèle Pydantic dédié. Ces modèles sont la "grammaire" que `_check_schema`
utilisera pour valider les params avant toute logique métier.

Choix de conception :
  - `extra="forbid"` : un champ inconnu fait échouer la validation (fail-closed).
    Le LLM ne peut pas glisser des params que l'exécuteur ne comprendrait pas.
  - `str_strip_whitespace=True` : "   " devient "" et échoue aux `min_length`,
    on ne laisse pas passer des valeurs vides déguisées.
  - Les invariantes STRUCTURELLES (ex: end_date > start_date) vivent ici.
    Les invariantes qui dépendent de l'ÉTAT Jira (ex: issue déjà Closed) sont
    du ressort de la règle 5 (state consistency), PAS du schéma.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Même format que `JiraMockExecutor._KEY_RE` : PROJ-123
JIRA_KEY_PATTERN = r"^[A-Z][A-Z0-9]*-\d+$"
IssueKey = Annotated[str, StringConstraints(pattern=JIRA_KEY_PATTERN)]


class _ActionParams(BaseModel):
    """Base commune : rejette les champs inconnus et normalise les espaces."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateEpicParams(_ActionParams):
    """Params de `create_epic`."""

    summary: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    labels: list[str] = Field(default_factory=list)


class CreateIssueParams(_ActionParams):
    """Params de `create_issue`."""

    summary: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    issue_type: str = Field("Task", min_length=1, description="Bug, Task, Story…")
    epic_key: IssueKey | None = None
    labels: list[str] = Field(default_factory=list)
    story_points: float | None = Field(None, ge=0)


class CreateSprintParams(_ActionParams):
    """Params de `create_sprint`. Invariante structurelle : end_date > start_date."""

    board_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: date
    goal: str | None = None

    @model_validator(mode="after")
    def check_dates_ordered(self) -> CreateSprintParams:
        if self.end_date <= self.start_date:
            raise ValueError("end_date doit être strictement postérieure à start_date")
        return self


class AssignIssueParams(_ActionParams):
    """Params de `assign_issue`."""

    issue_key: IssueKey
    assignee: str = Field(..., min_length=1, description="Identifiant applicatif de l'assigné")
    estimated_hours: float | None = Field(None, ge=0)


class TransitionIssueParams(_ActionParams):
    """Params de `transition_issue`.

    Le schéma vérifie seulement la forme. La validité de la transition au regard
    de l'état courant de l'issue relève de la règle 5 (state consistency).
    """

    issue_key: IssueKey
    transition: str = Field(..., min_length=1, description="Nom de l'état cible")


class AddCommentParams(_ActionParams):
    """Params de `add_comment`."""

    issue_key: IssueKey
    body: str = Field(..., min_length=1)


class UpdateFieldParams(_ActionParams):
    """Params de `update_field`."""

    issue_key: IssueKey
    field: str = Field(..., min_length=1, description="Nom du champ Jira à modifier")
    value: Any
