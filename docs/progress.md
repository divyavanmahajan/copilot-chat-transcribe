# Progress

## Status

| Milestone | Status |
|-----------|--------|
| M1 models.py | ✅ Done |
| M2 parser.py | ✅ Done |
| M3 renderer.py | ✅ Done |
| M4 CLI entry point | ✅ Done |
| M5 Smoke test | ✅ Done |
| Showboat demo | ✅ Done |
| F1 Output folder (html + md + json) | ✅ Done |
| F2 render_markdown_doc() | ✅ Done |
| F3 connector.py (Playwright CDP) | ✅ Done |
| F4 CLI --connect flag | ✅ Done |
| F4b Auto-start Edge if port 9222 not open | ✅ Done |
| F5 --connect debugging (listener-before-navigation) | ✅ Done |
| F6 Show more (m/more paging in conversation picker) | ✅ Done |
| PKG Reformat as PyPI package (`copilot-chat-transcribe`) | ✅ Done |
| DOC README, architecture, demo updated | ✅ Done |

## Package layout

```
src/copilot_chat/
    __init__.py      # version
    models.py        # dataclasses
    parser.py        # JSON -> model
    renderer.py      # HTML + Markdown output
    connector.py     # Playwright CDP + Edge auto-start + response interception
    cli.py           # copilot-chat-transcribe entry point
examples/
    demo_parse.py    # parse walkthrough (uses installed package)
docs/
    spec.md, architecture.md, data-model.md, implementation-plan.md
    demo.md          # showboat walkthrough
    progress.md      # this file
pyproject.toml       # hatchling build, copilot-chat-transcribe entry point
README.md
.gitignore
```

## Notes

- Package name: `copilot-chat-transcribe` (PyPI), Python module: `copilot_chat`
- Entry point: `copilot-chat-transcribe = copilot_chat.cli:main`
- Core dep: `markdown>=3.0`; optional `copilot-chat-transcribe[connect]` adds `playwright>=1.40`
- Installed into `.venv` with `uv pip install -e ".[connect]"`
- Install playwright browsers: `playwright install msedge`

## --connect architecture notes

- `list_conversations`: registers `expect_response` **before** `page.goto(CHAT_BASE_URL)`; filters on `"RefreshNavPane"` in request body; 120s timeout allows sign-in
- `download_conversation`: registers `expect_response` before `page.goto(conversation-url)`; falls back to `page.evaluate(fetch(..., credentials:"include"))` with generated `x-session-id`
- `prompt_select_conversation`: fetches 50 conversations upfront; pages 10 at a time; `m`/`more` advances without re-fetching

## Package layout

```
src/copilot_chat/
    __init__.py      # version
    models.py        # dataclasses
    parser.py        # JSON → model
    renderer.py      # HTML + Markdown output
    connector.py     # Playwright CDP + Edge auto-start
    cli.py           # copilot-chat-transcribe entry point
examples/
    demo_parse.py    # parse walkthrough
docs/
    spec.md, architecture.md, data-model.md, implementation-plan.md
    demo.md          # showboat walkthrough
    progress.md      # this file
pyproject.toml       # hatchling build, copilot-chat-transcribe entry point
README.md
.gitignore
```

## Notes

- Package name: `copilot-chat-transcribe` (PyPI), Python module: `copilot_chat`
- Entry point: `copilot-chat-transcribe = copilot_chat.cli:main`
- Core dep: `markdown>=3.0`; optional `copilot-chat-transcribe[connect]` adds `playwright>=1.40`
- Installed into `.venv` with `uv pip install -e ".[connect]"`
- Install playwright browsers: `playwright install msedge`


## 2026-03-29 — Renamed to copilot-chat-transcribe

- Confirmed copilot-chat-transcribe not taken on PyPI
- Renamed src/copilot_chat/ → src/copilot_chat_transcribe/`n- Updated pyproject.toml, cli.py, README.md, all docs
- Reinstalled: copilot-chat-transcribe 0.1.0 working

