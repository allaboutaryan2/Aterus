# Deploy Aterus: GitHub → Render

The main address is https://aterus.onrender.com. One Free Render service serves the public website, PWA launcher, desktop downloads, release metadata and health endpoint. Vercel is optional. It does **not** host local agents or relay private sessions. Users still pair directly to their own computer's authenticated HTTPS address. A secure multi-user relay remains separate, unfinished work.

## Render website and API

1. Connect the GitHub repository to Render and create a Blueprint from `render.yaml`.
2. The requested service name is `aterus` (free plan). Accept no paid upgrade or purchase. Render chooses the final unique hostname; `aterus.onrender.com` is a preference, not reserved.
3. Verify `https://aterus.onrender.com/` opens the website, `/healthz` returns status `ok`, and `/v1/releases` returns development release metadata. `/api/sessions` must return 404. Check the manifest, service worker, icons and both ZIP downloads.
4. After pushing changes to GitHub, check that Render deploys the latest main commit. For repositories connected by public URL without GitHub app access, use Manual Deploy → Deploy latest commit when automatic deployment is unavailable.

No database, credentials, account tokens or desktop files belong in this public service. Render restarts do not affect agents running on a user's computer.

## Optional Vercel frontend

1. Import this repository in Vercel, project name `aterus` if available. Framework preset: Other. Build: `npm run build`. Output directory: `dist`. No private environment variables are required.
2. After Render returns its real hostname, run `node scripts/connect-backend.cjs https://ACTUAL-HOST.onrender.com`, commit the configuration and deploy. This proxies only public release metadata through `/api/releases`; it does not proxy private hosts.
3. Request the alias `aterus.vercel.app` if available. Hostnames must be confirmed by the deployment result.
4. Verify HTTPS, `/manifest.webmanifest`, `/sw.js`, icons and download links. Never rewrite every path to index.html: that masks missing service-worker files.

## UptimeRobot: 5-minute HTTP check

The monitor **Aterus · health check** has been created for `https://aterus.onrender.com/healthz`, every **5 minutes**, using the existing account email alert contact. Manage it at https://dashboard.uptimerobot.com/monitors/804523163. To reproduce monitoring in another account, use an HTTP/S monitor with certificate validation enabled. Use the UptimeRobot dashboard, or privately set `UPTIMEROBOT_API_KEY` in your terminal and run:

```sh
python3 scripts/setup-monitor.py https://ACTUAL-HOST.onrender.com
```

The script reuses an exact existing HTTP monitor, does not duplicate it, prints no key and makes no purchases. It does not enable a paused existing monitor or change its interval; review the returned status/interval in that case. No monitor has been created until the provider confirms it. Check the account's alert contacts in UptimeRobot to receive downtime alerts.

Incoming HTTP traffic can prevent Render's idle timer from expiring, but monitors are not an availability guarantee. Free service restarts, cold starts, bandwidth/instance-hour limits and network outages still apply. Do not store persistent state on the free service filesystem.

## iPhone / Android PWA checks

- iPhone: open the main Render link in Safari → Share → Add to Home Screen → Add. Open the icon and check standalone launch. For terminal control, also install the **paired host's** PWA on its HTTPS origin.
- Android: Chrome install prompt when offered, or browser menu → Install / Add to Home Screen.
- Check 320px, 390px and landscape layouts, safe areas, keyboard-open controls, and network reconnect on actual hardware. These physical checks remain unverified.
- The offline launcher caches only public static assets. Downloads, query URLs, API responses and external-host traffic are excluded. An update requires the user's Reload action.

## Deployment records

Render Free service: https://dashboard.render.com/web/srv-dbkeli8n74is73f9fmkg

Blueprint: https://dashboard.render.com/blueprint/exs-dbkel9ou01pc73derk0g

Never put credentials, private host files or user sessions in the public service. Publishing a change is complete only after the latest main commit is visibly live on Render.

## Official references

- https://vercel.com/docs/project-configuration/vercel-json
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
- https://uptimerobot.com/api/legacy/
