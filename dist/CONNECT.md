# Aterus on your computer and phone

Aterus has a desktop host and a browser/PWA client. Each person runs a host on their own computer, uses their own agent accounts, and pairs only their devices. A shared download or public connection guide never grants access to someone else's sessions.

## Platform support

| Role | Platforms | Evidence / limits |
|---|---|---|
| Browser/PWA client | iPhone/iPad Safari, Android Chrome, macOS and Windows browsers | Manifest/icons/install/offline/update behavior implemented and fixture-tested. Physical iPhone/Android/Windows installation unverified. |
| Desktop host | macOS | PTY and socket fixtures pass; Claude/OpenCode response/resume confirmed by user. External OpenCode server attach/detach checked with a real installed CLI/backend. |
| Desktop host | Windows 10/11, Python 3.10+ | Optional pywinpty ConPTY adapter and exclusive data lock implemented. Contract fixtures run on Mac; native Windows test skipped. Requires native executables, not .cmd/.bat/.ps1 agent shims. File uploads/previews/downloads disabled until Windows reparse-point safety is verified. Native descendant-process cleanup remains unverified. |
| Desktop host | Linux | POSIX paths retained; no Linux runtime verification in this build. Terminal.app view is macOS only. |

Phones are clients; they do not run desktop CLI agents. Keep the host computer awake and online.

## Start your own host

macOS:

```sh
cd /path/to/Aterus
python3 aterus.py --workspace /path/to/your/projects --data-dir "$HOME/.aterus"
```

If PATH resolves an older OpenCode, explicitly select the modern executable without replacing global installations:

```sh
python3 aterus.py --workspace /path/to/your/projects --opencode-bin "$HOME/.opencode/bin/opencode"
```

Windows: install Python 3.10+ with the `py` launcher. In a PowerShell window opened in Aterus, run `./Setup-Windows.ps1` under your organization's ordinary script policy. This creates a local virtual environment and installs the pinned Windows dependency. It does not change execution policy. Then run `Start-Aterus.cmd`, or:

```powershell
.\.venv\Scripts\python.exe aterus.py --workspace 'C:\Users\you\Projects' --data-dir "$env:LOCALAPPDATA\Aterus"
```

Run the startup URL on that computer to become owner. The URL contains a one-use credential; keep it private. An absent dependency or unsupported shell shim produces an explicit terminal error. No shell fallback is attempted.

## Attach an already-running OpenCode session

1. Open Aterus on the owner computer and select **Attach existing → OpenCode · live shared server**.
2. Select **Find owned OpenCode servers**, or enter the exact loopback endpoint from the original OpenCode server. Only literal `http://127.0.0.1:PORT` / `http://[::1]:PORT` endpoints with ports 1024–65535 are accepted. The listening process must be a verified current-user OpenCode process.
3. Enter that server's password if it has one. Credentials are used only in memory/private worker pipes and child environment; never placed in process arguments or returned to the browser. Discovery expires in ten minutes.
4. Select **Discover eligible sessions**, choose the exact native session and attach. The original session's workspace must be inside the root authorized at host startup.
5. Aterus starts `opencode attach` as a second terminal frontend to the same server and native ID. This is live attachment, not starting a fresh agent or resuming separate state. Both frontends share the conversation; avoid simultaneous conflicting prompts.
6. **Detach** closes only the Aterus frontend. It does not shut down the external server or end the original agent. Stopping Aterus likewise stops only the frontend it owns.

Modern OpenCode may expose a local listener from its TUI; discovery checks only owned loopback listeners. If the original session exposes no attach endpoint, it cannot be retrofitted by Aterus. For future sessions you can start a loopback `opencode serve` and connect the desktop terminal with `opencode attach` using the documented CLI. Do not stop an active session just to migrate it. Server passwords, if needed, should be configured using OpenCode's own environment/configuration rather than pasted into command arguments.

## Other already-open terminal sessions

On macOS, opt in at host startup with `--external-terminal-view`, then choose **Attach existing → macOS Terminal · read-only live view**. Only owned foreground agent processes inside the permitted workspace can be selected. PID/start-time/tty/executable/workspace are checked before and after each history read. macOS may require Automation permission for the displayed host application (Terminal/Python). No settings are changed automatically.

This reads snapshots of Terminal.app history, not full VT state. It cannot send input, resize or terminate the original session. Plain terminals have no safe generic post-launch takeover protocol. Aterus does not inject keys into arbitrary terminal tabs: a race after agent exit could execute them in the surrounding shell. Node wrappers, VS Code terminals, iTerm and other unsupported surfaces are not silently treated as supported. Use a supported agent server interface for live control; native saved-session resume remains separate.

## Install the PWA on phones and desktops

Aterus includes an install button/help panel. iPhone/iPad: open your own host's trusted HTTPS origin in Safari, pair it, then Share → Add to Home Screen → Add. Android: open it in Chrome and use Install/Add to Home screen. Desktop Chrome/Edge: use the browser's install button when offered. Safari and other browsers show platform guidance instead of a fake install prompt.

`127.0.0.1` on your phone refers to the phone, not the computer. For Wi-Fi/cellular access, supply a trusted HTTPS origin served by a reverse proxy or private network you control, and launch the host with its exact origin:

```sh
python3 aterus.py --workspace /path/to/your/projects --public-url https://your-own-host.example
```

The proxy forwards to the host's `127.0.0.1:4380`, preserving the configured public Host. `Caddyfile.example` is a configuration template, not an activated deployment. Your hostname, trusted certificate, reachability and provider/network choice must be configured by you; no public tunnel or network permission is created automatically. A private VPN/proxy can restrict the address to your devices. Cellular access requires the chosen network path to reach the host while it is awake.

On the owner browser, Devices → Create pairing code; enter that code at the HTTPS origin on each phone/browser. Each code expires after ten minutes and works once. Revoke devices from the owner browser. An unrelated person installing the app gets no access until their own host owner pairs them.

The service worker caches public app assets only. Agent output, file contents and API responses are never cached. Offline mode cannot control agents. Updates require a user click and reload; they do not silently discard current UI input. Background push is still pending.

## Distribution and public availability

The source package can be distributed with its third-party notices. Each recipient needs a desktop host, installed agents, their own accounts, and their own private HTTPS/pairing setup. A public download/connect page can distribute Aterus and link to a user's chosen HTTPS host, but it cannot magically reach a computer's localhost or serve as an authenticated multi-user relay. This build has no central relay/account service or one-click managed tunnel. A public website alone does not make private desktops reachable.

No private transcripts, credentials, owner URLs or session databases belong in a release package. The release builder uses an explicit source allowlist. Public access to a particular desktop must be a separate, intentional deployment choice.
