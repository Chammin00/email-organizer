import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import requests

from email_organizer.gmail_client import GmailClient
from email_organizer.rules import RulesConfig


@dataclass
class UnsubscribeTarget:
    sender: str
    clean_sender: str
    sample_subject: str
    message_ids: List[str] = field(default_factory=list)
    http_url: Optional[str] = None
    mailto_url: Optional[str] = None
    one_click: bool = False
    unsubscribed: bool = False
    status_detail: str = ""
    trashed_count: int = 0


# Domains and keywords that must NEVER be unsubscribed or bulk-trashed
PROTECTED_SENDERS = [
    "allenisd.org",
    "peachjar.com",
    "easyiep.com",
    "rmoreland.009@gmail.com",
    "chase.com",
    "wellsfargo.com",
    "capitalone.com",
    "usbank.com",
    "citi.com",
    "synchronybank.com",
    "fidelity.com",
    "vanguard.com",
    "paypal.com",
    "stripe.com",
    "accounts.google.com",
    "tinglabs.com",
]

PROTECTED_SUBJECT_KEYWORDS = [
    "chance",
    "chandler",
    "reign",
    "hamilton",
    "mortgage",
    "payment received",
    "payment confirmation",
    "direct deposit",
    "security alert",
    "verification code",
    "2-step verification",
    "statement is ready",
    "statement available",
]


def extract_clean_email(sender_str: str) -> str:
    """Extract clean email address from sender string."""
    match = re.search(r"<([^>]+)>", sender_str)
    if match:
        return match.group(1).lower().strip()
    return sender_str.lower().strip()


def parse_list_unsubscribe(header_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse List-Unsubscribe header according to RFC 2369.
    Returns (http_url, mailto_url).
    """
    if not header_str:
        return None, None

    # Matches anything enclosed in < >
    items = re.findall(r"<([^>]+)>", header_str)
    http_url = None
    mailto_url = None

    for item in items:
        item = item.strip()
        if item.lower().startswith("https://") or item.lower().startswith("http://"):
            if not http_url:
                http_url = item
        elif item.lower().startswith("mailto:"):
            if not mailto_url:
                mailto_url = item

    return http_url, mailto_url


def is_protected_message(meta: Dict[str, Any], config: Optional[RulesConfig] = None) -> bool:
    """Check if an email must be strictly protected from unsubscribing/trashing."""
    sender = meta.get("from", "").lower()
    subject = meta.get("subject", "").lower()
    snippet = meta.get("snippet", "").lower()

    for p in PROTECTED_SENDERS:
        if p in sender:
            return True

    for k in PROTECTED_SUBJECT_KEYWORDS:
        if k in subject or k in snippet:
            return True

    if config:
        for rule in config.categories:
            if rule.name in ["Family-Hamilton", "Finance", "Action-Needed", "Notifications"]:
                if rule.matches(meta):
                    return True

    return False


class JunkUnsubscriber:
    """Detects junk subscriptions, executes automated unsubscriptions, and removes junk messages."""

    def __init__(self, client: GmailClient, config: Optional[RulesConfig] = None):
        self.client = client
        self.config = config or RulesConfig.load()

    def scan_junk_subscriptions(
        self,
        query: str = "is:inbox",
        max_results: int = 100,
    ) -> List[UnsubscribeTarget]:
        """
        Scan messages matching query and identify marketing/junk subscriptions.
        Groups them by unique sender.
        """
        msg_ids = self.client.search_messages(query=query, max_results=max_results)
        grouped: Dict[str, UnsubscribeTarget] = {}

        for mid in msg_ids:
            meta = self.client.get_message_summary(mid)

            if is_protected_message(meta, self.config):
                continue

            raw_unsub = meta.get("list_unsubscribe", "")
            raw_post = meta.get("list_unsubscribe_post", "")
            http_url, mailto_url = parse_list_unsubscribe(raw_unsub)

            # Check if this qualifies as a junk subscription / newsletter / promotion
            is_newsletter_or_promo = False
            for rule in self.config.categories:
                if rule.name in ["Newsletters", "Promotions", "Scam-Phishing"] and rule.matches(meta):
                    is_newsletter_or_promo = True
                    break

            # If it has an unsubscribe header or matches newsletter/promo rules
            if http_url or mailto_url or is_newsletter_or_promo:
                sender_raw = meta.get("from", "Unknown")
                clean_sender = extract_clean_email(sender_raw)

                one_click = "one-click" in raw_post.lower()

                if clean_sender not in grouped:
                    grouped[clean_sender] = UnsubscribeTarget(
                        sender=sender_raw,
                        clean_sender=clean_sender,
                        sample_subject=meta.get("subject", "(No Subject)"),
                        message_ids=[mid],
                        http_url=http_url,
                        mailto_url=mailto_url,
                        one_click=one_click,
                    )
                else:
                    target = grouped[clean_sender]
                    target.message_ids.append(mid)
                    if not target.http_url and http_url:
                        target.http_url = http_url
                    if not target.mailto_url and mailto_url:
                        target.mailto_url = mailto_url
                    if not target.one_click and one_click:
                        target.one_click = one_click

        return list(grouped.values())

    def execute_unsubscribe(self, target: UnsubscribeTarget) -> bool:
        """
        Attempt automated unsubscription via RFC 8058 One-Click POST or HTTPS GET.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        # 1. Try RFC 8058 One-Click POST if supported
        if target.http_url and target.one_click:
            try:
                post_headers = {
                    **headers,
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                resp = requests.post(
                    target.http_url,
                    data={"List-Unsubscribe": "One-Click"},
                    headers=post_headers,
                    timeout=10,
                    allow_redirects=True,
                )
                if resp.status_code in [200, 201, 202, 204, 301, 302, 303, 307, 308]:
                    target.unsubscribed = True
                    target.status_detail = f"Auto-unsubscribed (RFC 8058 One-Click, HTTP {resp.status_code})"
                    return True
                else:
                    target.status_detail = f"POST failed (HTTP {resp.status_code}), attempting GET..."
            except Exception as e:
                target.status_detail = f"POST error ({e}), attempting GET..."

        # 2. Try HTTP GET on the HTTPS unsubscribe link
        if target.http_url and target.http_url.startswith("https://"):
            try:
                resp = requests.get(
                    target.http_url,
                    headers=headers,
                    timeout=10,
                    allow_redirects=True,
                )
                if resp.status_code in [200, 202, 204, 301, 302, 303, 307, 308]:
                    target.unsubscribed = True
                    target.status_detail = f"Unsubscribed via Web GET (HTTP {resp.status_code})"
                    return True
                else:
                    target.status_detail = f"Web GET responded with HTTP {resp.status_code}"
            except Exception as e:
                target.status_detail = f"Web GET failed: {e}"

        # 3. Fallback
        if target.http_url:
            target.status_detail = "Web link available (may require manual confirmation)"
        elif target.mailto_url:
            target.status_detail = f"Mailto address: {target.mailto_url}"
        else:
            target.status_detail = "No direct header link detected"

        return False

    def process_and_clean(
        self,
        targets: List[UnsubscribeTarget],
        apply_unsub: bool = True,
        trash_emails: bool = True,
    ) -> List[UnsubscribeTarget]:
        """
        Executes unsubscriptions and trashes matching messages.
        """
        for target in targets:
            if apply_unsub:
                self.execute_unsubscribe(target)
            else:
                target.status_detail = "Dry Run (Preview)"

            if trash_emails:
                trashed = self.client.batch_trash_messages(target.message_ids)
                target.trashed_count = trashed
            else:
                target.trashed_count = 0

        return targets
