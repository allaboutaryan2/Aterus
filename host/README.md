# Aterus

Your agents, within reach. An independently authored Mac agent hub, with Shed used as a behavior reference. **Development build; full parity and the real Kiro/phone milestone are not complete.** See [PARITY.md](PARITY.md) for the source-backed scope and [VALIDATION.md](VALIDATION.md) for evidence.

## Launch

```sh
cd /Users/apple/Documents/Codex/2026-11-01/new-chat-3/Aterus
python3 aterus.py --workspace "$PWD" --data-dir "$PWD/.aterus-data"
```

Or double-click `Start-Aterus.command`. Python 3.9+ on macOS/Linux is required. No package download is required for this build. The original implementation at `../new-chat/Aterus` is preserved; this session could write only to the new workspace.

The service listens on `127.0.0.1:4380`. Open its private startup URL on the Mac; the fragment contains a one-use owner credential. Do not share it. Sessions may use the launch workspace or its subdirectories. To use other projects, launch with their common parent as `--workspace`. Choose the narrowest useful parent. Every paired device can control agents and files within this scope; an agent's own filesystem permissions remain those of its Mac account.

## Implemented behavior

- Kiro, Claude Code, Codex, Gemini, OpenCode and Pi installation detection. Read-only version/auth probes distinguish signed-out, unknown and environment-blocked states. Signed in does not imply a verified model response. Health refresh runs in the background.
- Direct-exec PTYs, without an intervening shell. Real keyboard input, resize and interruption; bounded shutdown escalation and process-group cleanup. Detached processes that deliberately create separate process groups are outside this cleanup guarantee.
- Actual terminal rendering through vendored xterm.js, including raw VT sequences and split byte streams. Serialized browser input and byte-offset polling with reconnect handling. xterm's license/provenance is in `public/vendor/`; it is a locally available beta version and still needs real-browser QA.
- CLI help checked optional model/resume flags. Kiro session and model discovery via its CLI, with exact resume-ID checks in the selected workspace. Unknown schemas fail closed. Other agents' native discovery remains pending.
- SQLite history and private transcripts, restart interruption records, and a per-data-directory single-instance lock. Running agents stop on service shutdown; live PTYs do not survive restart. New sessions' native IDs are not automatically captured yet.
- Explicit cross-agent handoff: create a new session in the same workspace and prepare instructions plus at most 6,000 transcript bytes for review in the prompt field. Press Send when the target is ready. Native memory and approvals are not transferred. The source session remains running until you stop it.
- Authenticated project listing, downloads (20 MiB), UTF-8 text preview (256 KiB), and new-file uploads (4 MiB) under `uploads/`. Uploads never overwrite an existing file. Hidden/dependency files and symlink paths are excluded. File opens pin directory descriptors to prevent symlink-swap escapes.
- One-use owner bootstrap, one-use 10-minute pairing codes, hashed device tokens, 30-idle-day expiration, revocation and logout. Host/origin/content-type/duplicate-header checks; explicit root boundaries; local-only owner bootstrap.
- Original responsive UI and PWA manifest/icons/service worker. The worker caches only the public app shell, never API responses, credentials, terminals or project files. Offline shell availability does not provide offline agent access. Background push is not implemented.

## Kiro first milestone

Kiro CLI 2.36.0 is installed. Its help confirms `chat`, `--model`, `--resume-id`, `--list-sessions`, `--list-models`, and JSON output. Actual discovery/account access is blocked in this execution environment; its account probe reports no signed-in account. The earlier sandbox probe reported Claude signed out, but user-run screenshots now confirm real Claude responses through Aterus using the existing Mac login. Codex reports signed in; its model exchange remains unverified.

On the Mac, outside this restricted execution context:

1. Run `kiro-cli login` and complete Kiro's normal browser login. Alternatively use Aterus → New session → Kiro → Sign in to agent.
2. Launch Aterus with a dedicated test workspace and open the startup URL.
3. Select Kiro and workspace; create a session, or Refresh native sessions and select an exact ID. Discovery errors are shown explicitly.
4. Send a harmless prompt. Verify a real response, then request a harmless action that produces a normal approval. Answer using the terminal's displayed options. Continue the conversation, then End session.
5. Confirm output stops, input is rejected, and no child agent remains. Repeat exact native resume and browser reconnect.

The real Kiro JSON schemas and full-screen behavior still require this runtime check. Do not disable agent trust mechanisms to make testing pass.

## iPhone access

No public access or tunnel was created. To use your own authorized HTTPS reverse proxy, forward to `http://127.0.0.1:4380`, preserve its public Host header, and launch:

```sh
python3 aterus.py --workspace /path/to/projects --public-url https://your-private-origin.example
```

Use the Mac's local startup URL to become owner, then Devices → Create pairing code. Open the HTTPS origin on the phone and enter the code. Phone pairing cannot create more codes. On iPhone, Safari → Share → Add to Home Screen uses the PWA metadata. Wi-Fi, cellular, Home Screen installation and background notifications have not been tested. QR pairing, tunnel management and Web Push remain gaps. The proxy must prevent outsiders from reaching the service as a forged local Host; do not expose the bare HTTP listener.

## Startup and lifecycle

`lifecycle.py` generates a private user-scoped launchd plist and prints enable/disable commands. It does not install or activate anything automatically:

```sh
python3 lifecycle.py --write-plist ./app.aterus.agent-hub.plist --workspace /path/to/projects --data-dir /path/to/private/aterus-data
```

First launch manually and pair the owner browser using the same data directory. Stop the manual service before enabling startup. Startup output is discarded to avoid logging the owner credential. If owner access is lost, stop the job and run manually again to obtain a new one-use URL. Disable startup using the commands printed by the generator. Disabling preserves history. Automatic updates and a complete installer/uninstaller remain pending; update manually only with a backup of the data directory.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node tests/test_browser_glue.cjs
node --check public/app.js
node --check public/sw.js
```

See `VALIDATION.md`. Fixture tests do not consume AI tokens and do not prove real account, browser rendering or phone functionality.

## Remaining scope

The source-backed parity tracker covers the full remaining scope, including structured conversation/task state and approval detection, all-agent session discovery, verified external/Codex Desktop interfaces, routing/model defaults, queued tasks, inter-session communications with loop/flood controls, share-sheet/Shortcut/media ingestion, QR pairing, HTTPS provider lifecycle, background push/preferences, safe idle cleanup, complete install/update/uninstall, and desktop/iPhone QA. No decorative implementations stand in for these features.

Transcripts remain unbounded private local logs; automatic idle cleanup and rotation are not yet provided. Review uploads before committing project files. No license has been selected for original Aterus code. Third-party components retain their own licenses; Shed source/assets were not copied.


## OpenCode integration

Aterus detects the interface from installed CLI help rather than assuming all executables named `opencode` support the same commands.

**Installed here: Go OpenCode 0.0.55.** Start it through New session → OpenCode → select workspace → Open session, leaving model and resume fields empty (these are disabled for this version). Focus the OpenCode editor before sending a prompt; Aterus submits with Ctrl+S. Dedicated buttons expose Models (Ctrl+O), Sessions (Ctrl+A), Cancel generation (Ctrl+X), Escape, left/right and Tab, so model selection, native session selection and approval menus remain in OpenCode's own TUI. Ctrl+C quits this legacy application; use Cancel generation to interrupt just the current operation. Normal approvals remain enabled. Noninteractive `--prompt` mode is deliberately unused because this legacy mode auto-approves permissions.

Legacy OpenCode has no verified CLI login, model-list or resume-ID option. Aterus reports these limitations rather than passing unsupported commands. Configure a supported provider inside OpenCode or its own configuration; a working Claude Code login does not establish OpenCode provider access. Aterus neither reads nor copies provider credentials.

**Newer OpenCode CLI:** capability-gated adapters support `--session ID`, `--model provider/model`, JSON session discovery, workspace-exact resume validation, model discovery and an explicit `auth login` terminal. All optional commands depend on installed help. These paths are fixture-tested, not tested against an installed modern OpenCode. No global CLI upgrade/replacement was performed.

Official behavior references: [current CLI](https://opencode.ai/docs/cli/) and [legacy project](https://github.com/opencode-ai/opencode), plus the installed 0.0.55 README/help. Full end-to-end OpenCode provider responses and browser interaction still need verification; see VALIDATION.md.


## Live attachment and cross-platform PWA release

See [CONNECT.md](CONNECT.md) for the complete platform table and setup. **Attach existing** now discovers owned loopback OpenCode servers and connects a second frontend to an exact native session within the authorized root. This does not resume a separate agent. Detach leaves the external server running. Server credentials stay in memory/private pipes, never worker argv. Registering external sources requires the owner; paired devices can view/control attached sessions afterward.

Optional `--external-terminal-view` enables read-only history for eligible macOS Terminal.app foreground agents. These views never inject keys or terminate the external process. Unsupported terminals and unverified process identities fail closed. Generic takeover of arbitrary plain terminals is not implemented.

The PWA includes iPhone/Android/desktop install guidance, offline/reconnect notices and user-triggered updates. Each person runs their own desktop host and pairs their own devices over their trusted HTTPS connection. There is no central multi-user relay. Phone installation and Windows runtime are still unverified. Windows ConPTY code requires Python 3.10+, pywinpty and native agent executables; files are disabled on Windows pending safe reparse-point handling. No shell fallback is used.

For Windows, use Setup-Windows.ps1 and Start-Aterus.cmd. No execution-policy change, global CLI replacement, account change or tunnel activation is performed. The public host package is built by `release.py` using source allowlists, excluding databases, transcripts, environment files and owner credentials.


Public download/connect page: https://aterus-connect.allaboutaryan2.chatgpt.site . It distributes the desktop host and points users to their own HTTPS origin; it does not expose this Mac or host a central relay. See CONNECT.md before pairing a phone.

## Desktop / phone connection milestone (2026-11-02)

Implemented a desktop workspace chooser, per-user Aterus data, opt-in sign-in startup, bundled macOS arm64 connector, explicit temporary HTTPS activation, local QR generation and pending phone pairing requiring desktop verification/approval. Pair requests expire, secrets remain in memory, and tokens are issued once after approval. Connection shutdown clears pairing state. PWA installation guidance and reconnect/update behavior are included.

Validation: 88 Python tests: 87 passed, 1 native Windows skip. Three JavaScript fixture suites passed. Packaged Mac app self-test returned HTTP shell 200, unauthenticated API 401 and local QR output with connector present; no tunnel started. Frozen worker real PTY execution also passed. No physical phone, native Windows GUI, QR scan, actual tunnel route or background notification test has passed. The Apple Silicon app is a development build, without Developer ID signing/notarization. Stable managed relay, signed automatic native updates, arbitrary external-terminal control and background push remain gaps.

## Mobile layout and public hosting work

The source PWA now tracks the visual viewport when the phone keyboard opens, respects screen safe areas, and keeps terminal input and horizontally scrollable 44px keyboard controls reachable. Existing JavaScript fixtures pass with a simulated 360px viewport; physical phone rendering remains unverified. The rebuilt native Mac app self-test again returned shell 200 / unpaired API 401 with no tunnel activation.

The public portal source is prepared for Vercel, with an installable public launcher, original responsive layout and public-only offline caching. A separate Render public release/health service and five-minute UptimeRobot provisioning script are available. These are not a centralized multi-user session relay; users still connect to their own paired HTTPS host. Permanent Vercel/Render deployment and UptimeRobot activation require provider account access.
