from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class RuleConditions(BaseModel):
    subject_contains: List[str] = Field(default_factory=list)
    from_contains: List[str] = Field(default_factory=list)
    snippet_contains: List[str] = Field(default_factory=list)
    exclude_subject_contains: List[str] = Field(default_factory=list)
    exclude_from_contains: List[str] = Field(default_factory=list)
    has_header: List[str] = Field(default_factory=list)


class RuleActions(BaseModel):
    add_labels: List[str] = Field(default_factory=list)
    archive: bool = False
    mark_read: bool = False
    trash: bool = False



class CategoryRule(BaseModel):
    name: str
    description: str = ""
    priority: int = 100
    rules: RuleConditions
    actions: RuleActions

    def matches(self, email_meta: Dict[str, Any]) -> bool:
        subject = email_meta.get("subject", "").lower()
        sender = email_meta.get("from", "").lower()
        snippet = email_meta.get("snippet", "").lower()
        has_unsub = bool(email_meta.get("list_unsubscribe"))

        # Check exclusions first
        for exc in self.rules.exclude_subject_contains:
            if exc.lower() in subject:
                return False

        for exc in self.rules.exclude_from_contains:
            if exc.lower() in sender:
                return False

        # Check subject substring matches
        for kw in self.rules.subject_contains:
            if kw.lower() in subject:
                return True

        # Check sender substring matches
        for kw in self.rules.from_contains:
            if kw.lower() in sender:
                return True

        # Check snippet substring matches
        for kw in self.rules.snippet_contains:
            if kw.lower() in snippet:
                return True

        # Check header conditions (e.g. List-Unsubscribe)
        for h in self.rules.has_header:
            if h.lower() == "list-unsubscribe" and has_unsub:
                return True

        return False


class SettingsConfig(BaseModel):
    label_prefix: str = "Organizer"
    default_search_query: str = "is:inbox"
    max_fetch_limit: int = 50
    summary_dir: str = "daily_summaries"


class RulesConfig(BaseModel):
    version: str = "1.0"
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    categories: List[CategoryRule] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "RulesConfig":
        if path is None:
            path = Path(__file__).resolve().parent.parent.parent / "config" / "rules.yaml"

        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Sort categories by priority ascending
        config = cls(**data)
        config.categories.sort(key=lambda c: c.priority)
        return config
