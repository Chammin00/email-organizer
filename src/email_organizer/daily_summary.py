from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from email_organizer.organizer import TriageResult


def format_daily_markdown(date_str: str, result: TriageResult) -> str:
    """Formats triage results into a Markdown daily digest."""
    lines = [
        f"# 📬 Daily Email Organizer Digest - {date_str}",
        "",
        "## 📊 Summary Overview",
        f"- **Total Emails Scanned:** {result.scanned_count}",
        f"- **Categorized & Organized:** {len(result.categorized)}",
        f"- **Uncategorized:** {len(result.uncategorized)}",
        "",
        "### Categories Breakdown",
    ]

    for cat, count in result.category_counts.items():
        lines.append(f"- **{cat}:** {count}")

    # Section 1: Removed Scams
    scams = [item for item in result.categorized if item.get("trash") or item["category"] == "Scam-Phishing"]
    if scams:
        lines.append("")
        lines.append("## 🛑 Removed Scam & Phishing Emails (Moved to Trash)")
        for s in scams:
            lines.append(f"- **{s['subject']}** (From: `{s['from']}`)")

    # Section 2: Important Family & School Updates (Chance, Chandler, Reign, Hamilton)
    family = [item for item in result.categorized if item["category"] == "Family-Hamilton"]
    if family:
        lines.append("")
        lines.append("## 👨‍👩‍👦 Important Family & School Updates (Chance, Chandler, Reign, Hamilton)")
        for fam in family:
            lines.append(f"- **{fam['subject']}**")
            lines.append(f"  - *From:* `{fam['from']}` | *Date:* {fam['date']}")

    # Section 3: Action-Needed / Urgent
    urgent = [item for item in result.categorized if item["category"] == "Action-Needed" and not item.get("trash")]
    lines.append("")
    lines.append("## 🚨 Action Needed & High Priority")
    if urgent:
        for u in urgent:
            lines.append(f"- **{u['subject']}**")
            lines.append(f"  - *From:* `{u['from']}` | *Date:* {u['date']}")
    else:
        lines.append("*No urgent action items detected in today's batch.*")



    # Section 2: Financial & Invoices
    finance = [item for item in result.categorized if item["category"] == "Finance"]
    lines.append("")
    lines.append("## 💳 Finance & Receipts")
    if finance:
        for f in finance:
            lines.append(f"- **{f['subject']}** (From: `{f['from']}`)")
    else:
        lines.append("*No finance or receipt emails.*")

    # Section 3: Newsletters & Subscriptions
    newsletters = [item for item in result.categorized if item["category"] == "Newsletters"]
    lines.append("")
    lines.append("## 📰 Newsletters & Subscriptions")
    if newsletters:
        for n in newsletters:
            archived_status = "*(Archived)*" if n.get("archive") else ""
            lines.append(f"- **{n['subject']}** {archived_status}")
    else:
        lines.append("*No newsletters detected.*")

    # Section 4: Other Categorized & Notifications
    other = [
        item for item in result.categorized
        if item["category"] not in ["Action-Needed", "Finance", "Newsletters"]
    ]
    if other:
        lines.append("")
        lines.append("## 🔔 Notifications & Other Updates")
        for o in other:
            lines.append(f"- [{o['category']}] **{o['subject']}** (From: `{o['from']}`)")

    # Section 5: Uncategorized Emails
    if result.uncategorized:
        lines.append("")
        lines.append("## ❓ Uncategorized (Still in Inbox)")
        for un in result.uncategorized[:10]:
            lines.append(f"- **{un['subject']}** (From: `{un['from']}`)")
        if len(result.uncategorized) > 10:
            lines.append(f"- *...and {len(result.uncategorized) - 10} more*")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated automatically at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    return "\n".join(lines)


def save_daily_digest(
    result: TriageResult,
    output_dir: Path,
    date_str: Optional[str] = None,
) -> Path:
    """Save daily digest to a markdown file."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    output_dir.mkdir(parents=True, exist_ok=True)
    digest_path = output_dir / f"{date_str}-digest.md"

    content = format_daily_markdown(date_str, result)
    digest_path.write_text(content, encoding="utf-8")
    return digest_path


def render_console_summary(result: TriageResult, console: Console):
    """Renders a rich table and summary panel to the terminal."""
    table = Table(title="📬 Email Organizer - Triage Summary", show_header=True)
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Count", style="green", justify="right")
    table.add_column("Details", style="dim")

    for cat, count in result.category_counts.items():
        sample = ", ".join(
            [item["subject"][:35] for item in result.categorized if item["category"] == cat][:2]
        )
        table.add_row(cat, str(count), sample or "-")

    if result.uncategorized:
        table.add_row("Uncategorized", str(len(result.uncategorized)), "Needs review or new rules", style="yellow")

    console.print(table)

    scams = [item for item in result.categorized if item.get("trash") or item["category"] == "Scam-Phishing"]
    if scams:
        scams_text = "\n".join([f"[dim]• Trashed:[/] [bold]{s['subject']}[/] from {s['from']}" for s in scams])
        console.print(Panel(scams_text, title="Scam / Phishing Emails Moved to Trash", border_style="red"))

    family = [item for item in result.categorized if item["category"] == "Family-Hamilton"]
    if family:
        fam_text = "\n".join([f"• [bold magenta]{f['subject']}[/] from {f['from']}" for f in family])
        console.print(Panel(fam_text, title="Family & School Updates (Chance, Chandler, Reign, Hamilton)", border_style="magenta"))

    urgent = [item for item in result.categorized if item["category"] == "Action-Needed" and not item.get("trash")]
    if urgent:
        urgent_text = "\n".join([f"• [bold red]{u['subject']}[/] from {u['from']}" for u in urgent])
        console.print(Panel(urgent_text, title="Action Required Immediately", border_style="yellow"))


