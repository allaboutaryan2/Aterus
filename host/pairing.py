"""Expiring, approval-gated device pairing; no device token exists before approval."""
import collections
import hashlib
import hmac
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from vendor.qrcodegen import QrCode


class PairingGate:
    def __init__(self, issue_device, codes=None, *, clock=time.time):
        self.issue_device = issue_device
        self.codes = codes if codes is not None else {}
        self.clock = clock
        self.lock = threading.RLock()
        self.pending = {}
        self.attempts = collections.deque()

    def reset(self):
        with self.lock:
            self.codes.clear()
            for record in self.pending.values():
                if record['state'] in ('pending','approved'):
                    record['state']='rejected'

    def create(self):
        with self.lock:
            code=secrets.token_hex(6).upper()
            self.codes.clear();self.codes[code]=self.clock()+600
            return {'code':code,'expires_in':600}

    def request(self, code, name):
        with self.lock:
            now=self.clock()
            while self.attempts and self.attempts[0] < now-600:self.attempts.popleft()
            if len(self.attempts)>=20:raise ValueError('Too many pairing attempts. Try again in ten minutes.')
            self.attempts.append(now)
            expiry=self.codes.pop(str(code).strip().upper(),0)
            if expiry<=now:raise ValueError('Pairing code is invalid or expired. Generate a new code on the computer.')
            self.pending={key:r for key,r in self.pending.items() if r['expires_at']>now}
            if len(self.pending)>=32:raise ValueError('Too many pending devices. Reject unused requests on the computer.')
            identity,secret=secrets.token_hex(16),secrets.token_urlsafe(32)
            verification=str(secrets.randbelow(1000000)).zfill(6)
            self.pending[identity]={'id':identity,'name':str(name).strip()[:80] or 'Phone',
                'hash':hashlib.sha256(secret.encode()).hexdigest(),'verification':verification,
                'expires_at':min(expiry,now+300),'state':'pending'}
            return {'id':identity,'secret':secret,'verification':verification,'expires_in':int(min(expiry-now,300))}

    def requests(self):
        with self.lock:
            now=self.clock()
            return [{key:r[key] for key in ('id','name','verification','expires_at')} for r in self.pending.values() if r['state']=='pending' and r['expires_at']>now]

    def decide(self, identity, approve):
        with self.lock:
            record=self.pending.get(identity)
            if not record or record['expires_at']<=self.clock():raise ValueError('Pair request expired; request a new pairing code')
            if record['state'] not in ('pending','approved'):raise ValueError('This request is no longer awaiting a decision')
            record['state']='approved' if approve else 'rejected'
            return {'state':record['state']}

    def status(self, identity, secret):
        with self.lock:
            record=self.pending.get(identity)
            digest=hashlib.sha256(str(secret).encode()).hexdigest()
            if not record or not hmac.compare_digest(record['hash'],digest):raise ValueError('Pairing request could not be verified')
            if record['expires_at']<=self.clock():return {'state':'expired'},None
            state=record['state']
            if state=='approved':
                token=self.issue_device(record['name'])
                record['state']='claimed'
                return {'state':'approved'},token
            if state=='claimed':return {'state':'expired'},None
            return {'state':state},None


def pairing_url(origin, code):
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('A trusted HTTPS connection is required before QR pairing')
    if not re.fullmatch(r'[A-F0-9]{12}',code):raise ValueError('Invalid pairing code')
    return origin.rstrip('/')+'/#pair='+code


def qr_svg(url):
    # QR encoding uses unmodified, MIT-licensed Project Nayuki v1.8.0.
    qr=QrCode.encode_text(url,QrCode.Ecc.MEDIUM)
    size=qr.get_size();border=4
    path=' '.join(f'M{x+border},{y+border}h1v1h-1z' for y in range(size) for x in range(size) if qr.get_module(x,y))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size+border*2} {size+border*2}" role="img" aria-label="Pair this phone" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="white"/><path d="{path}" fill="black"/></svg>').encode()
