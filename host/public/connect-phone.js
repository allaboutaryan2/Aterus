'use strict';
(() => {
  const make = (tag, text, cls) => {const node=document.createElement(tag);if(text)node.textContent=text;if(cls)node.className=cls;return node;};
  const fragment = new URLSearchParams(location.hash.slice(1));
  const claimCode = fragment.get('pair');
  if (claimCode) {
    fragment.delete('pair');
    history.replaceState(null, '', location.pathname + location.search + (fragment.toString() ? '#' + fragment.toString() : ''));
    $('pair-code').value = claimCode;
  }
  const page=$('devices-page');
  const legacy=page.querySelector('.device-panel');
  if(legacy)legacy.hidden=true;
  const panel=make('section','','phone-setup');panel.id='phone-setup';
  const heading=make('h2','Your computer. Now on your phone.');
  const intro=make('p','Create a secure connection, scan the code, then approve your phone here. Your coding agents keep running on this computer.','phone-intro');
  const status=make('p','Checking connection…','phone-status');status.setAttribute('role','status');
  const details=make('p','','phone-note');
  const actions=make('div','','phone-actions');
  const start=make('button','Enable phone access','primary');start.type='button';
  const stop=make('button','Turn off tunnel','secondary');stop.type='button';stop.hidden=true;
  actions.append(start,stop);
  const disclosure=make('p','Enabling phone access starts a Cloudflare HTTPS tunnel with a temporary public address. Access still requires pairing and your approval. Keep this computer awake and online.','phone-note');
  const pairing=make('div','','phone-pairing');
  const create=make('button','Create phone QR code','primary');create.type='button';create.disabled=true;
  const qr=make('img');qr.alt='Scan to request pairing with this computer';qr.width=224;qr.height=224;qr.hidden=true;
  const code=make('output','','phone-code');
  const address=make('a','','phone-address');address.rel='noreferrer';address.hidden=true;
  const copy=make('button','Copy phone link','secondary');copy.type='button';copy.hidden=true;
  const expires=make('p','','phone-note');
  pairing.append(create,qr,code,address,copy,expires);
  const requests=make('div','','phone-requests');
  const errors=make('p','','phone-error');errors.setAttribute('role','alert');
  panel.append(heading,intro,status,details,actions,disclosure,pairing,requests,errors);page.prepend(panel);
  const waiting=make('div','','phone-waiting');waiting.hidden=true;
  waiting.setAttribute('role','status');$('pair-form').append(waiting);
  let connection=null, activeOrigin='', pairingUrl='', expiresAt=0, generation=0, pending=null, ownerPolling=false, ownerEpoch=0, qrGeneration=0;
  const checked=new Set();
  function clearPairing(message='') {
    qrGeneration++;pairingUrl='';expiresAt=0;qr.hidden=true;qr.removeAttribute('src');code.textContent='';address.hidden=true;address.removeAttribute('href');address.textContent='';copy.hidden=true;expires.textContent=message;
  }
  function originFrom(result) {
    const value=result.public_origin || result.connection?.origin || '';
    try {const url=new URL(value);return url.protocol==='https:' && !url.username && !url.password && !url.search && !url.hash && url.pathname==='/' ? url.origin : '';}catch(_){return '';}
  }
  function renderConnection(result) {
    connection=result.connection || {};
    const origin=originFrom(result);
    const ready=!!origin && ['connected','running','ready','configured'].includes(connection.state);
    const nextOrigin=ready?origin:'';
    if(nextOrigin!==activeOrigin)clearPairing(activeOrigin?'Connection changed. Create a new QR code.':'');
    activeOrigin=nextOrigin;
    const running=['connected','running','ready','starting'].includes(connection.state);
    status.textContent=ready?'Phone access is ready':connection.state==='starting'?'Starting your HTTPS connection…':'Phone access is off';
    details.textContent=connection.error || (ready?origin:connection.installed===false?'Cloudflared is not installed on this computer. Install cloudflared, then try again.':'Enable a temporary tunnel or configure an HTTPS origin when starting Aterus.');
    start.disabled=running || connection.installed===false;
    start.textContent=connection.state==='starting'?'Connecting…':'Enable phone access';
    stop.hidden=!running;create.disabled=!ready;
    if(!ready && pairingUrl)clearPairing('Connect again, then create a fresh QR code.');
  }
  async function action(fn) {errors.textContent='';try{await fn();}catch(error){errors.textContent=error.message;}}
  start.onclick=()=>action(async()=>{start.disabled=true;ownerEpoch++;try{renderConnection(await api('/api/connect/start',{}));await refreshOwner();}catch(error){start.disabled=false;throw error;}});
  stop.onclick=()=>action(async()=>{stop.disabled=true;ownerEpoch++;activeOrigin='';create.disabled=true;clearPairing('Tunnel stopped. Previously paired devices stay registered.');try{renderConnection(await api('/api/connect/stop',{}));await refreshOwner();}finally{stop.disabled=false;}});
  create.onclick=()=>action(async()=>{
    if(!activeOrigin)return;
    const origin=activeOrigin, version=qrGeneration;create.disabled=true;
    try {
      const result=await api('/api/pairing',{});
      if(activeOrigin!==origin || version!==qrGeneration)return;
      const url=new URL(result.url);
      if(url.origin!==origin || url.pathname!=='/' || url.search || !url.hash.startsWith('#pair='))throw new Error('Pairing link did not match the active HTTPS connection. Try again.');
      pairingUrl=url.href;expiresAt=Date.now()+Math.max(0,Number(result.expires_in)||0)*1000;
      code.textContent=result.code;
      qr.src='/api/pairing/qr?code='+encodeURIComponent(result.code);qr.hidden=false;
      qr.onerror=()=>{qr.hidden=true;expires.textContent='QR unavailable. Open the phone link below instead.';};
      address.href=pairingUrl;address.textContent=pairingUrl;address.hidden=false;copy.hidden=false;copy.textContent='Copy phone link';
      expires.textContent='Expires in '+Math.ceil((expiresAt-Date.now())/60000)+' minutes. Scan with your phone camera.';
    } finally {create.disabled=!activeOrigin;}
  });
  copy.onclick=()=>action(async()=>{if(!pairingUrl)return;try{await navigator.clipboard.writeText(pairingUrl);copy.textContent='Copied';}catch(_){throw new Error('Copy is unavailable here. Select and copy the phone link shown above.');}});
  function renderRequests(items) {
    requests.replaceChildren();
    const currentIds=new Set(items.map(item=>item.id));for(const id of checked)if(!currentIds.has(id))checked.delete(id);
    if(!items.length)return;
    requests.append(make('h3','Approve your phone'),make('p','Compare the verification code on both screens. Approve only a device you recognize.','phone-note'));
    for(const item of items){
      const row=make('div','','phone-request');
      row.append(make('strong',item.name || 'Unnamed device'),make('p',item.verification,'phone-verification'));
      const label=make('label','','phone-verify');const check=make('input');check.type='checkbox';check.disabled=!item.verification;check.checked=!!item.verification && checked.has(item.id);label.append(check,make('span','The verification matches my phone.'));
      const approve=make('button','Approve device','primary');approve.type='button';approve.disabled=!check.checked;
      check.onchange=()=>{if(check.checked)checked.add(item.id);else checked.delete(item.id);approve.disabled=!check.checked;};
      const reject=make('button','Reject','secondary');reject.type='button';
      approve.onclick=()=>action(async()=>{approve.disabled=true;await api('/api/pair-approve',{id:item.id});checked.delete(item.id);await refreshOwner();});
      reject.onclick=()=>action(async()=>{reject.disabled=true;await api('/api/pair-reject',{id:item.id});checked.delete(item.id);await refreshOwner();});
      const buttons=make('div','','phone-actions');buttons.append(approve,reject);row.append(label,buttons);requests.append(row);
    }
  }
  async function refreshOwner() {
    if(ownerPolling || typeof state==='undefined' || !state?.owner)return;
    ownerPolling=true;const epoch=ownerEpoch;
    try {
      const result=await api('/api/connect');if(epoch!==ownerEpoch)return;renderConnection(result);
      const items=await api('/api/pair-requests');if(epoch!==ownerEpoch)return;renderRequests(Array.isArray(items)?items:items.requests || []);
    }catch(error){if(epoch!==ownerEpoch)return;clearPairing('Connection could not be verified. Retry before creating a new QR code.');activeOrigin='';create.disabled=true;errors.textContent=error.message;}
    finally{ownerPolling=false;}
  }
  const form=$('pair-form'), submit=form.querySelector('button[type="submit"]') || form.querySelector('button');
  const finishPhone=(message)=>{pending=null;generation++;waiting.textContent=message;waiting.hidden=false;if(submit)submit.disabled=false;};
  async function pollPhone(version) {
    if(!pending || version!==generation)return;
    if(Date.now()>=pending.deadline){finishPhone('This request expired. Ask your computer for a new QR code.');return;}
    try {
      const result=await api('/api/pair-status',{id:pending.id,secret:pending.secret});
      if(version!==generation)return;
      if(result.state==='approved'){pending=null;generation++;waiting.textContent='Approved. Opening your computer workspace…';if(submit)submit.disabled=false;try{await boot();}catch(error){$('auth-error').textContent='Paired, but the workspace could not load. Reload to reconnect. '+error.message;}return;}
      if(result.state==='rejected'){finishPhone('The computer rejected this request. Check that you are pairing with the correct Mac.');return;}
      if(result.state==='expired'){finishPhone('This request expired. Ask your computer for a new QR code.');return;}
      waiting.textContent='Waiting for approval on your computer. Compare this verification code: '+pending.verification;
    }catch(_){waiting.textContent='Connection interrupted. Retrying your pairing request… Verification: '+pending.verification;}
    setTimeout(()=>pollPhone(version),1500);
  }
  form.onsubmit=async event=>{
    event.preventDefault();if(pending)return;
    $('auth-error').textContent='';if(submit)submit.disabled=true;
    try {
      const result=await api('/api/pair-request',{code:$('pair-code').value.trim(),name:$('device-name').value.trim()});
      if(!result.id || !result.secret || !result.verification)throw new Error('The computer did not return a valid pairing request. Scan a fresh QR code and try again.');
      pending={id:result.id,secret:result.secret,verification:result.verification,deadline:Date.now()+(Number(result.expires_in)||600)*1000};
      $('pair-code').value='';waiting.hidden=false;waiting.textContent='Waiting for approval on your computer. Compare this verification code: '+pending.verification;
      const version=++generation;setTimeout(()=>pollPhone(version),1500);
    }catch(error){$('auth-error').textContent=error.message;if(submit)submit.disabled=false;}
  };
  $('devices-nav').addEventListener('click',()=>refreshOwner());
  setInterval(()=>{
    const owner=typeof state!=='undefined' && state?.owner;
    panel.hidden=!owner;
    if(owner && !page.classList.contains('hidden'))refreshOwner();
    if(expiresAt && Date.now()>=expiresAt)clearPairing('QR code expired. Create a new one.');
  },3000);
  panel.hidden=!(typeof state!=='undefined' && state?.owner);
})();
