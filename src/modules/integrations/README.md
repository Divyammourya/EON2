# Integrations

Calendar, email, and messaging — the parts of "manage my life" that
need real external services, not just the local machine.

## Tools

- `calendar_tool.py` — `CalendarTool`. Reads upcoming Google Calendar
  events, or creates a new one. "read:"/"create:" prefix (added by the
  action executor) picks the operation.
- `email_tool.py` — `EmailTool`. Reads recent/unread Gmail, or sends a
  new message. Same "read:"/"send:" prefix convention.
- `messaging_tool.py` — `MessagingTool`. Sends a message via Telegram
  bot or Slack incoming webhook (`messaging_provider` in
  config/settings.json picks which). No reading, no threads/channels —
  "notify me somewhere" is the feature, not a full chat client.
- `google_auth.py` — `GoogleAuthManager`, shared OAuth for Calendar +
  Gmail (same account, same consent flow, one cached token covers
  both).
- `datetime_parsing.py` — stdlib-only "tomorrow at 3pm" / "next monday
  at 10am" parsing for calendar event creation. Not a general date
  parser — falls back to sensible defaults rather than guessing.

## Setup

### Calendar + Email (Google)

1. In [Google Cloud Console](https://console.cloud.google.com/), create
   a project, enable the **Google Calendar API** and **Gmail API**,
   and create an OAuth Client ID of type **Desktop app**.
2. Download the client secret JSON, save it at
   `config/google_credentials.json` (or point `GOOGLE_CREDENTIALS_PATH`
   in `.env` at wherever you put it).
3. The first calendar/email request opens a browser for you to sign in
   and consent. After that, `data/google_token.json` caches the token
   and refreshes it automatically — no more browser popups.

```
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### Messaging

Pick one, set it as `messaging_provider` in `config/settings.json`:

**Telegram** (default):
1. Message [@BotFather](https://t.me/BotFather), `/newbot`, copy the
   token it gives you into `TELEGRAM_BOT_TOKEN` in `.env`.
2. Message your new bot once (anything) — bots can't message you
   first, they can only reply once you've started the conversation.
3. Get your chat ID from
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and put it in
   `TELEGRAM_CHAT_ID`.

**Slack**:
1. In a workspace you can add apps to, create an **Incoming Webhook**.
2. Put the URL it gives you in `SLACK_WEBHOOK_URL` in `.env`.

No new package needed — sent via `httpx`, already a dependency.

## Config

`config/settings.json`: `calendar_enabled`, `email_enabled`,
`messaging_enabled` (all default `true`), `messaging_provider`
(`"telegram"` or `"slack"`).

`.env` (secrets — never committed, already in `.gitignore`):
`GOOGLE_CREDENTIALS_PATH`, `GOOGLE_TOKEN_PATH`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, `SLACK_WEBHOOK_URL`.

## Permissions

Reading (`CALENDAR_READ`, `EMAIL_READ`) is auto-approved. Creating a
calendar event, sending an email, and sending a message
(`CALENDAR_CREATE`, `EMAIL_SEND`, `MESSAGE_SEND`) all require
confirmation by default — see `permissions/config.py` — since these
put content in front of another person, unlike everything else EON
does that only touches your own machine.

## Not built yet

- Multiple calendars/accounts — always `primary` calendar, whichever
  Google account you authenticated with.
- Replying to a specific email thread, or reading full email bodies
  (currently just subject/sender/snippet).
- Reading messages back from Telegram/Slack (send-only).
- Any provider besides Google (Calendar/Email) and
  Telegram/Slack (Messaging) — e.g. Outlook, WhatsApp, iMessage.
