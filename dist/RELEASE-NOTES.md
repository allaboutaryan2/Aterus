# Aterus development release

This package contains a Python desktop host and the browser/PWA client it serves. It is a development release, not a completed multi-user cloud service.

Implemented: owned PTY terminals; authentication and device pairing/revocation; workspace boundaries; supported native resume; modern OpenCode live server attachment; optional read-only macOS Terminal history; install guidance, offline public-shell assets and intentional update handling; an optional Windows ConPTY host adapter.

Tested on a Mac: automated CLI/version, PTY, auth/origin/file, exact session, live-attach boundary, process identity, lifecycle and release tests; JavaScript protocol/PWA fixtures. Real OpenCode server/session discovery and frontend attachment/detach have been exercised without sending a model prompt; the external server/session survived. Claude and OpenCode prompt/resume flows have also been manually exercised during development.

Not verified: native Windows execution/descendant cleanup; physical iPhone/Android install; cellular/private-network reachability; arbitrary external terminal control. Windows file upload/download/preview is deliberately unavailable pending reparse-point-safe implementation. Background push and a managed relay/tunnel are not implemented.

The host is loopback-only until the operator intentionally configures an HTTPS proxy/private route and its exact origin. The public portal never exposes agent messages or pairs devices for a host.

The archive excludes session databases, logs, account stores, environment files and owner credentials. Third-party xterm.js retains its MIT license and provenance in public/vendor.
