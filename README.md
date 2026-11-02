# Aterus

Your coding agents, within reach. Original public website and installable PWA launcher, with a dependency-free Node public release/health service for Render.

- Frontend: responsive static HTML/CSS/JavaScript, Vercel-ready. iPhone Safari installation guidance, Android install prompt, offline public shell and intentional updates.
- Backend: `/healthz` and `/v1/releases`. No credentials, private projects, user sessions or arbitrary outbound proxy endpoints.
- Desktop host: included source and Apple Silicon development downloads. Each person runs agents on their own computer and explicitly approves phone pairing.

**This is a development build. A central multi-user session relay, background push and native Windows validation remain unfinished.** Installing this public PWA installs a setup/connection launcher. Terminal control lives at the user's paired host origin.

## Verify

```sh
npm test
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

`npm start` serves the public API on `PORT` (default 10000). For local frontend preview: `python3 -m http.server 8080 --directory dist`. Production uses HTTPS for service workers and installation.

The complete desktop host implementation and its tests are in `host/`. To verify the host: `cd host`, then `python3 -m unittest discover -s tests -q` and `node tests/test_browser_glue.cjs`.

See [DEPLOY.md](DEPLOY.md) for GitHub, Vercel, Render and UptimeRobot setup. Preferred names `aterus.vercel.app` and `aterus.onrender.com` require provider availability confirmation. No monitor or permanent Vercel/Render deployment is claimed without provider evidence.

The desktop downloads contain third-party notices. `dist/releases.json` records archive SHA-256 checksums; this is an integrity record, not a code-signing certificate. The Mac app has no Apple Developer ID notarization.

Security candidate: see `host/VALIDATION.md`. The draft patch is not a verified security release; isolated Docker regressions are blocked by local Docker API permissions.
