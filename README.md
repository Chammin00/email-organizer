# 📬 Gmail Email Organizer & Daily Digest (Option 3: Hybrid)

A hybrid email management engine combining **standalone Python automation (for background & daily scheduled batch jobs)** with native **Model Context Protocol (MCP)** tool exposure for AI agents.

---

## 🌟 Key Features

1. **Automated Daily Organization**:
   - Classifies unread/inbox emails into organized categories (`Scam-Phishing`, `Action-Needed`, `Finance`, `Promotions`, `Newsletters`, `Notifications`).
   - Applies nested Gmail labels (`Organizer/Scam-Phishing`, `Organizer/Finance`, etc.).
   - Auto-archives low-priority bulk items (newsletters, marketing promos) to keep your inbox at **Inbox Zero**.
2. **Automated Scam & Phishing Defense**:
   - Detects fraudulent emails, fake renewal notices (Geek Squad, McAfee, Norton), crypto blackmail, lottery scams, and account suspension phishing.
   - Automatically marks them as read and moves them into Gmail's **Trash / Bin** (safely retained for 30 days before permanent purging).
3. **Daily Briefing Digest**:
   - Generates a daily markdown report in `daily_summaries/YYYY-MM-DD-digest.md` highlighting blocked scams, high-priority action items, financial updates, and stats.
4. **Flexible Execution**:
   - **CLI Mode**: Run on-demand or dry-run previews from the terminal.
   - **Windows Scheduled Task**: Runs quietly in the background every morning.
   - **Agent MCP Server**: Gives Antigravity native tools to search, triage, and organize your inbox conversationally.
5. **Customizable Rules**:
   - Configured in a clean, human-readable [`config/rules.yaml`](file:///g:/My%20Drive/Antigravity/Projects/email%20organizer/config/rules.yaml).


---

## 🚀 Quick Setup Guide

### Step 1: Get `credentials.json` from Google Cloud Console
To allow the script to interact with your Gmail account:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `Email Organizer`).
3. Navigate to **APIs & Services > Library**, search for **Gmail API**, and click **Enable**.
4. Go to **APIs & Services > OAuth consent screen**:
   - Select **External** (or Internal if using Google Workspace).
   - Fill in App Name (`Email Organizer`) and your email.
   - Under **Test users**, add your own Gmail address (important while in testing mode!).
   - Save and finish.
5. Go to **APIs & Services > Credentials**:
   - Click **Create Credentials** -> **OAuth client ID**.
   - Application type: **Desktop app**.
   - Name: `Email Organizer Client`.
   - Click **Create**, then click **Download JSON**.
6. Rename the downloaded file to `credentials.json` and place it in the project root:
   ```
   g:\My Drive\Antigravity\Projects\email organizer\credentials.json
   ```

---

### Step 2: One-Time Authentication
Open PowerShell in this folder and run:
```powershell
.\email-organizer auth
```
- A browser window will open asking you to sign in with your Google account.
- Click **Continue** (if prompted with "Google hasn't verified this app") and grant permissions.
- A `token.json` file will be created. The script will automatically refresh it whenever it expires.

---

### Step 3: Test Run (Dry Run Preview)
To test how your rules classify your current inbox without touching any emails:
```powershell
.\email-organizer triage
```
To apply the changes (create labels, label emails, and archive according to rules):
```powershell
.\email-organizer triage --apply
```

---

### Step 4: Enable Daily Automatic Organization

You can set up a Windows Scheduled Task to run every morning automatically:
```powershell
# Set up to run every morning at 8:00 AM (default)
.\setup_daily_task.ps1

# Or specify a custom time (e.g., 7:30 AM):
.\setup_daily_task.ps1 -Time "07:30"

# Test trigger immediately:
.\setup_daily_task.ps1 -RunNow

# Remove the scheduled task if ever needed:
.\setup_daily_task.ps1 -Uninstall
```

Every morning, the task runs [`run_daily.bat`](file:///g:/My%20Drive/Antigravity/Projects/email%20organizer/run_daily.bat) and writes your daily digest to `daily_summaries/`.

---

### Step 5: Connect to Antigravity as an MCP Server (Optional)

To let Antigravity manage your emails during chat sessions:
1. Open your Antigravity MCP settings.
2. Add the server entry from [`mcp_config_snippet.json`](file:///g:/My%20Drive/Antigravity/Projects/email%20organizer/mcp_config_snippet.json):
```json
{
  "mcpServers": {
    "email-organizer": {
      "command": "C:\\Users\\chase\\.venvs\\email-organizer\\Scripts\\python.exe",
      "args": ["-m", "email_organizer.cli", "serve-mcp"],
      "env": {
        "PYTHONPATH": "G:\\My Drive\\Antigravity\\Projects\\email organizer\\src",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```
Available agent tools:
- `gmail_status()`: Verify API connection and token.
- `gmail_list_unread()`: Inspect unread emails in inbox.
- `gmail_search(query)`: Search emails by sender, subject, date, or labels.
- `gmail_run_triage(dry_run)`: Run automated categorization.
- `gmail_daily_digest()`: Generate and return today's email briefing report.
- `gmail_apply_label(message_id, label_name, archive)`: Label or archive a message.

---

## ⚙️ Customizing Organization Rules

Edit [`config/rules.yaml`](file:///g:/My%20Drive/Antigravity/Projects/email%20organizer/config/rules.yaml) to tailor categories to your personal workflow:
- **Priority**: Rules are evaluated from lowest number (1 = highest priority) down.
- **Rules**: Match based on `from_contains`, `subject_contains`, or `has_header` (e.g. `List-Unsubscribe`).
- **Actions**:
  - `add_labels`: Gmail labels to attach.
  - `archive: true`: Automatically moves email out of Inbox.
  - `mark_read: true`: Marks email as read.
