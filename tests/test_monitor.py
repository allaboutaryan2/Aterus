import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).parents[1]/'scripts/setup-monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_existing_monitor_is_not_duplicated(self):
        calls = []
        def api(method, key, **args):
            calls.append(method)
            return {'monitors':[{'id':7,'type':1,'url':'https://aterus.onrender.com/healthz','interval':300,'status':2}]}
        result = monitor.ensure_monitor('https://aterus.onrender.com', 'fixture', api)
        self.assertEqual(result['action'], 'existing')
        self.assertEqual(calls, ['getMonitors'])

    def test_new_monitor_uses_five_minutes_and_verified_tls(self):
        def api(method, key, **args):
            if method == 'getMonitors': return {'monitors':[]}
            self.assertEqual(args['interval'],300)
            self.assertEqual(args['ignore_ssl_errors'],0)
            self.assertEqual(args['url'],'https://aterus.onrender.com/healthz')
            return {'monitor':{'id':8}}
        self.assertEqual(monitor.ensure_monitor('https://aterus.onrender.com', 'fixture',api)['monitor_id'],8)
        for value in ('http://example.com','https://user:secret@example.com','https://example.com/?token=x','https://localhost'):
            with self.assertRaises(ValueError):monitor.monitor_url(value)


if __name__ == '__main__':unittest.main()
