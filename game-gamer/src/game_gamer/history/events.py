"""Shared canonical mutation record, preserving mutation schema 0.1."""
from dataclasses import dataclass, field
from typing import Any

@dataclass(kw_only=True)
class Mutation:
    id: str
    action_id: str | None
    kind: str
    entity_type: str
    entity_id: str
    before: Any
    after: Any
    occurred_at: str
    caused_by: str
    metadata: dict = field(default_factory=dict)
    schema_version: str = '0.1'
