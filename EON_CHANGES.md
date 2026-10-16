# Voice/Identity Verification for High-Risk Actions

New permission tier above CONFIRM: VERIFY. A plain "yes" approves
opening apps, adding calendar events, overwriting the clipboard, etc.
(unchanged). But running a command, organizing/deleting files, or
sending an email/message now needs the configured authorization
passphrase, not just a yes/no — "someone else in the room" can still
talk to EON, but can't approve these without knowing the phrase.

## Design choice: passphrase, not voice biometrics

The feature request offered two options: real speaker verification,
or "just a spoken confirmation phrase." Went with the passphrase,
deliberately, over an ML voiceprint match:

- A proper speaker-verification model (resemblyzer, speechbrain, etc.)
  needs PyTorch — a very heavy dependency for this project, and not
  something I could meaningfully validate without real microphone
  audio to test against in this environment.
- A passphrase is exact, predictable, and testable — it either matches
  or it doesn't. A lightweight from-scratch voiceprint match (MFCCs +
  cosine similarity, no deep learning) would be lighter, but its
  accuracy would be genuinely mediocre, which is worse than no
  biometric claim at all: it would create false confidence in a
  security feature.
- The passphrase already satisfies the actual requirement in the
  request: "someone else in the room can't just tell it to do
  things" — they can't, unless they also know the phrase.

If you want real voice biometrics later, the extension point is
narrow and clean: `PermissionManager._resolve_verify` is the only
place that would need a second check (e.g. "and the audio matched the
enrolled voiceprint") alongside/instead of the passphrase compare.

## New: PermissionLevel.VERIFY

- `src/modules/permissions/models.py` — new `PermissionLevel.VERIFY`.
  `PendingConfirmation` gained `level` (which tier this is) and
  `verify_attempts` (wrong-passphrase counter).
- `src/modules/permissions/config.py` — new `HIGH_RISK_ACTION_TYPES`
  (`RUN_COMMAND`, `ORGANIZE_FILES`, `EMAIL_SEND`, `MESSAGE_SEND` — the
  three examples from the request, verbatim: "delete, send, run
  arbitrary commands"; ORGANIZE_FILES is the closest thing to a
  dedicated "delete" action type, since delete/move/rename/create are
  all bundled into one ActionType, same as before this change).
  `PermissionsServiceConfig` gained `high_risk_action_types`,
  `authorization_passphrase`, `max_verify_attempts` (default 3), and a
  `from_env()` classmethod that reads `AUTHORIZATION_PASSPHRASE` from
  `.env` — kept out of settings.json, same reasoning as every other
  secret in this project (API keys, bot tokens): it's a secret, not a
  setting.
- `src/modules/permissions/manager.py`:
  - `classify()` checks `high_risk_action_types` first — VERIFY beats
    CONFIRM.
  - `resolve()` branches by tier: a negative word ("no"/"cancel"/etc.)
    still declines either tier immediately — you don't need the
    passphrase to say no. For VERIFY, approving requires the message
    to match the passphrase after normalizing (lowercase, punctuation
    stripped, whitespace collapsed) — deliberately an *exact* match
    after normalization, not fuzzy, since approximate matching would
    make the passphrase guessable by degrees. Three wrong attempts
    (configurable) and the confirmation is denied outright rather than
    left open to keep guessing.
  - If no passphrase is configured at all, VERIFY quietly falls back
    to a plain yes/no (same as CONFIRM) — logged as a warning both at
    startup and on each such approval, so this is never a silent gap.
  - `describe_pending()` / the initial confirmation prompt (now built
    in `ConversationManager._confirmation_prompt`) use different
    wording for VERIFY vs CONFIRM, and flag explicitly when VERIFY is
    running without a passphrase configured.
- `src/modules/conversation/manager.py` — the single call site that
  used to check `== PermissionLevel.CONFIRM` now checks `!=
  PermissionLevel.AUTO` (so it also catches VERIFY), and delegates to
  the new `_confirmation_prompt` helper for tier-appropriate wording.
- `src/bootstrap/services.py` — builds `PermissionsServiceConfig` via
  `.from_env()`, logs clearly at startup whether high-risk actions are
  actually passphrase-protected or just yes/no-protected.
- `.env` — added `AUTHORIZATION_PASSPHRASE` (empty by default).

## Verified (offline)

- `classify()` across all relevant action types: reads stay `auto`,
  calendar-create/clipboard-write/window-control stay `confirm`,
  run_command/organize_files/email_send/message_send are now `verify`
  — confirmed no regressions on the pre-existing tiers.
- No passphrase configured: a plain "yes" approves a VERIFY action
  (with a warning logged) — matches "or just a spoken confirmation
  phrase" being optional, not a hard requirement to use EON at all.
- Passphrase configured: "yes" alone does *not* approve it
  (`not_a_response`); the correct passphrase does, even with different
  case/punctuation ("Only Tony can authorize this." still matches
  "only tony can authorize this").
- Three wrong passphrase attempts in a row correctly denies and clears
  the pending confirmation (lockout), rather than leaving it open
  indefinitely.
- "cancel"/"no" correctly declines a VERIFY-tier action without
  needing the passphrase.
- Confirmation prompt wording checked for all three cases: VERIFY with
  passphrase, VERIFY without one, and plain CONFIRM — no more
  redundant "[high-risk] ... high-risk action" double-wording (caught
  and fixed during testing).

## Not built (see design choice above)

- Actual voice biometrics/speaker verification. The passphrase is the
  shipped mechanism; `_resolve_verify` is the clean extension point if
  a real voiceprint check gets added later.

---

# Fix: EON's Hindi/Hinglish replies were unintelligible

Bug report: asked EON things in Hindi/Hinglish (typed, e.g. "mujhe
japan ke bare me jankari do") — text replies were broken Devanagari
Hindi, and speech was unintelligible.

## Root causes (two separate problems, both real)

1. **Text quality**: the local chat model (qwen2.5:3b) is small and
   weak at generating Devanagari-script Hindi — it only attempted
   Hindi when explicitly told "hindi me", and even then produced
   grammatically broken output ("जपान को प्रसिद्ध विश्वभरी बैकथा
   में..." isn't real Hindi). This is a model-capability limit, not a
   bug in the pipeline — the intent/action/reasoning/execution layers
   all worked correctly around it (confirmed from the pasted log).

2. **Speech pronunciation**: the Voice module already has real,
   working infrastructure for a separate Hindi Piper voice
   (`PiperProvider._select_voice`, `detect_reply_language` in
   `src/utils/text.py`, `VoiceServiceConfig.piper_hi`) — but
   `src/bootstrap/services.py` built `VoiceServiceConfig()` with
   nothing but hardcoded defaults, never reading a Hindi voice path
   from `config/settings.json` at all. So even a manually downloaded
   Hindi voice file would never actually get wired in — every
   Hindi-script reply was being spoken with the default *English*
   Piper voice, which can't pronounce Devanagari at all. That's the
   direct cause of "can not even understand what EON is trying to
   say".

## Fixes

- `src/modules/identity/manager.py` — added system-prompt rules: (a)
  always reply in the language the user just used, without being
  asked, (b) when that's Hindi/Hinglish, reply in **Hinglish (Roman
  script)**, not Devanagari — a small local model is noticeably more
  coherent in Hinglish than Devanagari (closer to the Latin-script
  text it's mostly trained on), and Hinglish is also what the
  *default* English Piper voice can actually attempt to pronounce
  reasonably, with no new voice model needed. (c) keep sentences short
  — long sentences are where small models are most likely to produce
  broken grammar, Hindi or otherwise.
- `src/bootstrap/services.py` — now reads `piper_hi_model_path` /
  `piper_hi_config_path` from `config/settings.json` into
  `VoiceServiceConfig.piper_hi`, closing the gap above. Logs clearly
  on startup whether a Hindi voice is configured.
- `config/settings.json` — added `piper_hi_model_path` /
  `piper_hi_config_path` (both empty by default — no Hindi voice ships
  with EON, same as the existing `piper_hi` docstring already said).

## If you want proper Devanagari Hindi speech (optional, not required)

The Hinglish system-prompt fix above needs nothing else and works
today. If you'd rather EON actually speak fluent Devanagari Hindi
(closer to a real Hindi voice, not Hinglish-via-English-voice):

1. Download a Hindi Piper voice — e.g. `hi_IN-pratham-medium` or
   `hi_IN-rohan-medium` — from
   https://huggingface.co/rhasspy/piper-voices/tree/main/hi/hi_IN
   (grab both the `.onnx` and `.onnx.json` files).
2. Save them anywhere, e.g. `data/voice/piper/voice_hi.onnx` +
   `data/voice/piper/voice_hi.onnx.json`.
3. Set `piper_hi_model_path` / `piper_hi_config_path` in
   `config/settings.json` to those paths.

`detect_reply_language` (already built, in `src/utils/text.py`) will
then route any Devanagari-script sentence to that voice automatically
— but the text quality problem (broken Devanagari grammar from the 3B
model) would still need a bigger/more multilingual model to fully fix;
the Hinglish prompt change doesn't depend on any of this and is the
more immediately reliable fix.

## Verified

- System prompt renders correctly with the new rules appended.
- `config.get("piper_hi_model_path"/"piper_hi_config_path")` correctly
  leaves `VoiceServiceConfig.piper_hi` as `None` when both are empty
  (today's default), and correctly populates it when both are filled
  in.

## Not fixed (out of scope for a config/prompt change)

- qwen2.5:3b's actual Hindi-generation quality, if you do want
  Devanagari replies specifically — that needs a larger or
  Indic-tuned model; ask if you want a specific recommendation for
  your hardware.

---

# Integrations — Calendar / Email / Messaging

Fills in the fourth roadmap item: EON can now read/create Google
Calendar events, read/send Gmail, and send a Telegram/Slack message,
using the same Intent -> Action -> Executor -> Tool pipeline as
everything else (Vision, automation/) -- no new architecture invented.

## New module: src/modules/integrations/

- `config.py` -- `IntegrationsConfig`. Enabled flags + provider choice
  come from config/settings.json (calendar_enabled, email_enabled,
  messaging_enabled, messaging_provider); secrets (tokens, webhook
  URLs, credential file paths) come from `.env` via `from_env()` --
  kept out of settings.json, which is plain versioned JSON, not a
  secrets store.
- `google_auth.py` -- `GoogleAuthManager`. Shared OAuth for Calendar +
  Gmail (same Google account, same consent flow, one cached token
  covers both -- both scopes are requested together up front so a
  later addition of Gmail scopes can't invalidate an existing
  Calendar-only token). First use opens a browser for consent; after
  that, data/google_token.json is cached and auto-refreshed.
- `calendar_tool.py` -- `CalendarTool` ("calendar" tool). Reads
  upcoming events (today/tomorrow/this week), or creates one from
  natural language like "schedule a meeting with the team tomorrow at
  3pm".
- `email_tool.py` -- `EmailTool` ("email" tool). Reads recent/unread
  Gmail (sender/subject/snippet), or sends one: "send an email to
  jane@example.com saying the report is ready".
- `messaging_tool.py` -- `MessagingTool` ("messaging" tool). Sends via
  Telegram bot or Slack incoming webhook (config-selected) -- both
  chosen specifically because neither needs an OAuth flow, unlike
  WhatsApp/iMessage/most chat platform APIs. Send-only by design (no
  reading messages back) -- "notify me somewhere" is the feature, not
  a full chat client.
- `datetime_parsing.py` -- stdlib-only "tomorrow at 3pm" / "next monday
  at 10am" parsing for event creation. Deliberately not a general NLP
  date parser (no new dependency like `dateparser`) -- falls back to
  sensible defaults rather than guessing at anything fancier.
- `README.md` -- setup steps for Google OAuth + Telegram/Slack, config
  keys, what's not built (multiple calendars, email threads/full
  bodies, reading messages back, any provider besides Google/
  Telegram/Slack).

## Edited files

- `src/modules/actions/models.py` / `src/modules/intent/models.py` --
  added CALENDAR_READ, CALENDAR_CREATE, EMAIL_READ, EMAIL_SEND,
  MESSAGE_SEND. Read and create/send are separate types per service
  (not bundled into one like VOLUME_CONTROL bundles up/down/mute) --
  see permissions note below for why that split matters here
  specifically.
- `src/modules/intent/classifier.py` -- trigger phrases for all five,
  added to the same rule-based block as the rest of automation/.
  Create/send variants checked before their read siblings (matching
  the existing CLIPBOARD_WRITE-before-READ ordering) since they're the
  more specific signal.
- `src/modules/actions/router.py` -- maps the five new intents to their
  matching action types.
- `src/modules/actions/executor.py` -- new branches for all five,
  added to `_AUTOMATED_ACTION_TYPES` (real external side effects, so
  gated by automation_enabled same as everything else non-CHAT). Each
  service's Tool gets a "read:"/"create:"/"send:" prefix from the
  executor so one CalendarTool/EmailTool instance can tell which
  operation was asked for -- MessagingTool only has one operation
  (send) so no prefix needed there.
- `src/modules/permissions/config.py` -- CALENDAR_READ and EMAIL_READ
  added to the auto-approve allow-list; CALENDAR_CREATE, EMAIL_SEND,
  and MESSAGE_SEND are deliberately left out, so they require
  confirmation by default. This is exactly the "send"-style example
  already called out in this file's own docstring -- these three put
  content in front of another person, unlike everything else EON does
  that only touches your own machine.
- `src/modules/permissions/manager.py` -- added confirmation-prompt
  descriptions for the three actions that now require one.
- `src/core/config.py` -- calls `load_dotenv()` once at startup
  (python-dotenv was already a dependency, unused until now) so
  `os.getenv()` in `integrations/config.py` picks up `.env` values.
- `src/bootstrap/services.py` -- builds `IntegrationsConfig` from
  settings.json + `.env`, constructs one shared `GoogleAuthManager`,
  registers `CalendarTool`/`EmailTool`/`MessagingTool` into the
  existing `ToolRegistry` alongside the automation/ tools.
- `config/settings.json` -- added calendar_enabled, email_enabled,
  messaging_enabled (all default true), messaging_provider (default
  "telegram").
- `.env` -- added (empty/template) keys: GOOGLE_CREDENTIALS_PATH,
  GOOGLE_TOKEN_PATH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
  SLACK_WEBHOOK_URL. Already gitignored.
- `requirements.txt` -- added google-api-python-client,
  google-auth-httplib2, google-auth-oauthlib. (httpx, used for the
  Telegram/Slack HTTP calls, was already a dependency.)

## Verified (offline; this sandbox has no display, no real Google/
## Telegram/Slack credentials)

- Intent -> action routing for all five new phrasings, plus a
  regression check that existing intents (open_app, volume_control,
  etc.) still route correctly.
- Permission classification: CALENDAR_READ/EMAIL_READ -> auto;
  CALENDAR_CREATE/EMAIL_SEND/MESSAGE_SEND -> confirm. Confirmation
  description text renders correctly for a real target string.
- `CalendarTool`/`EmailTool`/`MessagingTool` against mocked
  Google API / httpx calls: create-event body construction, event
  listing/formatting (including all-day events, which don't have a
  `dateTime`, only a `date`), email send MIME/base64 construction,
  email read formatting, Telegram POST payload construction.
- `datetime_parsing.parse_when()` against six phrasings (tomorrow,
  today, bare time-of-day, "next <weekday>", bare weekday, noon).
- Found and fixed during testing: event titles were including the
  literal trigger verb ("schedule a meeting" -> title "schedule a
  meeting with the team" instead of "meeting with the team"), and
  all-day events were rendered with a fake midnight time. Both fixed
  in `calendar_tool.py`.

## Not built yet (see integrations README)

- Multiple calendars/accounts -- always the `primary` calendar of
  whichever Google account authenticated.
- Email thread replies, full email bodies (currently
  subject/sender/snippet only).
- Reading messages back from Telegram/Slack (send-only).
- Any provider besides Google (Calendar/Email) and Telegram/Slack
  (Messaging) -- e.g. Outlook, WhatsApp, iMessage.

---

# Vision Module — Screen Understanding

Fills in the previously-empty `src/modules/vision/` folder. EON can now
answer "what's on my screen", "describe this window", "what does this
error say", etc. by taking a screenshot and asking a vision-capable
local model about it — same request pipeline as everything else
(`Intent → Action → Executor`), no new pipeline invented.

## New files

- `src/modules/vision/config.py` — `VisionConfig` (enabled flag, which
  Ollama vision model to use, image downscale size/quality, whether to
  include the foreground window title as context).
- `src/modules/vision/models.py` — `ScreenCapture` (image bytes + size
  + window title + timestamp), `VisionResult` (success/description/
  message, matches the `ActionResult` shape used elsewhere).
- `src/modules/vision/capture.py` — `ScreenCapturer`. Uses
  `PIL.ImageGrab` (Windows/macOS, matching the rest of EON's tools
  layer which already assumes Windows via `os.startfile`/`win32com`).
  Downscales + JPEG-encodes the screenshot, and best-effort reads the
  foreground window title via `win32gui`. Returns `None` on failure
  (no display, missing Pillow) rather than raising.
- `src/modules/vision/analyzer.py` — `VisionAnalyzer`. Builds the
  prompt (falls back to a general "describe the screen" prompt when no
  question was asked, prefixes the window title when known) and calls
  the vision model.
- `src/modules/vision/manager.py` — `VisionManager`, the facade
  everything else should use. `describe_screen(question="")` handles
  the disabled/capture-failed/model-unreachable cases and always
  returns a `VisionResult`, never raises.
- `src/modules/vision/README.md` — requirements (Pillow, pywin32,
  `ollama pull llava`), config keys, what's not built yet (clicking
  elements, webcam, continuous/ambient watching).

## Edited files

- `src/modules/ai/provider.py` / `src/modules/ai/manager.py` — added
  `chat_with_image(prompt, image_bytes, model=...)`. Single-turn by
  design (no history) since vision queries are always "here's the
  screen right now", and takes an explicit `model` override since the
  default chat model (`qwen2.5:3b`) isn't vision-capable.
- `src/modules/intent/models.py` — added `IntentType.VISION`.
- `src/modules/intent/classifier.py` — added `VISION_TRIGGERS` (checked
  before `APP_KEYWORDS`/`SEARCH_KEYWORDS`, same slot as the existing
  terminal-trigger check) plus a `_VISION_SAY_PATTERN` regex so "what
  does this **error** say" / "what does that **message** say" match
  even with words in between, not just the exact phrase.
- `src/modules/actions/models.py` — added `ActionType.VIEW_SCREEN`.
- `src/modules/actions/router.py` — `IntentType.VISION →
  ActionType.VIEW_SCREEN`.
- `src/modules/actions/executor.py` — takes an optional `vision:
  VisionManager`, new `VIEW_SCREEN` branch. Deliberately **not** added
  to `_AUTOMATED_ACTION_TYPES` — it's read-only (no side effects on the
  user's machine), so it's gated by its own `vision_enabled` flag
  inside `VisionManager` instead of `automation_enabled`. A user should
  be able to turn one on without the other.
- `src/bootstrap/services.py` — reads `vision_enabled`/`vision_model`
  from `config/settings.json` (the `vision_enabled` key already existed
  there, unused, before this change), builds `VisionManager`, passes it
  into `ActionExecutor`, registers it in the container as `"vision"`.
- `config/settings.json` — `vision_enabled: false → true`, added
  `vision_model: "llava"`.
- `requirements.txt` — added `Pillow==11.3.0` and `pywin32==311`
  (`pywin32` was already a hard runtime dependency via `win32com`
  elsewhere in the codebase but was missing from this file).

## Verified (offline, this sandbox is Linux/no display/no Ollama server)

- Intent → action routing for: "what is on my screen", "describe my
  screen", "take a screenshot", "what does this error say", "what does
  that message say" — all correctly route to `VIEW_SCREEN`. Re-checked
  "open chrome" / "search Elon Musk" / "open downloads" / terminal
  commands still route correctly (no regressions).
- `VisionManager.describe_screen()` with mocked capture/analyze:
  success path, `vision_enabled=False` path, and capture-failure path
  all return the right `VisionResult`.
- `ScreenCapturer.capture()` against a real (display-less) Pillow call:
  fails gracefully, returns `None`, logs — doesn't crash.
- `ActionExecutor` with `automation_enabled=False`: confirmed
  `VIEW_SCREEN` still executes (it isn't gated by that flag), and
  confirmed it returns a clean error when no `VisionManager` is wired.

## Not built yet (see Vision README)

- Locating/clicking specific on-screen elements.
- Webcam input.
- Continuous/ambient watching — capture is on-demand only, triggered by
  a user request.

---

# Open Apps / Websites / Folders + Web Search — Verified & Enabled

Requested feature: "EON, open chrome" → Chrome opens; "search Elon Musk" →
searches in the browser. Turns out the full pipeline for this already
existed (`Intent → Action → Plan → Reasoning → Execution → ResourceService
/ ToolRegistry`), it just wasn't switched on. Rather than rebuild it,
verified it end-to-end and closed the gaps.

## Root cause it wasn't working

- `config/settings.json` had `automation_enabled: false`, which is the
  kill-switch `ActionExecutor` checks before running `OPEN_APP`,
  `SEARCH_WEB`, `OPEN_URL`, or `RUN_COMMAND`. With it off, EON would only
  ever reply "Automation is currently disabled..." instead of acting.

## Edited files

- `config/settings.json` — `automation_enabled` flipped to `true` so
  "open chrome" / "search X" / "open downloads" actually execute instead
  of being explained-but-declined.
- `src/modules/tools/resource/url_launcher.py` — expanded the well-known
  sites dict (added twitter/x, facebook, instagram, linkedin, netflix,
  amazon, spotify, whatsapp, maps, twitch, discord, wikipedia, claude).
  Added a `known_names` property.
- `src/modules/tools/resource/folder_launcher.py` — added a matching
  `known_names` property.
- `src/modules/tools/resource/resolver/resolver.py` — `ResourceResolver`
  now accepts `folder_names`/`url_names` instead of hardcoding its own
  copy of those sets. Previously this list was duplicated (and already
  slightly out of sync) between `UrlLauncher`/`FolderLauncher` and the
  resolver; now there's one source of truth per launcher.
- `src/modules/tools/resource/launcher.py` — `ResourceLauncher` now
  passes `self.folders.known_names` / `self.urls.known_names` into the
  resolver it builds.

## Verified (offline, win32-only calls stubbed out — this sandbox is Linux)

- `IntentClassifier` + `ActionRouter`: "open chrome" → `OPEN_APP`("chrome"),
  "search Elon Musk" → `SEARCH_WEB`("elon musk"), "open downloads" →
  `OPEN_APP`("downloads") [resolved as a folder downstream], "open netflix"
  → `OPEN_APP`("netflix") [resolved as a URL downstream], "go to
  github.com" → `OPEN_URL`.
- `ResourceResolver` with the launchers' real `known_names`: "downloads" →
  FOLDER, "netflix"/"whatsapp" → URL, "chrome" → APPLICATION (chrome.exe
  is already in `data/cache/applications.json`), "somerandomthing" →
  UNKNOWN.
- Confirmed `data/cache/applications.json` already has an entry for
  `chrome` (`C:\Program Files\Google\Chrome\Application\chrome.exe`), and
  `ApplicationBuilder` also assigns it the `"chrome"` alias when resolving
  the Start Menu shortcut — so "open chrome" resolves either way.

## Not touched

- No changes to `IntentClassifier`, `ActionRouter`, `Planner`, `Reasoner`,
  `ExecutionManager`, or `ActionExecutor` — that whole pipeline was
  already correct.
- `RUN_COMMAND` / terminal automation is also now gated by the same
  `automation_enabled` flag — worth knowing since flipping it on doesn't
  just affect app/URL opening.

---

# Voice Module — Engine Wiring (Plan A)

## New files

- `src/modules/voice/config.py` — `VoiceServiceConfig`: picks STT/TTS provider names + their constructor kwargs. Plain dataclass, no third-party imports (mirrors `MemoryConfig`).
- `src/modules/voice/service.py` — `VoiceService`: the single entry point for the rest of EON. Owns the `VoiceManager` + `Microphone` + `Speaker`. Exposes `initialize/shutdown/health_check`, `start_session/stop_session`, and two convenience methods that actually do a full round trip:
  - `listen_once(session_id, seconds)` — records from the mic, wraps it as WAV, calls the STT provider, returns the transcript.
  - `say(session_id, text)` — calls the TTS provider, plays the resulting audio through the speaker.
- `src/modules/voice/module.py` — `VoiceModule(Module)`: lifecycle wrapper (`initialize/start/stop/shutdown/health_check`), same shape as `MemoryModule`.
- `src/modules/voice/bootstrap.py` — `register(engine, container)`: pulls `"voice"` out of the container, wraps it in `VoiceModule`, registers it with `engine.module_loader`. Same shape as `memory/bootstrap.py`.
- `src/modules/voice/providers/sounddevice_speaker.py` — filled in the empty stub. `SoundDeviceSpeaker(Speaker)`, playback via `sounddevice.OutputStream`, mirrors `SoundDeviceMicrophone`'s structure and error handling.

## Edited files

- `src/modules/voice/session.py` — **bug fix**: `VoiceSessionManager` only defined `update_state(...)`, but `VoiceManager` calls `update_session_state(...)` in 9 places. This was a latent `AttributeError` waiting to happen the moment anyone actually called `transcribe`, `speak`, `start_listening`, etc. Renamed the method to `update_session_state` to match.
- `src/bootstrap/services.py` — constructs the real provider stack (`FasterWhisperProvider` for STT, `PiperProvider` for TTS, `SoundDeviceMicrophone`/`SoundDeviceSpeaker` for I/O), wires them into a `VoiceManager`, builds the `VoiceService`, and registers it in the container as `"voice"` — same pattern as how `memory_service` is built and registered as `"memory"`.
- `src/bootstrap/modules.py` — now also calls `register_voice(engine=engine, container=container)` alongside `register_memory(...)`.

## Verified

Ran a full lifecycle smoke test (fake STT/TTS/mic/speaker standing in for the real libraries, since this sandbox can't install `faster-whisper`/`piper`/`sounddevice`): `initialize → start → health_check → start_session → listen_once → say → stop_session → stop → shutdown`. All passed, including the `update_session_state` fix.

## Still open (not touched, flagged only)

- `src/modules/voice/providers/ollama.py` is still an empty stub. `VoiceProviderType.OLLAMA` exists in the models, but Ollama isn't actually a speech engine (no built-in STT/TTS) — this looks like a placeholder for a *local LLM-brokered* voice pipeline rather than a real provider. Left alone rather than inventing behavior for it; worth deciding what it's actually supposed to do before implementing it.
- `PiperProvider` needs a real `.onnx` voice model + config file on disk at whatever path you set in `VoiceServiceConfig.piper`; `FasterWhisperProvider` will download a Whisper model on first use. Neither is included here.
- `core/main.py` is still empty — there's no actual process entrypoint yet that calls `ApplicationBuilder().build()`. Worth doing next so you have something to literally run.

## Next: JARVIS-style features

With Voice now a real, lifecycle-managed module, the next layer (wake word, always-on listening loop, personality in TTS responses, proactive speech) can build on `VoiceService` directly instead of reaching around the architecture.

---

# Personality Layer (JARVIS-style tone)

## New files

- `src/modules/identity/personality.py` — `PersonalityProfile`: a small dataclass (tone descriptors, address term, wit level, formality, proactivity, verbosity, signature phrases) plus four presets in `PERSONALITY_PRESETS`: `"jarvis"`, `"friday"`, `"edith"`, `"neutral"`. Kept separate from `IdentityProfile` (who EON is) and `Capability` (what EON can do) — this is purely *how EON sounds* (Single Responsibility Principle).

## Edited files

- `src/modules/identity/manager.py` — `IdentityManager` now takes an optional `personality: PersonalityProfile` (defaults to the JARVIS preset), and `system_prompt()` includes a new "Personality" section built from it. This is the actual prompt the LLM sees (`brain/context.py` calls `identity.system_prompt()`), so this affects every text and voice reply.
- `src/modules/voice/config.py` — added `voice_id` and `speaking_rate` defaults, so the *sound* of EON's voice can also be tuned per personality, not just the wording.
- `src/modules/voice/service.py` — `say()` now applies those defaults unless a caller explicitly overrides them.
- `src/bootstrap/services.py` — `IdentityManager` is now constructed with `personality=PERSONALITY_PRESETS["jarvis"]` explicitly, so switching to `"friday"`, `"edith"`, or `"neutral"` later is a one-line change in the composition root.

## Verified

Ran a smoke test confirming: the JARVIS preset renders correctly into `system_prompt()` (tone, "sir", signature phrases all present), the default constructor argument still resolves to JARVIS, and swapping to the FRIDAY preset changes only what it should (address term, tone) without touching identity facts or capabilities. Re-ran the earlier Voice lifecycle smoke test too — no regressions.

## Notes / things you may want to tune

- `src/modules/ai/prompts.py` (`SYSTEM_PROMPT`) and `src/modules/identity/prompt.py` (`build_identity_prompt`) are both **dead code** — neither is imported anywhere. `IdentityManager.system_prompt()` is the one actually wired into `brain/context.py`. Left them untouched since removing them wasn't part of this task, but worth deleting later to avoid confusion about which prompt is "real."
- The presets are a starting point — wording, wit level, and signature phrases are easy to hand-tune in `personality.py` once you hear how the LLM actually plays each one.
- Voice tone (`voice_id`, `speaking_rate`) currently has to be set manually per preset in `bootstrap/services.py`; there's no automatic mapping from a chosen `PersonalityProfile` to voice settings yet — that'd be a reasonable next small step if you want the *voice itself* (not just wording) to shift with the preset.
