# Aterus validation — 1 November 2026

## Current security verification: passing isolated Docker run

The saved user-run Docker output for source revision 122da46442325f060c69b550d35b86568ebc5537 reports 98 tests in 13.761 seconds, OK (skipped=1): 97 passed, including all eight security regressions, with only native Windows ConPTY execution skipped. Earlier failed fixture runs below are historical. The run used an unprivileged container, no network, read-only root filesystem, no host mounts, dropped capabilities and bounded resources.

The three low-severity findings are addressed by the tested source changes: bounded HTTP admission/deadlines and early authentication; current-workspace authorization plus pinned directory descriptors; and valid-code pairing recovery without weakening owner approval. The focused original/alternate triggers and normal-host controls in this suite pass. This does not establish physical phone, native Windows or full native-binary/minified-terminal audit coverage.

## Automated results

Command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`

**51 tests discovered; 50 passed; 1 skipped; no failures in the latest run.** The skipped check is native Windows ConPTY, which cannot run on this Mac. The real loopback socket check now passes in this execution context. Earlier runs skipped it due to PermissionError. Additional HTTP handler boundary tests still use in-memory byte streams; those are not browser tests.

Passing coverage:

- Installed-help/version-dependent CLI arguments; unsafe option-like IDs; unknown/blocked authentication; bounded probe duration/output; no account identity in health responses.
- Native Kiro session identity matching, duplicate/unknown-schema rejection and model discovery fixtures. These fixture schemas are not yet confirmed against an authenticated Kiro installation.
- Real local PTYs: interactive input/output and no shell fallback; normal exit; resize; Ctrl+C; stop; stdin EOF and SIGTERM with resistant agents; cleanup when descendants retain the terminal.
- Hashed device credentials; single-use and expired pairing; rate limit; 30-day idle expiry; revocation; local bootstrap; host/origin/fetch-site/content-type/transfer-encoding/duplicate-header checks.
- Launch-root workspace boundary; regular-file access; hidden file/traversal/symlink rejection; exclusive-create uploads; symlink upload collision; single-instance locking and restart history recovery.
- Public asset routes including xterm/PWA icons. Explicit handoff produces a reviewable control-character-free draft and does not inject input into a starting CLI.
- launchd plist scope/arguments, invalid configuration rejection, no owner credential logging.

`node tests/test_browser_glue.cjs`: **passed**. Node VM fixtures check serialized input, rejection of stale input after changing sessions, raw VT bytes delivered unchanged to a renderer stub, offsets committed after renderer callback, and reconnect offset preservation. This does not exercise xterm rendering, a real DOM or networking.

`node --check public/app.js` and `node --check public/sw.js`: **passed**.

## Actual CLI evidence

- Kiro CLI **2.36.0** is installed. Its installed help verifies `chat`, `--model`, `--resume-id`, session/model listing and JSON format flags. `whoami --format json` reports no account. Session/model queries fail with an OS permission error while loading login state. No real Kiro response or approval has been verified.
- Claude CLI is installed. The earlier restricted probe reported signed out, but subsequent user-run screenshots confirm a real prompt, response, remembered context and follow-up through Aterus using the existing Mac login.
- Codex CLI is installed; `login status` reports signed in. No actual model exchange was run.
- Legacy Go OpenCode executable is installed; no newer HTTP/API assumptions were made.
- Gemini and Pi are not installed.

Probes intentionally suppress identity/credential output. No login, account-permission change, public tunnel, external deployment or background service was activated.

## Blocked/unverified gates

| Gate | Result | Smallest next action |
|---|---|---|
| Live HTTP/browser flow | Socket transport now passes; user screenshots confirm Claude browser exchange. Automated rendering remains unverified | Restart the server to load changes and open the private startup URL |
| Signed-in Kiro exchange and tool approval | No account; login/session storage access blocked here | Run `kiro-cli login` on Mac, then follow README Kiro milestone |
| Actual session/model JSON schema | Blocked by same account/session access | Run native discovery after login; adapt parser only to observed schema if it differs |
| Desktop/mobile rendering and xterm TUI | Not verified | Exercise live app in desktop browser and mobile viewport; verify cursor/redraw/input/resize/reconnect |
| iPhone Wi-Fi/cellular and revocation | Not verified; no authorized HTTPS origin configured | Configure user-controlled HTTPS proxy, pass exact `--public-url`, pair phone |
| Home Screen PWA | Metadata and worker implemented; install not verified | Add HTTPS app to Home Screen on iPhone |
| Background completion/failure/approval push | Not implemented | Implement Web Push subscriptions/delivery/preferences after structured turn/approval states |
| Startup activation | Configuration generated in fixtures only | Follow lifecycle.py instructions after owner pairing, with manual service stopped |

The first requested end-to-end milestone is **not yet achieved**. Full Shed parity is **not achieved**. PARITY.md retains every audited missing capability, including routing, queues, structured conversations, external and Codex Desktop sessions, inter-session exchanges, phone sharing/Shortcuts, QR, push, idle cleanup and full lifecycle tooling.

## Known implementation ceilings

xterm.js is the locally available 6.1.0-beta.304 distribution, with its MIT license preserved; browser compatibility remains unverified. Agent process-group cleanup cannot control intentionally detached groups. Raw logs are unbounded and survive shutdown; live processes do not. Background health probes report auth state rather than actual API availability. Handoffs transfer a user-reviewed text excerpt and workspace, not native memory, tool state or permissions. Approval/turn completion is not inferred from terminal silence. No idle timeout kills potentially busy agents.


## OpenCode implementation and runtime evidence

Installed executable: `/opt/homebrew/bin/opencode`, Homebrew Go version **0.0.55**. Its actual root help and packaged README were inspected, alongside official current CLI documentation. It has no `--model`, `--session`, `auth login`, JSON session-list or model-list commands. Its interactive editor uses Ctrl+S to submit; Ctrl+O opens models, Ctrl+A sessions and Ctrl+X cancels generation. Aterus now detects this interface, submits prompts accordingly, exposes the controls and disables unsupported model/resume/login fields. Normal TUI approvals are retained. Legacy noninteractive prompt mode is unused because its documentation says it auto-approves permissions.

Newer-CLI adapters are capability gated and fixture tested: model/session flags, explicit provider login, model roster filtering, exact-workspace native discovery, resume identity/duplicate validation and malformed-output handling. A modern OpenCode executable is not installed here; these fixtures do not prove modern runtime compatibility. Auth/readiness remains provider-unverified instead of borrowing Claude account status.

Actual PTY smoke checks started the installed binary in disposable clean workspaces. Initially it emitted terminal negotiation and stayed running; after scripted replies to foreground/background-color queries it exited **1** with **`Error: agent coder not found`**. No prompt or provider API request was submitted. This is a real startup failure in the clean test workspace, not a successful OpenCode exchange. Aterus now recognizes that exact error and displays static guidance to check OpenCode's provider and coder-model configuration without returning credential/config contents. No global CLI upgrade, account configuration or permission change was performed.

The missing native coder/provider setup is the remaining blocker for a real legacy OpenCode response. Configure that OpenCode installation on the Mac using its own documented configuration, then restart Aterus and test OpenCode in a dedicated workspace. The existing Claude Code subscription/login is not evidence that the legacy OpenCode provider is configured.

Five OpenCode fixture tests cover legacy/newer variants, unsupported flags, login behavior, native workspace boundaries and duplicate identities, model parsing and unknown authentication. Browser glue also verifies Ctrl+S for legacy versus Enter for newer OpenCode/Claude. Authenticated handler tests exercise the controls endpoint. The previous stopped-vs-failed status correction and disabled Send regression now pass too.

User screenshot evidence confirms Claude conversational continuity. A browser refresh itself, manual approvals, physical phone access and OS process-tree cleanup are not established by screenshots. The stop screenshot showed a nonzero intentional exit incorrectly labelled failed; the patched backend now records stopping/stopped and rejects input while stopping. Genuine unrequested nonzero exits remain failed; historical records are preserved.


## Live external attachment and cross-platform PWA — 1 November 2026

### Implemented and fixture-tested

- Owned loopback OpenCode listener discovery (macOS/lsof; Windows/CIM SID checks), literal-IP URL validation, no redirects/DNS/proxies, bounded JSON responses, server health/schema and exact native workspace/ID checks. Only owner devices can register or attach sources. Credentials are excluded from returned data, process arguments and release packages. Worker startup configuration now travels on its stdin pipe.
- A real `opencode attach` frontend to the same external backend/native session. Detach is distinct from stopping an owned agent; it never sends a shutdown request to the external server.
- Optional read-only Terminal.app history with foreground/user/tty/start/cwd identity checks before and after each read. No shell input, resize or process termination is implemented for these views. Sandbox process inspection prevents a real Terminal.app test here; Automation permissions were not changed.
- PWA install guidance for iPhone/iPad, Android and desktop, deferred install prompts, standalone detection, offline/reconnect status and intentional service-worker updates. Public shell caching excludes all API/private terminal/project data.
- Optional Windows ConPTY adapter, native-executable-only launch, bounded Unicode input/output, resize/shutdown, private configuration pipe, Windows lock and setup/launcher scripts. Ten contract fixtures pass. Actual Windows execution, process-tree cleanup, installer and platform-specific locking/listener enumeration require Windows. Windows project-file APIs deliberately fail closed pending verified reparse-point handling; .cmd/.bat/.ps1 agent shims are rejected.
- Source allowlist release packaging excludes data directories, credentials, environment files, logs and hidden assets. Public portal navigation rejects owner tokens, passwords, paths and non-HTTPS destinations.

### Real installed OpenCode server test

The modern binary at `~/.opencode/bin/opencode` was started as a separate, password-protected loopback server in an isolated disposable XDG workspace. A native empty conversation was created using its supported API; no model prompt or tool execution was requested. Aterus discovered the exact session, launched the supported attach CLI in a real PTY, answered terminal color negotiations and captured **4,034 output bytes**. The attached frontend was running before detach and recorded **detached** afterward. The original server remained alive and the exact native session remained present after detachment. The test's owned server and frontend were then cleaned up. This proves native server/session attachment and frontend detachment, not a model exchange or real browser rendering of that attached session.

The old PATH-resolved Go binary remains available; no global executable was replaced. `--opencode-bin` selects an explicit modern executable. Aterus keeps ordinary trust/approval settings.

### Latest checks

`python3 -m unittest discover -s tests -v`: **50 passed / 1 native Windows skip**. A PTY fixture initially timed out because select() was polling the descriptor while Python buffered a later output event; that fixture now uses unbuffered pipes. Its focused rerun and the complete 51-test rerun pass. No runtime signal handling was changed to mask the failure.

`node tests/test_browser_glue.cjs`, `node tests/test_pwa.cjs`, portal navigation/link fixtures and JavaScript syntax checks: **passed**. These do not constitute a rendered DOM or physical-device test.

### Public distribution

The download/connect portal is published at https://aterus-connect.allaboutaryan2.chatgpt.site . Sites reports successful production deployment and public access. It contains only a source-allowlisted desktop host package, public setup notes and a host-origin navigation form. It neither runs desktop agents nor proxies user messages. Each recipient must run their own desktop host, configure a reachable trusted HTTPS route and pair their own devices. No desktop listener was exposed publicly, no tunnel/provider/account permission was activated, and no owner credential or session database was published.

### Remaining gates

Physical iPhone/Android installation, Windows native execution, public-HTTPS pairing on an actual device, Wi-Fi/cellular reachability, shared-session approvals/model work and arbitrary non-server terminal control remain unverified/unsupported as documented in CONNECT.md. Background push and a managed multi-user relay remain unimplemented. A public download page is not a central agent-hosting service.

Public-page inspection through the web-reader tool was unavailable after deployment. Publication/public audience is confirmed by the Sites deployment result; rendered browser QA of the new portal remains unverified.

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

### Second user-run Docker result

The saved security-test-results.txt reports 98 tests: 96 passed, 1 errored, and 1 native Windows skip. All eight security regression tests passed. The remaining stop-session error came from another temporary executable fixture exiting before the test could stop it. This fixture now launches through the existing executable Python interpreter and waits for its explicit ready output before testing stop behavior. Container restrictions and application behavior remain unchanged. The corrected complete suite still needs a passing rerun before merge/release.
