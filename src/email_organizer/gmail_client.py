from typing import Any, Dict, List, Optional
from googleapiclient.discovery import Resource


class GmailClient:
    """Wrapper around Google Gmail API for searching, fetching, and labeling messages."""

    def __init__(self, service: Resource):
        self.service = service
        self._labels_cache: Optional[Dict[str, str]] = None  # name -> id

    def get_labels_map(self, force_refresh: bool = False) -> Dict[str, str]:
        """Fetch all user and system labels mapped name -> label_id."""
        if self._labels_cache is None or force_refresh:
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            self._labels_cache = {l["name"]: l["id"] for l in labels}
        return self._labels_cache

    def get_or_create_label(self, label_name: str) -> str:
        """Get the ID of an existing label or create it if missing."""
        labels = self.get_labels_map()
        if label_name in labels:
            return labels[label_name]

        body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created = (
            self.service.users()
            .labels()
            .create(userId="me", body=body)
            .execute()
        )
        self.get_labels_map(force_refresh=True)
        return created["id"]

    def search_messages(self, query: str = "is:inbox", max_results: int = 50) -> List[str]:
        """Search message IDs matching a standard Gmail query string."""
        message_ids = []
        request = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=min(max_results, 100))
        )
        while request and len(message_ids) < max_results:
            response = request.execute()
            messages = response.get("messages", [])
            message_ids.extend([m["id"] for m in messages])
            if len(message_ids) >= max_results:
                break
            request = self.service.users().messages().list_next(request, response)

        return message_ids[:max_results]

    def get_message_summary(self, message_id: str) -> Dict[str, Any]:
        """
        Fetch lightweight parsed headers and metadata for a message.
        """
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata", metadataHeaders=["From", "To", "Subject", "Date", "List-Unsubscribe", "List-Unsubscribe-Post"])
            .execute()
        )

        headers = {
            h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }

        return {
            "id": msg["id"],
            "thread_id": msg.get("threadId"),
            "snippet": msg.get("snippet", ""),
            "subject": headers.get("subject", "(No Subject)"),
            "from": headers.get("from", "(Unknown Sender)"),
            "to": headers.get("to", ""),
            "date": headers.get("date", ""),
            "list_unsubscribe": headers.get("list-unsubscribe", ""),
            "list_unsubscribe_post": headers.get("list-unsubscribe-post", ""),
            "label_ids": msg.get("labelIds", []),
        }

    def modify_message(
        self,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Add or remove label IDs on a specific message."""
        body = {
            "addLabelIds": add_label_ids or [],
            "removeLabelIds": remove_label_ids or [],
        }
        return (
            self.service.users()
            .messages()
            .modify(userId="me", id=message_id, body=body)
            .execute()
        )

    def archive_message(self, message_id: str) -> Dict[str, Any]:
        """Remove INBOX label from message (archive)."""
        return self.modify_message(message_id, remove_label_ids=["INBOX"])

    def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Remove UNREAD label from message."""
        return self.modify_message(message_id, remove_label_ids=["UNREAD"])

    def trash_message(self, message_id: str) -> Dict[str, Any]:
        """Move message to Gmail TRASH (Bin)."""
        return self.service.users().messages().trash(userId="me", id=message_id).execute()

    def batch_trash_messages(self, message_ids: List[str]) -> int:
        """Move multiple messages to Trash."""
        trashed_count = 0
        for mid in message_ids:
            try:
                self.trash_message(mid)
                trashed_count += 1
            except Exception:
                pass
        return trashed_count

