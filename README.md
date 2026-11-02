# Aterus

Your coding agents, within reach. Public website, installable PWA launcher, downloads and release/health API served together by a dependency-free Node service on Render.

- Frontend: responsive static HTML/CSS/JavaScript at `/`. iPhone Safari installation guidance, Android install prompt, offline public shell and intentional updates.
- Backend: `/healthz` and `/v1/releases`. No credentials, private projects, user sessions or arbitrary outbound proxy endpoints.
- Desktop host: included source and Apple Silicon development downloads. Each person runs agents on their own computer and explicitly approves phone pairing.

**This is a development build. A central multi-user session relay, background push and native Windows validation remain unfinished.** Installing this public PWA installs a setup/connection launcher. Terminal control lives at the user's paired host origin.

## Verify

```sh
npm test
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

`npm start` serves the website, downloads and public API on `PORT` (default 10000). Production uses HTTPS for service workers and installation.

The complete desktop host implementation and its tests are in `host/`. To verify the host: `cd host`, then `python3 -m unittest discover -s tests -q` and `node tests/test_browser_glue.cjs`.

See [DEPLOY.md](DEPLOY.md) for GitHub, Render and UptimeRobot setup. The main public URL is https://aterus.onrender.com. Vercel hosting is optional.

The desktop downloads contain third-party notices. `dist/releases.json` records archive SHA-256 checksums; this is an integrity record, not a code-signing certificate. The Mac app has no Apple Developer ID notarization.

Security regression verification: the isolated Docker suite passed 97 tests, including all eight security regressions; native Windows execution remains skipped. See `host/VALIDATION.md` for scope, historical runs and remaining limitations.
