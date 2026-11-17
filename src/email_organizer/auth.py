from pathlib import Path
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

# Scope required to read, label, modify, and archive messages
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"


def get_gmail_service(
    credentials_path: Path = CREDENTIALS_PATH,
    token_path: Path = TOKEN_PATH,
) -> Resource:
    """
    Authenticate with Gmail API using OAuth 2.0.
    Reuses cached token.json if valid; prompts browser login if expired or absent.
    """
    creds: Optional[Credentials] = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # If refresh fails, re-authenticate from scratch
                creds = None

        if not creds:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Credentials file not found at '{credentials_path}'.\n"
                    "To enable Gmail access:\n"
                    "  1. Go to Google Cloud Console (https://console.cloud.google.com/)\n"
                    "  2. Create a project and enable the 'Gmail API'\n"
                    "  3. Go to 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'\n"
                    "  4. Select Application type: 'Desktop app'\n"
                    "  5. Download the JSON file and save it as 'credentials.json' in this folder."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            # Opens default browser for one-time consent
            creds = flow.run_local_server(port=0)

        # Cache refreshed or new token
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
