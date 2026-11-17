"""Email Organizer Package."""

def main():
    from email_organizer.cli import main as _main
    _main()

__all__ = ["main"]
