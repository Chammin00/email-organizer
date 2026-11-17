from typing import Any, Dict, List, Optional
from email_organizer.gmail_client import GmailClient
from email_organizer.rules import CategoryRule, RulesConfig


class TriageResult:
    def __init__(self):
        self.scanned_count: int = 0
        self.categorized: List[Dict[str, Any]] = []
        self.uncategorized: List[Dict[str, Any]] = []
        self.actions_taken: List[Dict[str, Any]] = []

    @property
    def category_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in self.categorized:
            cat = item["category"]
            counts[cat] = counts.get(cat, 0) + 1
        return counts


class EmailOrganizer:
    """Core triage engine that executes rules on Gmail messages."""

    def __init__(self, client: GmailClient, config: Optional[RulesConfig] = None):
        self.client = client
        self.config = config or RulesConfig.load()
        self._resolved_label_ids: Dict[str, str] = {}

    def _get_full_label_name(self, base_name: str) -> str:
        prefix = self.config.settings.label_prefix.strip()
        if prefix:
            return f"{prefix}/{base_name}"
        return base_name

    def _resolve_label_id(self, base_name: str, dry_run: bool = False) -> Optional[str]:
        full_name = self._get_full_label_name(base_name)
        if full_name in self._resolved_label_ids:
            return self._resolved_label_ids[full_name]

        if dry_run:
            return f"dry_run_id_{full_name}"

        label_id = self.client.get_or_create_label(full_name)
        self._resolved_label_ids[full_name] = label_id
        return label_id

    def triage_inbox(
        self,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        dry_run: bool = False,
    ) -> TriageResult:
        """
        Runs triage logic over messages matching the query.
        """
        search_query = query or self.config.settings.default_search_query
        max_limit = limit or self.config.settings.max_fetch_limit

        msg_ids = self.client.search_messages(search_query, max_results=max_limit)
        result = TriageResult()
        result.scanned_count = len(msg_ids)

        for mid in msg_ids:
            msg_meta = self.client.get_message_summary(mid)
            matched_rule: Optional[CategoryRule] = None

            # First matching rule wins (since categories are sorted by priority)
            for rule in self.config.categories:
                if rule.matches(msg_meta):
                    matched_rule = rule
                    break

            if matched_rule:
                item = {
                    "id": mid,
                    "subject": msg_meta["subject"],
                    "from": msg_meta["from"],
                    "date": msg_meta["date"],
                    "category": matched_rule.name,
                    "archive": matched_rule.actions.archive,
                    "mark_read": matched_rule.actions.mark_read,
                    "trash": matched_rule.actions.trash,
                    "add_labels": [
                        self._get_full_label_name(lbl)
                        for lbl in matched_rule.actions.add_labels
                    ],
                }
                result.categorized.append(item)

                # Execute actions if not a dry run
                add_ids = []
                for lbl in matched_rule.actions.add_labels:
                    lid = self._resolve_label_id(lbl, dry_run=dry_run)
                    if lid and not dry_run:
                        add_ids.append(lid)

                remove_ids = []
                if matched_rule.actions.archive:
                    remove_ids.append("INBOX")
                if matched_rule.actions.mark_read:
                    remove_ids.append("UNREAD")

                if not dry_run and (add_ids or remove_ids):
                    self.client.modify_message(
                        mid,
                        add_label_ids=add_ids,
                        remove_label_ids=remove_ids,
                    )

                if matched_rule.actions.trash:
                    if not dry_run:
                        self.client.trash_message(mid)

                result.actions_taken.append({
                    "id": mid,
                    "subject": msg_meta["subject"],
                    "category": matched_rule.name,
                    "archived": matched_rule.actions.archive,
                    "trashed": matched_rule.actions.trash,
                    "dry_run": dry_run,
                })
            else:
                result.uncategorized.append({
                    "id": mid,
                    "subject": msg_meta["subject"],
                    "from": msg_meta["from"],
                    "date": msg_meta["date"],
                })

        return result
