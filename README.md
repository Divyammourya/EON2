# EON — Evolving Operating Nexus

EON is a modular, local-first personal AI assistant for the desktop. It is
designed to understand, reason, remember, plan, and act — on the user's
computer, not just in a chat window.

It is **not** a chatbot wrapper. It is an extensible AI runtime built around
independent modules for understanding, memory, planning, reasoning, execution,
and desktop interaction, wired together by a small service container and an
event bus.

---

## Status

- **Version:** 0.1.0
- **Phase:** Foundation complete — core intelligence under active development
- **Platform:** Windows (desktop control, voice, and hologram use Windows APIs)
- **Runs fully locally** via [Ollama](https://ollama.com); no cloud account required

---

## What it can do today

- **Conversation** — multi-turn chat with streaming replies, over a local LLM.
- **Long-term memory** — SQLite-backed semantic memory with embeddings,
  vector recall, and duplicate detection.
- **Identity** — a persistent persona and capability prompt, not a blank model.
- **Planning & reasoning** — intent detection, plan generation, and plan
  validation before acting.
- **Desktop control** — launch apps, open files/folders/URLs, control the
  clipboard, volume, brightness, windows, and take screenshots.
- **Automation** — type text, drive UI elements, organize files.
- **Integrations** — Google Calendar, email, and messaging (Telegram).
- **Voice** — wake word, speech-to-text (Faster-Whisper), text-to-speech
  (Piper / OpenAI), with Hindi/Hinglish support and barge-in.
- **Vision** — screen capture and image understanding via a vision model.
- **Coding workspace** — a repo-aware agent: project/file/git/search managers,
  symbol indexing, an AI editor, a diff/patch engine, a planner, and a
  terminal runner.
- **Proactive awareness** — ambient signals (downloads finishing, upcoming
  calendar events, hung windows) and idle check-ins.
- **Permissions** — a CONFIRM / VERIFY safety tier so high-risk actions
  (run command, delete files, send email/message) need explicit approval.
- **Desktop companion** — an optional PySide6 "hologram" overlay.

---

## Architecture

EON follows a strict modular design. Every request flows through one pipeline:

```text
User
  ↓
Conversation
  ↓
Perception
  ↓
Recall
  ↓
Context
  ↓
Brain
  ↓
Intent
  ↓
Planner
  ↓
Reasoning
  ↓
Execution
  ↓
Tools
  ↓
Response
```

New features integrate into this pipeline rather than bypassing it.

Key building blocks:

- `src/core/` — engine, service container, module loader, lifecycle, event bus.
- `src/bootstrap/` — assembles the application and registers services/modules.
- `src/modules/` — the feature modules (brain, memory, intent, planner,
  reasoning, execution, tools, voice, vision, automation, workspace, …).
- `src/interfaces/` — the contracts modules implement.
- `src/ui/` — the optional hologram overlay.

### Module map

| Module | Responsibility |
|--------|----------------|
| `brain` | Orchestrates a turn: builds context and calls the model |
| `conversation` | History, messages, streaming replies |
| `identity` | Persona, capabilities, system prompt |
| `memory` / `store` / `recall` | Semantic long-term memory pipeline |
| `context` / `perception` | Turn context and user-message understanding |
| `intent` / `planner` / `reasoning` | Understanding → plan → validate |
| `execution` / `actions` / `tools` | Acting on the computer |
| `automation` | Clipboard, volume, brightness, windows, input, files |
| `integrations` | Calendar, email, messaging |
| `voice` / `vision` | Speech and sight |
| `workspace` | The coding agent and its sub-systems |
| `permissions` | Action safety tiers |
| `monitor` / `proactive` | Ambient awareness and unprompted speech |
| `reflection` | Post-turn reflection |

---

## Requirements

- Python 3.12+
- [Ollama](https://ollama.com) running locally (default host
  `http://127.0.0.1:11434`)
- Windows for the desktop-control, voice, and hologram features

Install dependencies:

```bash
pip install -r requirements.txt
```

Pull a chat model and an embedding model (defaults are `qwen2.5:3b` and
`nomic-embed-text`):

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

---

## Configuration

Settings live in `config/settings.json`. Feature flags such as `voice_enabled`,
`vision_enabled`, `automation_enabled`, `proactive_enabled`, and
`ambient_awareness_enabled` are read from there at startup.

**Secrets never go in `settings.json`.** They live in a `.env` file (which is
git-ignored) and are read via `from_env()`. This includes API keys, bot tokens,
Google OAuth credentials, and the high-risk-action `AUTHORIZATION_PASSPHRASE`.

---

## Running

```bash
python main.py
```

This starts the interactive console. Depending on what's enabled in
`config/settings.json`, EON may also listen for its wake word, show the
hologram overlay, and speak up proactively.

Useful console commands:

- `listen` — speak your message instead of typing
- `enroll voice` — teach EON to recognize your voice
- `remind <minutes> <message>` — schedule a spoken reminder
- `exit` / `quit` — shut down

---

## Tests

```bash
pytest
```

The pure-Python parts of the codebase (memory, coding workspace, planning,
patching, command running) run and are tested on any platform. Windows-only
features are exercised on Windows.

---

## Documentation

- `docs/PROJECT.md` — vision and goals
- `docs/STATUS.md` — what's implemented, per module
- `docs/CURRENT_TASK.md` — where development currently stands
- `docs/architecture/` — architecture, modules, and system diagrams
- `docs/decisions/` — architecture decision records (ADRs)
- `docs/guides/` — coding, testing, git, contributing

---

## Design principles

- Local-first and privacy-focused
- Modular, service-based design — extend, don't rewrite
- Provider-independent (LLM, STT, TTS, vision are all swappable)
- No hardcoded behavior; explainable code
- Documentation updated whenever architecture changes

See `AGENTS.md` for the rules contributors (human or AI) should follow.

---

## License

See `LICENSE`.
