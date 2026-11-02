"""Create one UptimeRobot HTTP monitor, or reuse the exact existing URL.

Uses UptimeRobot's documented v2 API; the key is read from the environment and
is never written to disk or printed. Run only after the backend is deployed.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


def monitor_url(origin):
    url = urllib.parse.urlsplit(origin)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.port not in (None, 443)
            or url.path not in ('', '/') or url.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Supply a public HTTPS backend origin without credentials or paths')
    return origin.rstrip('/') + '/healthz'


def api(method, key, **params):
    data = urllib.parse.urlencode(dict(api_key=key, format='json', **params)).encode()
    req = urllib.request.Request('https://api.uptimerobot.com/v2/' + method,
        data=data, headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read(1024 * 1024))
    if result.get('stat') != 'ok':
        raise RuntimeError('UptimeRobot rejected the request; check key permissions and account limits')
    return result


def ensure_monitor(origin, key, call=api):
    target = monitor_url(origin)
    offset = 0
    while True:
        result = call('getMonitors', key, offset=offset, limit=50)
        monitors = result.get('monitors', [])
        for monitor in monitors:
            if monitor.get('url') == target and int(monitor.get('type', 0)) == 1:
                return {'action':'existing', 'monitor_id':monitor['id'],
                        'status':monitor.get('status'), 'interval_seconds':monitor.get('interval')}
        offset += len(monitors)
        if not monitors or offset >= result.get('pagination', {}).get('total', offset):
            break
    result = call('newMonitor', key, friendly_name='Aterus backend', url=target,
                  type=1, interval=300, ignore_ssl_errors=0)
    return {'action':'created', 'monitor_id':result['monitor']['id'], 'interval_seconds':300}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend_origin')
    args = parser.parse_args()
    key = os.environ.get('UPTIMEROBOT_API_KEY', '')
    if not key:
        sys.exit('UPTIMEROBOT_API_KEY is not configured. Set it privately in your terminal; do not commit it.')
    try:
        print(json.dumps(ensure_monitor(args.backend_origin, key)))
    except Exception:
        sys.exit('Monitor setup failed. Check the HTTPS origin, network access and API key permissions. No secrets logged.')
