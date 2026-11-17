import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from email_organizer.auth import get_gmail_service, CREDENTIALS_PATH, TOKEN_PATH
from email_organizer.gmail_client import GmailClient
from email_organizer.organizer import EmailOrganizer
from email_organizer.rules import RulesConfig
from email_organizer.daily_summary import (
    render_console_summary,
    save_daily_digest,
)
from email_organizer.unsubscriber import JunkUnsubscriber

app = typer.Typer(
    name="email-organizer",
    help="Intelligent Gmail Organizer & Daily Digest CLI",
    add_completion=False,
)
console = Console(legacy_windows=False)



@app.command()
def auth():
    """Verify or complete Google Gmail OAuth authentication."""
    console.print(Panel.fit("[bold blue]Gmail Authentication Check[/bold blue]"))

    if not CREDENTIALS_PATH.exists():
        console.print(
            "[bold red][ERROR] 'credentials.json' not found in project directory![/bold red]\n\n"
            "[yellow]How to get your credentials:[/yellow]\n"
            "1. Visit the [link=https://console.cloud.google.com/]Google Cloud Console[/link]\n"
            "2. Create a project and enable the [bold]Gmail API[/bold]\n"
            "3. Go to [bold]APIs & Services > Credentials > Create Credentials > OAuth client ID[/bold]\n"
            "4. Choose [bold]Desktop app[/bold] as Application Type and name it 'Email Organizer'\n"
            "5. Under [bold]OAuth consent screen[/bold], add your Gmail address as a [bold]Test user[/bold]\n"
            f"6. Download the client secret JSON file, rename it to [bold green]credentials.json[/bold green], and place it at:\n"
            f"   [cyan]{CREDENTIALS_PATH}[/cyan]"
        )
        raise typer.Exit(code=1)

    try:
        console.print("[cyan]Connecting to Gmail API... (A browser window may open for initial sign-in)[/cyan]")
        service = get_gmail_service()
        client = GmailClient(service)
        labels = client.get_labels_map()
        console.print(f"[bold green][OK] Successfully connected![/bold green] Found {len(labels)} existing Gmail labels.")
        console.print(f"[dim]Cached token stored at: {TOKEN_PATH}[/dim]")
    except Exception as e:
        console.print(f"[bold red]Authentication failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def triage(
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview matches without altering emails vs applying changes"),
    limit: int = typer.Option(30, "--limit", "-n", help="Maximum emails to scan"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Custom Gmail search query filter (default: is:inbox)"),
):
    """Scan and categorize emails based on config/rules.yaml."""
    console.print(Panel.fit(f"[bold cyan]Running Email Triage[/bold cyan] (dry_run={dry_run})"))
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

    client = GmailClient(service)
    config = RulesConfig.load()
    organizer = EmailOrganizer(client=client, config=config)

    with console.status("[bold green]Scanning and classifying emails...[/bold green]"):
        result = organizer.triage_inbox(query=query, limit=limit, dry_run=dry_run)

    render_console_summary(result, console)

    if dry_run:
        console.print("\n[yellow][NOTE] This was a dry run. To apply changes in Gmail, run with `--apply`[/yellow]")
    else:
        console.print("\n[bold green][OK] Changes applied successfully in Gmail![/bold green]")


@app.command()
def daily(
    dry_run: bool = typer.Option(False, "--dry-run/--apply", help="Preview vs apply organization actions"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum emails to process for daily digest"),
):
    """Run daily email organization and generate the Daily Briefing Digest."""
    console.print(Panel.fit("[bold green]Daily Email Organization & Digest[/bold green]"))

    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

    client = GmailClient(service)
    config = RulesConfig.load()
    organizer = EmailOrganizer(client=client, config=config)

    with console.status("[bold green]Running daily organization pass...[/bold green]"):
        result = organizer.triage_inbox(limit=limit, dry_run=dry_run)

    # Save Markdown digest
    out_dir = Path(__file__).resolve().parent.parent.parent / config.settings.summary_dir
    digest_file = save_daily_digest(result, out_dir)

    render_console_summary(result, console)
    console.print(f"\n[bold green][OK] Daily digest saved to:[/bold green] [cyan]{digest_file}[/cyan]")


@app.command()
def unsubscribe(
    apply_unsub: bool = typer.Option(True, "--apply/--dry-run", help="Auto-unsubscribe via RFC 8058 / Web vs preview only"),
    trash: bool = typer.Option(True, "--trash/--keep", help="Move junk subscription emails to Trash vs keep in mailbox"),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum emails to scan in inbox"),
    query: Optional[str] = typer.Option("is:inbox", "--query", "-q", help="Gmail search query filter"),
):
    """Scan inbox for marketing/junk subscriptions, auto-unsubscribe, and purge emails."""
    mode_str = "[bold green]APPLY (Unsubscribe & Trash)[/bold green]" if (apply_unsub and trash) else (
        "[yellow]DRY RUN (Preview Only)[/yellow]" if not apply_unsub else "[cyan]APPLY (Unsubscribe Only)[/cyan]"
    )
    console.print(Panel.fit(f"[bold red]Junk Subscription Cleaner & Auto-Unsubscriber[/bold red]\nMode: {mode_str}"))

    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

    client = GmailClient(service)
    config = RulesConfig.load()
    unsubber = JunkUnsubscriber(client=client, config=config)

    with console.status("[bold cyan]Scanning inbox for junk subscriptions & mailing lists...[/bold cyan]"):
        targets = unsubber.scan_junk_subscriptions(query=query, max_results=limit)

    if not targets:
        console.print("[bold green][✓] No junk or promotional subscriptions found in inbox![/bold green]")
        return

    total_emails = sum(len(t.message_ids) for t in targets)
    console.print(f"Found [bold yellow]{len(targets)}[/bold yellow] unique subscriptions across [bold yellow]{total_emails}[/bold yellow] emails.\n")

    if apply_unsub:
        with console.status("[bold green]Executing automated unsubscriptions and cleaning emails...[/bold green]"):
            targets = unsubber.process_and_clean(targets, apply_unsub=True, trash_emails=trash)

    # Render summary table
    table = Table(title="Junk Subscriptions & Actions", show_header=True)
    table.add_column("Sender / Brand", style="cyan", no_wrap=False, max_width=35)
    table.add_column("Emails", justify="center", style="magenta", width=8)
    table.add_column("Unsub Type", justify="center", style="yellow", width=14)
    table.add_column("Unsubscribe Status", style="green")
    if trash:
        table.add_column("Trashed", justify="center", style="red", width=8)

    unsub_success_count = 0
    total_trashed_count = 0

    for t in targets:
        unsub_type = "RFC 8058 1-Click" if t.one_click else ("Web Link" if t.http_url else ("Mailto" if t.mailto_url else "None"))
        status_display = t.status_detail if apply_unsub else "[dim]Preview (Dry Run)[/dim]"
        if t.unsubscribed:
            unsub_success_count += 1
            status_display = f"[bold green][✓] {t.status_detail}[/bold green]"
        elif not apply_unsub:
            status_display = f"[dim]{unsub_type} available[/dim]"
        else:
            status_display = f"[yellow]{t.status_detail}[/yellow]"

        row = [t.sender[:35], str(len(t.message_ids)), unsub_type, status_display]
        if trash:
            total_trashed_count += t.trashed_count
            trashed_display = f"[bold red]{t.trashed_count}[/bold red]" if apply_unsub else f"[dim]{len(t.message_ids)}[/dim]"
            row.append(trashed_display)

        table.add_row(*row)

    console.print(table)

    if apply_unsub:
        console.print(Panel.fit(
            f"[bold green]Cleaning Complete![/bold green]\n"
            f"- Subscriptions auto-unsubscribed: [bold cyan]{unsub_success_count} / {len(targets)}[/bold cyan]\n"
            f"- Junk emails moved to Trash: [bold red]{total_trashed_count}[/bold red]"
        ))
    else:
        console.print("\n[yellow][NOTE] This was a dry run. To execute unsubscriptions and purge emails, run with `--apply`[/yellow]")


@app.command()
def rules():
    """Display the active organization categories, rules, and priorities."""
    config = RulesConfig.load()
    table = Table(title="Active Email Classification Rules", show_header=True)
    table.add_column("Priority", style="dim", justify="center")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Actions", style="green")

    for cat in config.categories:
        actions_str = f"Labels: {cat.actions.add_labels}"
        if cat.actions.archive:
            actions_str += " | Archive: Yes"
        if cat.actions.mark_read:
            actions_str += " | Read: Yes"

        table.add_row(str(cat.priority), cat.name, cat.description, actions_str)

    console.print(table)


@app.command("serve-mcp")
def serve_mcp():
    """Start the Model Context Protocol (MCP) server over stdio."""
    from email_organizer.mcp_server import run_server
    run_server()


def main():
    app()


if __name__ == "__main__":
    main()
