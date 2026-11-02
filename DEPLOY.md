# Deploy Aterus: GitHub → Vercel + Render

The Vercel app is the public PWA/download/connect launcher. The Render service is a public release API and health endpoint. It does **not** host local agents or relay private sessions. Users still pair directly to their own computer's authenticated HTTPS address. A secure multi-user relay remains separate, unfinished work.

## Render backend

1. Connect the GitHub repository to Render and create a Blueprint from `render.yaml`.
2. The requested service name is `aterus` (free plan). Accept no paid upgrade or purchase. Render chooses the final unique hostname; `aterus.onrender.com` is a preference, not reserved.
3. Verify `https://ACTUAL-HOST.onrender.com/healthz` returns status `ok`, and `/v1/releases` returns development release metadata. `/api/sessions` must return 404.

No database, credentials, account tokens or desktop files belong in this public service. Render restarts do not affect agents running on a user's computer.

## Vercel frontend

1. Import this repository in Vercel, project name `aterus` if available. Framework preset: Other. Build: `npm run build`. Output directory: `dist`. No private environment variables are required.
2. After Render returns its real hostname, run `node scripts/connect-backend.cjs https://ACTUAL-HOST.onrender.com`, commit the configuration and deploy. This proxies only public release metadata through `/api/releases`; it does not proxy private hosts.
3. Request the alias `aterus.vercel.app` if available. Hostnames must be confirmed by the deployment result.
4. Verify HTTPS, `/manifest.webmanifest`, `/sw.js`, icons and download links. Never rewrite every path to index.html: that masks missing service-worker files.

## UptimeRobot: 5-minute HTTP check

After the backend is live, create an HTTP monitor named **Aterus backend**, URL `https://ACTUAL-HOST.onrender.com/healthz`, interval **5 minutes**, certificate validation enabled. Use the UptimeRobot dashboard, or privately set `UPTIMEROBOT_API_KEY` in your terminal and run:

```sh
python3 scripts/setup-monitor.py https://ACTUAL-HOST.onrender.com
```

The script reuses an exact existing HTTP monitor, does not duplicate it, prints no key and makes no purchases. It does not enable a paused existing monitor or change its interval; review the returned status/interval in that case. No monitor has been created until the provider confirms it. Check the account's alert contacts in UptimeRobot to receive downtime alerts.

Incoming HTTP traffic can prevent Render's idle timer from expiring, but monitors are not an availability guarantee. Free service restarts, cold starts, bandwidth/instance-hour limits and network outages still apply. Do not store persistent state on the free service filesystem.

## iPhone / Android PWA checks

- iPhone: open the Vercel site in Safari → Share → Add to Home Screen → Add. Open the icon and check standalone launch. For terminal control, also install the **paired host's** PWA on its HTTPS origin.
- Android: Chrome install prompt when offered, or browser menu → Install / Add to Home Screen.
- Check 320px, 390px and landscape layouts, safe areas, keyboard-open controls, and network reconnect on actual hardware. These physical checks remain unverified.
- The offline launcher caches only public static assets. Downloads, query URLs, API responses and external-host traffic are excluded. An update requires the user's Reload action.

## Current deployment gates

GitHub authentication is available as `allaboutaryan2`. Vercel CLI is logged out; no Render or UptimeRobot API keys are configured in this session, and no authorized browser automation tool is connected. A provider sign-in or privately configured provider credentials is required to create permanent named deployments and the monitor. Never paste keys into a public issue, source file or website form.

## Official references

- https://vercel.com/docs/project-configuration/vercel-json
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
- https://uptimerobot.com/api/legacy/
