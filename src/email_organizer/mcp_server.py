from pathlib import Path
from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer

from email_organizer.auth import get_gmail_service, CREDENTIALS_PATH, TOKEN_PATH
from email_organizer.gmail_client import GmailClient
from email_organizer.organizer import EmailOrganizer
from email_organizer.rules import RulesConfig
from email_organizer.daily_summary import format_daily_markdown, save_daily_digest
from datetime import datetime

# Initialize MCP server
mcp = MCPServer(
    name="email-organizer",
    description="Gmail Email Organizer MCP Server for automated triage, daily digests, and rule-based email management.",
    version="0.1.0",
)


def _get_client() -> GmailClient:
    service = get_gmail_service()
    return GmailClient(service)


@mcp.tool()
def gmail_status() -> Dict[str, Any]:
    """Check Gmail API connection status, credentials, and token presence."""
    creds_exist = CREDENTIALS_PATH.exists()
    token_exist = TOKEN_PATH.exists()

    status = {
        "credentials_json_found": creds_exist,
        "token_json_found": token_exist,
        "connected": False,
        "message": "",
    }

    if not creds_exist and not token_exist:
        status["message"] = (
            "credentials.json is missing. Please download OAuth client credentials from "
            "Google Cloud Console (Desktop app) and save to the project root."
        )
        return status

    try:
        client = _get_client()
        labels = client.get_labels_map()
        status["connected"] = True
        status["total_labels"] = len(labels)
        status["message"] = "Successfully authenticated and connected to Gmail API."
    except Exception as e:
        status["message"] = f"Authentication error: {str(e)}"

    return status


@mcp.tool()
def gmail_list_unread(limit: int = 15) -> List[Dict[str, Any]]:
    """List recent unread emails in the user's Inbox with subject, sender, and snippet."""
    client = _get_client()
    msg_ids = client.search_messages("is:inbox is:unread", max_results=limit)
    summaries = []
    for mid in msg_ids:
        meta = client.get_message_summary(mid)
        summaries.append({
            "id": meta["id"],
            "subject": meta["subject"],
            "from": meta["from"],
            "date": meta["date"],
            "snippet": meta["snippet"],
        })
    return summaries


@mcp.tool()
def gmail_search(query: str = "is:inbox", limit: int = 15) -> List[Dict[str, Any]]:
    """Search Gmail messages using standard Gmail query syntax (e.g. 'from:github', 'has:attachment')."""
    client = _get_client()
    msg_ids = client.search_messages(query, max_results=limit)
    summaries = []
    for mid in msg_ids:
        meta = client.get_message_summary(mid)
        summaries.append({
            "id": meta["id"],
            "subject": meta["subject"],
            "from": meta["from"],
            "date": meta["date"],
            "snippet": meta["snippet"],
        })
    return summaries


@mcp.tool()
def gmail_run_triage(
    dry_run: bool = True,
    limit: int = 50,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run email triage rules against Inbox messages.
    If dry_run is True, previews categorized emails and actions without changing labels or archiving.
    """
    client = _get_client()
    config = RulesConfig.load()
    organizer = EmailOrganizer(client=client, config=config)
    result = organizer.triage_inbox(query=query, limit=limit, dry_run=dry_run)

    return {
        "dry_run": dry_run,
        "scanned_count": result.scanned_count,
        "category_counts": result.category_counts,
        "categorized": result.categorized,
        "uncategorized_count": len(result.uncategorized),
    }


@mcp.tool()
def gmail_daily_digest(save_to_file: bool = True) -> str:
    """
    Execute daily organization pass and generate a comprehensive markdown briefing of today's emails.
    """
    client = _get_client()
    config = RulesConfig.load()
    organizer = EmailOrganizer(client=client, config=config)
    result = organizer.triage_inbox(dry_run=False)

    date_str = datetime.now().strftime("%Y-%m-%d")
    md_content = format_daily_markdown(date_str, result)

    if save_to_file:
        out_dir = Path(__file__).resolve().parent.parent.parent / config.settings.summary_dir
        save_daily_digest(result, out_dir, date_str)

    return md_content


@mcp.tool()
def gmail_apply_label(
    message_id: str,
    label_name: str,
    archive: bool = False,
) -> Dict[str, Any]:
    """Manually apply a label to a specific email, and optionally archive it from the Inbox."""
    client = _get_client()
    label_id = client.get_or_create_label(label_name)
    remove_ids = ["INBOX"] if archive else []
    client.modify_message(message_id, add_label_ids=[label_id], remove_label_ids=remove_ids)
    return {
        "success": True,
        "message_id": message_id,
        "label": label_name,
        "archived": archive,
    }


def run_server():
    """Start MCP stdio server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
