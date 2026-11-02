import unittest
from unittest.mock import Mock
from xml.etree import ElementTree
from pairing import PairingGate,pairing_url,qr_svg


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.time=1000;self.issue=Mock(return_value='device-token');self.gate=PairingGate(self.issue,clock=lambda:self.time)

    def test_never_grants_token_until_owner_approval_and_secret_proof(self):
        code=self.gate.create()['code'];pending=self.gate.request(code,'My phone')
        self.assertEqual(self.gate.status(pending['id'],pending['secret']),({'state':'pending'},None))
        self.issue.assert_not_called()
        self.assertNotIn('secret',str(self.gate.requests()))
        with self.assertRaises(ValueError):self.gate.status(pending['id'],'wrong-secret')
        self.gate.decide(pending['id'],True)
        self.assertEqual(self.gate.status(pending['id'],pending['secret']),({'state':'approved'},'device-token'))
        self.issue.assert_called_once_with('My phone')
        self.assertEqual(self.gate.status(pending['id'],pending['secret'])[0]['state'],'expired')
        with self.assertRaises(ValueError):self.gate.request(code,'Reuse')

    def test_expiration_rejection_and_connection_reset(self):
        pending=self.gate.request(self.gate.create()['code'],'Phone')
        self.gate.decide(pending['id'],False)
        self.assertEqual(self.gate.status(pending['id'],pending['secret'])[0]['state'],'rejected')
        pending=self.gate.request(self.gate.create()['code'],'Phone')
        self.time+=301
        self.assertEqual(self.gate.status(pending['id'],pending['secret'])[0]['state'],'expired')
        self.issue.assert_not_called()
        pending=self.gate.request(self.gate.create()['code'],'Phone')
        self.gate.decide(pending['id'],True);self.gate.reset()
        self.assertEqual(self.gate.status(pending['id'],pending['secret'])[0]['state'],'rejected')
        self.issue.assert_not_called()

    def test_rate_limit_code_and_payload_boundary(self):
        self.gate.create()
        for _ in range(20):
            with self.assertRaises(ValueError):self.gate.request('INVALID','Phone')
        with self.assertRaisesRegex(ValueError,'Too many'):self.gate.request('INVALID','Phone')
        self.time+=601
        pending=self.gate.request(self.gate.create()['code'],'x'*1000)
        self.assertEqual(len(self.gate.requests()[0]['name']),80)
        self.assertEqual(len(pending['verification']),6)

    def test_real_qr_svg_has_quiet_zone_no_embedded_secret_text_or_scripts(self):
        url=pairing_url('https://test.example','ABCDEF123456')
        data=qr_svg(url);root=ElementTree.fromstring(data)
        self.assertTrue(root.attrib['viewBox'].startswith('0 0 '))
        self.assertNotIn(url.encode(),data)
        self.assertNotIn(b'<script',data)
        self.assertGreater(len(root.find('{http://www.w3.org/2000/svg}path').attrib['d']),1000)
        for origin in ('http://test.example','https://user:pass@test.example','https://test.example/path','https://test.example/?token=x'):
            with self.assertRaises(ValueError):pairing_url(origin,'ABCDEF123456')
