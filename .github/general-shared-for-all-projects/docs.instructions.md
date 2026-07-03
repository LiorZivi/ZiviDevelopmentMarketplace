---
applyTo: "agent-memory/**,human-docs/**"
---

# Documentation conventions (`agent-memory\` and `human-docs\`)

When writing or editing any doc under `agent-memory\` or `human-docs\`:

- **Always reference files and folders by their full path from the project root.** Example: write `src\comfywrap\capabilities\video\text_to_video\adapter.py`, not `adapter.py`, not `text_to_video\adapter.py`, and not the Python dotted form (`comfywrap.capabilities...`). A reader must be able to copy the path and find the file without guessing where it lives.
- Use **Windows-style backslash** separators in these root-relative paths.
- For installed third-party tools, give a locatable hint — comfy-cli installs into the active venv and its binary is at `.venv\Scripts\comfy.exe`; ComfyUI's own install is at `C:\AI\ComfyUI\resources\ComfyUI` with data root `C:\AI\Softwares`. Don't list a tool by bare name when the reader may need to find it.
- For workflow templates and produced media, give the real on-disk location (bundled templates under `src\comfywrap\data\workflows\`; produced videos under the ComfyUI output dir `C:\AI\Softwares\output\`).
- **Exceptions — keep these as written:**
  - Genuine Python identifiers: the entry-point literal `comfywrap.core.cli:main` and real `import` / `from ... import` statements inside code blocks.
  - Real shell invocations of the engine, e.g. `comfy run --json`.
  - Markdown link targets `[text](path)` must stay forward-slash (they are URLs).
  - ASCII tree diagrams may keep forward-slash directory indicators.
- **The split is by audience:** `agent-memory\` is written to be read by the **Copilot agent** (keep it short and high-signal); `human-docs\` is written to be read by **humans** (may be narrative). When behavior changes, update `agent-memory\` and the README so the agent's context stays accurate; update `human-docs\` when a human asks.
