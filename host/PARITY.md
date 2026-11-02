# Aterus parity and verification ledger

Source baseline: local `/Users/apple/Desktop/shed-main` (package version 0.2.0), inspected directly. Paths below are relative to that reference. This ledger records behavior, not permission to reuse source or assets. Shed is MIT-licensed; Aterus is independently implemented. No Shed source or assets were imported for this audit.

Statuses describe the inspected initial Aterus build unless a later implementation entry explicitly supersedes them. “Present” is source evidence, not a real-agent or phone pass. Fixture checks, CLI probes, browser checks and physical-phone checks must be reported separately.

## Core sessions and control

| Capability | Reference evidence | Aterus baseline / remaining work |
|---|---|---|
| Five original agents plus Kiro | `server/models.js:harnesses`, `server/index.js:startTask` | Six launch adapters present; Kiro added. Runtime/version compatibility needs verification. |
| Installed vs authenticated/readiness | `server/health.js:probe`, 30-second refresh | PATH detection only; add bounded version/auth probes with unknown/blocked states. |
| Explicit agent sign-in | `server/index.js:loginMatch`, `public/app.js` login drawer | Kiro/Claude/Codex login PTYs present; verify commands and account status. |
| Native session discovery, project/title/model metadata | `server/sessions.js:discoverSessions`, per-agent record parsers | Missing. Must retain native identity and original workspace; incomplete/corrupt live files must not break scans. |
| Native transcript reading | `server/sessions.js:sessionMessages` | Missing structured conversation/history; Aterus has raw owned-terminal logs only. |
| New session, selected project, new workspace | `server/index.js:startTask`, `autoWorkspace`; `public/app.js:renderProjects` | Arbitrary existing cwd accepted; no owner-managed workspace boundary or create-workspace UI. |
| Exact native resume | `server/index.js:startTask`, `deliverToTerminal` | Kiro/Claude/Codex arguments present; others missing. Validate installed versions and disallow arbitrary option-like identities. |
| Resume sessions that lack project metadata | `server/index.js:startTask` Gemini safeguard | Must refuse unsafe/ambiguous resume; currently accepts caller-provided IDs and cwd independently. |
| Attach/continue external Terminal sessions | `server/terminal.js:agentInForeground`, `typeIntoTerminalAsync`, `readTerminalAsync` | Missing. Foreground ownership checks required before any injection. |
| Codex Desktop queue and interrupt | `server/index.js:queueCodexTask`, `server/codex-app.js:interruptCodexThread` | Missing. Reference uses a local app-server control socket and transcript queue; interface support must be verified independently before adoption. |
| Prompt/follow-up delivery | `server/index.js:deliverToTerminal`, `startTask` | Direct PTY input present for owned sessions; native identity must be captured for fresh sessions. |
| Live terminal output and controls | `server/terminal.js:readTerminalAsync`; `server/menu.js` | PTY bytes present, browser strips ANSI rather than emulates VT. Proven VT renderer required for full-screen agents; preserve split UTF-8 and resize. Reference itself reads Terminal.app text, not a full browser VT emulator. |
| Approval/menu options and keyboard input | `server/menu.js:parseMenu`, `keysToChoose`; terminal routes | Raw keys present; no structured menu/approval detection. Normal trust/approval stays enabled. |
| Permission mode display/change | `server/live.js:footerMode`; `server/index.js:permMatch`; `test/permissions.test.js` | Missing structured mode display and safe mode controls. Do not implement reference skip-permission switches: user explicitly requires ordinary approvals. |
| Stop, interrupt, process ownership, shell guard | `server/terminal.js:stopAgent`, `agentInForeground`, `closeTerminalTab`; `test/stop.test.js` | Direct exec prevents shell fallback. Test descendant cleanup, process-group ownership, escalation and exited-input rejection. |
| Working/idle/asking/history states | `server/live.js:liveSessionStates`, transcript/terminal parsers | Only running/exited/failed/interrupted lifecycle states; no turn-level completion or pending approval state. |
| Persistent sessions/tasks and restart recovery | `server/index.js:loadTasks`, `saveTasks`; `server/exchanges.js` | SQLite sessions and logs present; old running rows become interrupted. Reconnect/restart/single-instance ownership needs verification. |
| Task queue, progress, cancellation, pending prompts | `server/index.js:refreshQueuedTasks`, task routes, `public/app.js:pendingMessages` | Missing task/turn layer; running process is not equivalent to a working turn. |

## Routing, models and collaboration

| Capability | Reference evidence | Aterus baseline / remaining work |
|---|---|---|
| Manual model choice | `server/models.js:validateModelConfig`, `server/index.js:startTask` | Free-text field present. Version-specific support and safe argument validation needed. |
| Model discovery/defaults and editable enabled roster | `server/models.js:codexDefaults`, model GET/POST routes | Missing. Reference uses Codex cache/config and curated/manual lists, not authoritative live discovery for all agents. Distinguish available, configured and verified models. |
| Automatic agent/session route, route preview | `server/router.js:rankSessions`; `server/laya.js:decideRoute`; `/api/route` | Missing; implement explicit route choice and reason, safe fallback when optional router unavailable. |
| Automatic model and follow-up routing | `server/laya.js:decideModel`, `decideFollowup`; `/api/followup-preview` | Missing; optional local Laya capability/status/probe and constrained roster decisions. |
| Automatic project inference/new-folder creation | `server/index.js:autoWorkspace`, `routeInput` | Missing; explicit workspace authorization required before creating/using inferred paths. |
| Cross-agent handoff and context limits | `server/index.js:handoffPrompt`, `uncommittedChanges`, `returnToOrigin` | Missing; transfer bounded recent conversation/project state with explicit new-session semantics, original session association and optional return. |
| Human-directed session introductions | `/api/exchanges/introduce`, `server/exchanges.js:introductionPrompt` | Missing. |
| Agent-to-agent sessions/ask/reply interface | `bin/shed`; `/api/agent/*`; caller process ancestry | Missing Aterus-specific local client and authenticated caller-session identification. |
| Exchange tracking, reply waiting, failure recovery | `server/exchanges.js:exchangeStore`; `test/exchanges.test.js` | Missing persistent exchange/task relation and bounded replies. |
| Loop/flood prevention | `server/exchanges.js:refusal`, `MAX_DEPTH`, `HOURLY_LIMIT` | Missing: self, duplicate, reverse waiting, depth (3), per-source hourly cap (20), live-target checks. Equivalent safeguards required, not necessarily identical limits. |

## Files, sharing and phone access

| Capability | Reference evidence | Aterus baseline / remaining work |
|---|---|---|
| Bounded project file listing and search | `server/files.js:listArtifacts`; `public/app.js:renderFileRows` | Bounded newest-file listing present, limited to 60 displayed. Search/pagination/type filtering missing. |
| Safe downloads and previews | `server/files.js:resolveInside`, `sendFile`; file routes | Binary downloads present (20 MiB). Safe image/audio/video/PDF/text previews and range requests missing. Never execute workspace HTML in app origin. |
| Upload/attach files to prompts | `server/uploads.js:uploadStore`, `attachmentNote`; `/api/uploads`; `test/uploads.test.js` | Missing streaming size-limited uploads, private staging, expiry, collision handling, workspace placement and prompt attachment context. Reference permits 100 MiB. |
| Share-sheet URL/text/note ingestion | `/api/share`; `server/share.js:fetchShared`, `sharePrompt`; `test/share.test.js` | Missing. Includes metadata preview/media retrieval via optional yt-dlp and selected browser cookies. Treat fetched content as untrusted and avoid indiscriminate credential access. |
| iPhone Shortcut install / QR / manual integration | `server/share.js:signedShortcut`; share shortcut/install/manual-key routes | Missing Aterus-branded shortcut generation and user-authorized installation. |
| Revocable limited share keys | `server/index.js:shareKeyFor`, share settings routes | Missing separate share credential scope, usage tracking and revocation. |
| Device authentication/pair/revoke/logout/expiry | `server/index.js` auth/device routes, `deviceFor` | One-use owner token, hashed device cookies, pairing code, owner revoke and idle expiry present. Review bootstrap race, request limits and expiration tests. |
| Local approval of pending devices / revoke others | `server/index.js` devices approve/reject/revoke-others routes | Missing pending device approval queue and bulk revocation; current explicit owner-issued code is a different pairing design. |
| Password setup / login fallback | `/api/password/setup`, `/api/auth`, scrypt and rate limiting | Missing; pairing is current access method. Retain as explicit parity gap even if pairing remains preferred. |
| Host/origin/request boundary | `server/index.js:checkOrigin`, `isDirectLocal`, `isAuthorized` | Host/origin allowlists present. Workspace authorization, duplicate headers, content types, bootstrap proxy identity and owner-only sensitive actions require tests. |
| QR pairing/link display | `/api/connect`, qrcode dependency; `public/app.js:loadConnect` | Text code present; QR missing. Keep secrets out of logs/screenshots. |
| HTTPS quick tunnel and lifecycle | `server/tunnel.js` | Only explicit HTTPS reverse-proxy origin configuration present; no tunnel process management. Publishing requires user authorization. |
| Permanent hostname/relay activation | `server/pro.js`, `test/relay.test.js` | Missing. Implement user-owned provider configuration; do not reuse Shed service identifiers or purchase/activate accounts implicitly. |
| Installable PWA / icons / home screen | `public/manifest.webmanifest`, `public/sw.js`, app registration | Missing original manifest/icons/service worker and iPhone install verification. |
| Background Web Push | `server/notify.js`, `public/sw.js`; push routes | In-page exit notices only. Missing VAPID/subscriptions/delivery/expired-subscription cleanup and physical iPhone check. |
| Completion/failure/approval notifications and preferences | `server/index.js:watchAndNotify`, `notifyPrefs`; push prefs routes | Must distinguish turn complete from process exit, deduplicate notices, preserve notification deep links and user preference controls. |

## Operations and interface

| Capability | Reference evidence | Aterus baseline / remaining work |
|---|---|---|
| Configurable idle cleanup, never kill busy sessions | `server/idle.js`, `server/index.js:autoCloseIdle`; `test/idle.test.js` | Missing; cannot safely infer idle from absent terminal output alone. |
| Installer/dependency checks, startup service, update/uninstall | `site/install.sh` | Manual `.command` launcher only. Need Aterus-specific install paths/service identifiers, reversible launchd configuration and non-destructive uninstall/update. |
| Responsive phone/desktop UI | `public/app.js`, `public/styles.css`, `public/theme.css` | Original responsive UI present; browser/mobile visual and interaction checks pending. |
| Session search/filter/live prioritization | `public/app.js:render`, session search/filter handlers | Missing search/filter/pagination and approval/working priority. |
| Structured conversation/Markdown/task activity | `public/markdown.js`, `public/app.js:renderTask`, session drawer | Raw terminal stream only; no structured chat renderer, task activity log or handoff/exchange affordances. |
| Realtime refresh and reconnection | `/api/events` SSE; `public/app.js:connectEvents` plus polling fallback | Output polling present; reconnect, byte offset integrity and failure UX need verification. |
| Deep links and notification reopening | `public/app.js:openFromUrl`, `public/sw.js:notificationclick` | Missing stable session/task links and mobile navigation restoration. |
| Service health/settings and optional-router diagnostics | `/api/settings`, `/api/laya/test`, harness-health routes | Minimal state endpoint; no operational settings/diagnostic UI. |

## Verification gates

1. **Automated fixtures:** CLI construction/version variants; PTY I/O, resize, UTF-8, exit, interrupt, descendant cleanup and post-exit input; native identity fixtures; auth/pair/expiry/revoke/origin/request/workspace/file tests. Fixture success is not a real-agent success.
2. **Browser:** authenticated start/resume, input/output, approval keyboard, reconnect and desktop/mobile viewport checks. Record browser and exact result.
3. **Real Kiro milestone:** open app → choose Kiro/workspace → start or exact native resume → actual signed-in response → actual tool approval → continue → safe stop. Record authentication and any sandbox/account restriction without credentials.
4. **Physical iPhone:** trusted HTTPS pairing over Wi-Fi and cellular, revoke/expiry, Home Screen install, background completion/failure/approval push and deep-link reopen. Requires the user's device and authorized network setup; do not claim a viewport emulation verifies it.
5. **Operations:** restart recovery, idle cleanup without busy-process termination, install/startup/update/uninstall and provider/tunnel error handling.

Initial reported validation: six fixture tests passed; one local-socket test skipped; JS syntax passed. Browser rendering, actual AI response and iPhone/network/push remained unverified. Later run evidence must supersede this paragraph explicitly.

## Implementation update — 1 November 2026

This section supersedes the baseline column only for the capabilities listed here. Every other baseline gap remains open.

| Capability | Current implementation evidence | Verification limit |
|---|---|---|
| Installation/auth/version health | `agents.py:agent_status`, background cached probes in `aterus.py` | Actual Kiro account null; discovery blocked. Claude signed out; Codex signed in, response unverified. |
| Version-aware launch/model/resume | `agents.py:command`, `validate_resume` | Optional flags checked against installed help; Kiro exact identity verified with fixtures only. |
| Kiro native sessions/model list | `agents.py:native_sessions`, `available_models`; discovery controls in `public/app.js` | Workspace-scoped CLI commands; schema/identity fixtures pass. Actual JSON schema blocked by account access. Other agents remain gaps. |
| Full VT renderer/input/reconnect/resize | `public/vendor/xterm.js`, `public/app.js` | Real dependency with MIT notice; Node glue fixtures pass. Browser rendering/TUI/mobile not tested. |
| Owned process lifecycle | `pty_worker.py`, `tests/test_pty_lifecycle.py` | Real PTY resize/Ctrl+C/exit/EOF/escalation/descendant fixtures pass. Deliberately detached process groups excluded. |
| Workspace/files/request boundaries | `aterus.py:workspace_path`, `open_project_file`, `upload`, `dispatch` | Launch-root restriction, pinned descriptors, no symlink traversal, duplicate headers/content type/origin checks fixture-tested. |
| File upload/text preview | `aterus.py` upload/preview routes; `public/app.js` file controls | 4 MiB exclusive-create uploads, 256 KiB text preview. No large streaming uploads, media previews or staging expiry yet. |
| Explicit handoff | `/api/handoff`; UI handoff dialog | New target plus reviewable prompt draft, 6,000 transcript bytes maximum; no native state transfer or automatic execution. Real-agent handoff not tested. Return-to-origin/routing remain missing. |
| Restart/data ownership | `Hub` single-instance lock, collector join, SQLite recovery | History restart/expired device fixture tests pass. Live PTYs stop on shutdown. |
| PWA | `public/manifest.webmanifest`, icons, `sw.js` | Public shell only; no API cache. Syntax checked; physical iPhone install unverified. Push absent. |
| Startup preparation | `lifecycle.py`, `tests/test_lifecycle.py` | Tested plist generation only; no service activated. Full installer/updater/uninstaller absent. |

Current validation is recorded in `VALIDATION.md`. Full Shed parity and the real Kiro/approval/phone milestone remain incomplete.


### OpenCode update — 1 November 2026

- `agents.py:controls` identifies installed legacy Go vs newer CLI capabilities. Legacy prompt submission uses Ctrl+S; model/session/cancel controls use Ctrl+O/Ctrl+A/Ctrl+X. The browser exposes these and standard approval-navigation keys without bypassing permissions.
- Newer CLI adapters support help-gated model/resume arguments, explicit provider login, model listing and JSON native discovery. Exact workspace identity and unique native session IDs are required to resume. Unknown/ambiguous output fails closed; no cross-workspace sessions appear in the picker.
- Legacy 0.0.55 lacks CLI native discovery/model selection/login. These remain accessible through its own TUI; unsupported controls are disabled/explained. No global upgrade was performed. Provider auth remains unverified rather than inferred from installation or Claude login.
- Actual CLI help/version inspected; compatibility and browser-submit fixtures pass. Actual provider response and browser approval remain open. See VALIDATION.md for the real-startup result.
- Previous stop-status correction is now verified by automated tests: deliberate stop yields stopped, unexpected nonzero exit yields failed, input is blocked while stopping, and Send disables after exit. Old historical failures remain unchanged because no stop intent was stored.


### Live attach and PWA update — 1 November 2026

| Capability | Implemented now | Still open |
|---|---|---|
| Existing live OpenCode server/session | Owned loopback listener discovery, health identity, workspace-checked native IDs, password-in-memory, supported attach frontend, detach preserving backend | Existing TUI must expose a server; endpoints without ownership/schema proof rejected. Real model/approval during shared attachment remains unverified. |
| Existing Mac Terminal | Explicit opt-in read-only history with before/after PID/start/uid/tty/cwd checks | No input, full VT state, iTerm/VS Code support, generic post-launch takeover or Codex Desktop control. |
| PWA installation | iPhone/iPad guidance, Android/desktop deferred prompt, standalone detection, offline status and intentional updates | Native device installation/background notifications unverified. |
| Windows desktop host | Optional pywinpty ConPTY worker, same private pipe protocol, native-executable checks, setup/launcher, Windows data lock and listener-owner adapter | Native Windows execution/cleanup unverified; shell shims rejected; Windows files disabled pending safe implementation. |
| Public distribution | Source-only desktop host allowlist builder and public connection/download portal; each person pairs their own host | No central relay, accounts, managed tunnel or automatic trusted HTTPS setup. Public portal alone cannot reach a computer's localhost. |

Full parity remains incomplete. CONNECT.md and VALIDATION.md distinguish implementation, fixtures, native backend evidence and device/runtime blockers.

## Desktop / phone connection milestone (2026-11-02)

Implemented a desktop workspace chooser, per-user Aterus data, opt-in sign-in startup, bundled macOS arm64 connector, explicit temporary HTTPS activation, local QR generation and pending phone pairing requiring desktop verification/approval. Pair requests expire, secrets remain in memory, and tokens are issued once after approval. Connection shutdown clears pairing state. PWA installation guidance and reconnect/update behavior are included.

Validation: 88 Python tests: 87 passed, 1 native Windows skip. Three JavaScript fixture suites passed. Packaged Mac app self-test returned HTTP shell 200, unauthenticated API 401 and local QR output with connector present; no tunnel started. Frozen worker real PTY execution also passed. No physical phone, native Windows GUI, QR scan, actual tunnel route or background notification test has passed. The Apple Silicon app is a development build, without Developer ID signing/notarization. Stable managed relay, signed automatic native updates, arbitrary external-terminal control and background push remain gaps.

## Mobile layout and public hosting work

The source PWA now tracks the visual viewport when the phone keyboard opens, respects screen safe areas, and keeps terminal input and horizontally scrollable 44px keyboard controls reachable. Existing JavaScript fixtures pass with a simulated 360px viewport; physical phone rendering remains unverified. The rebuilt native Mac app self-test again returned shell 200 / unpaired API 401 with no tunnel activation.

The public portal source is prepared for Vercel, with an installable public launcher, original responsive layout and public-only offline caching. A separate Render public release/health service and five-minute UptimeRobot provisioning script are available. These are not a centralized multi-user session relay; users still connect to their own paired HTTPS host. Permanent Vercel/Render deployment and UptimeRobot activation require provider account access.

## Security patch candidate — verification blocked

Eight independent static security reviews reported three low-severity issues: unbounded HTTP worker/body resources before pairing; persisted sessions exposing files outside a later-selected workspace; and invalid pairing attempts exhausting a shared quota for valid code holders. The review explicitly leaves native binary internals and the full minified terminal implementation partially unaudited.

This branch contains a candidate patch: authenticate protected POSTs before body reads; reject non-API POSTs without body reads; cap global/per-connection-client workers with an absolute header/body deadline; serialize large upload parsing; reauthorize saved sessions against the active workspace; pin project directory descriptors for listing, preview, download and upload; and let valid active pairing codes proceed despite invalid-attempt throttling. Session history stays stored and becomes accessible when its workspace is selected again.

Python AST parsing, JavaScript syntax and the unchanged public portal/backend/monitor fixtures pass. Host security regressions have NOT run: Docker API access failed with permission denied at unix:///Users/apple/.docker/run/docker.sock. Applicable AGENTS.md requires vulnerability reproductions in isolated Docker. The security outcome is BLOCKED pending dynamic verification, not verified fixed. Existing published download binaries are not replaced by this candidate.

Run from the repository root with authorized Docker access:

```sh
docker build -f host/Dockerfile.security -t aterus-security-check .
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=256m --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 512m --cpus 2 aterus-security-check
```

The image copies only host source, runs without host mounts or credentials, and uses an unprivileged container user. Tests cover valid pairing after invalid traffic, aliases, single-use codes, workspace changes, descriptor-based directory-swap rejection, early body rejection, upload-slot release, worker admission, trickled header/body deadlines and normal requests after cleanup. These tests remain unexecuted in this session.

### First user-run Docker result and fixture correction

The supplied container output ran 98 tests: 91 passed, 5 failed, 1 errored, and the native Windows test was skipped. Seven of the eight security regressions passed; the upload-budget case errored because its assertion expected dispatch() to return a tuple on the exception path, although the handler sends its error response and returns None. That assertion now checks the captured reply status.

The five failures involved executable test fixtures in /tmp, consistent with a noexec temporary mount. Fixtures now use the container's existing executable Python interpreter; executable-discovery fixtures reference that interpreter, with a separate non-executable-file negative control. The real helper lifecycle fixture still launches and stops an owned child, but reads the fixture script as interpreter data. Application executable checks and container mount/capability/network restrictions are not changed.

These harness corrections have passed syntax and whitespace checks only. The corrected 98-test suite has not yet been rerun successfully. Docker API access is still denied to the assistant session. Run `bash scripts/check-security.sh` from the repository root; it preserves the existing isolated container restrictions, records output to the ignored security-test-results.txt file, and preserves the Docker test exit status. Do not merge or replace the published build until the corrected run passes.
