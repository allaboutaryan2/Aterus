'use strict';
const $ = id => document.getElementById(id);
const readinessText = agent => ({not_installed:'Not installed',unverified:'Authentication unknown',probe_failed:'Status check failed',access_blocked:'Account access blocked',authentication_reported:'Signed in · response unverified',login_required:'Sign in required',provider_unverified:'Provider access unverified'}[agent.readiness] || 'Authentication unknown');
let state, selected, offset = 0, outputTimer, stateTimer, lastStates = {};
let terminal, generation = 0, outputRequest, inputQueue = Promise.resolve(), terminalObserver, resizeTimer;
let polling = false, lastSnapshot = null, liveSource = null;
async function api(path, body) {
  const res = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? {} : {'Content-Type':'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await res.json();
  if (!res.ok) { if (res.status === 401) showAuth(); throw new Error(data.error || 'Request failed'); }
  return data;
}
function showAuth() { $('shell').classList.add('hidden'); $('auth').classList.remove('hidden'); clearInterval(stateTimer); closeTerminal(); }
function toast(text) { $('toast').textContent = text; $('toast').classList.remove('hidden'); setTimeout(() => $('toast').classList.add('hidden'), 4500); }
function element(tag, cls, text) { const el = document.createElement(tag); if (cls) el.className=cls; if (text !== undefined) el.textContent=text; return el; }
function protect(fn, errorId) { return async e => { try { await fn(e); } catch (error) { if (errorId) $(errorId).textContent=error.message; else toast(error.message); } }; }
async function refresh() {
  state = await api('/api/state');
  $('auth').classList.add('hidden'); $('shell').classList.remove('hidden');
  $('device-label').textContent=state.device;
  $('workspace-path').textContent=state.workspace;
  $('active-count').textContent=state.sessions.filter(s => s.state==='running' || s.state==='viewing').length;
  $('agent-count').textContent=state.agents.filter(a => a.installed).length;
  $('session-count').textContent=state.sessions.length;
  $('agent-list').replaceChildren(...state.agents.map(a => {
    const row=element('div','agent-item'+(a.installed?'':' offline'));
    const info=element('span','agent-info'); info.append(element('span','',a.name),element('small','',a.installed ? readinessText(a) : 'Not installed')); row.append(element('span','agent-avatar',a.name[0]),info,element('span','dot')); 
    row.title=a.installed ? [a.version || a.executable, readinessText(a)].join(' · ') : a.executable+' is not installed'; return row;
  }));
  const picker=$('agent-select'), previous=picker.value;
  picker.replaceChildren(...state.agents.map(a => { const opt=element('option','',a.name+(a.installed?'':' · not installed')); opt.value=a.id; opt.disabled=!a.installed; return opt; }));
  if (state.agents.some(a => a.id===previous && a.installed)) picker.value=previous;
  else picker.value=state.agents.find(a=>a.installed)?.id || '';
  $('new-session').disabled=!picker.value; $('empty-new').disabled=!picker.value;
  $('sessions').replaceChildren(...state.sessions.map(session => {
    if (lastStates[session.id]==='running' && session.state!=='running') toast(session.title+' · '+session.state);
    lastStates[session.id]=session.state;
    const agent=state.agents.find(a=>a.id===session.agent), card=element('button','session-card');
    const top=element('div','card-top'), identity=element('div','card-agent');
    identity.append(element('span','agent-avatar',agent.name[0]),element('span','',agent.name));
    top.append(identity,element('span','status '+session.state,session.state));
    const foot=element('div','card-footer'); foot.append(element('span','',new Date(session.created*1000).toLocaleDateString(undefined,{month:'short',day:'numeric'})),element('span','','Open terminal ↗'));
    card.append(top,element('h3','',session.title),element('span','card-path',session.cwd),foot);
    card.onclick=protect(()=>openTerminal(session)); return card;
  }));
  $('empty').classList.toggle('hidden',state.sessions.length>0);
  $('create-code').disabled=!state.owner;
  $('attach-existing').disabled=!state.owner;
}
function agentHealth() {
  const agent=state.agents.find(a=>a.id===$('agent-select').value);
  $('agent-health').textContent=agent ? [agent.version || agent.executable, readinessText(agent)].join(' · ') : '';
  const fresh=element('option','','Start a new session'); fresh.value=''; $('native-session').replaceChildren(fresh);
  $('resume').value=''; $('native-status').textContent='Refresh to discover native sessions in this workspace.'; $('available-models').replaceChildren(); $('model-status').textContent='';
  configureAgentControls();
}
async function configureAgentControls() {
  const agent=$('agent-select').value;
  $('model').disabled=false; $('resume').disabled=false; $('login-agent').disabled=true;
  try {
    const controls=await api('/api/agent-controls?agent='+encodeURIComponent(agent));
    if($('agent-select').value!==agent) return;
    $('login-agent').disabled=!controls.login;
    if(agent==='opencode') {
      const legacy=controls.variant!=='modern';
      $('model').disabled=legacy; $('resume').disabled=legacy;
      if(legacy){$('model').value='';$('resume').value='';}
      $('agent-health').textContent += ' · '+(controls.notice || 'OpenCode native sessions and provider/model IDs supported');
    }
  } catch(error) { if($('agent-select').value===agent) $('agent-health').textContent=error.message; }
}
function promptInput(text) {
  if(selected?.agent==='opencode' && selected.controls?.variant==='unknown') throw new Error('Use the OpenCode terminal directly for this unrecognized version');
  return text+(selected?.controls?.submit || '\r');
}
function openCreate() { $('cwd').value=state.workspace; $('create-error').textContent=''; agentHealth(); $('create-dialog').showModal(); }
async function discoverSessions() {
  const agent=$('agent-select').value, cwd=$('cwd').value;
  $('discover-sessions').disabled=true;
  try {
    const result=await api('/api/native-sessions?agent='+encodeURIComponent(agent)+'&cwd='+encodeURIComponent(cwd));
    if ($('agent-select').value!==agent || $('cwd').value!==cwd) return;
    const fresh=element('option','','Start a new session'); fresh.value='';
    $('native-session').replaceChildren(fresh,...result.sessions.map(s=>{const option=element('option','',s.title || s.id);option.value=s.id;return option;}));
    $('native-status').textContent=result.error || (result.sessions.length+' native sessions found. Resuming creates a new managed terminal; it does not attach an external terminal.');
  } finally { $('discover-sessions').disabled=false; }
}
$('agent-select').onchange=()=>{$('model').value='';agentHealth();};
$('cwd').onchange=agentHealth;
$('discover-sessions').onclick=protect(discoverSessions,'native-status');
$('native-session').onchange=()=>{$('resume').value=$('native-session').value;};
async function launch(kind) {
  $('create-error').textContent=''; $('launch-button').disabled=true; $('login-agent').disabled=true;
  try {
    const session=await api('/api/sessions',{agent:$('agent-select').value,cwd:$('cwd').value,title:$('session-title').value,model:$('model').value,resume:$('resume').value,kind});
    $('create-dialog').close(); await refresh(); await openTerminal(session);
  } finally { $('launch-button').disabled=false; configureAgentControls(); }
}
function closeTerminal() {
  clearInterval(outputTimer); clearTimeout(resizeTimer); generation++;
  outputRequest?.abort(); outputRequest=null; polling=false; selected=null;
  terminalObserver?.disconnect(); terminalObserver=null;
  terminal?.dispose(); terminal=null;
  if ($('terminal-dialog').open) $('terminal-dialog').close();
}
function fitTerminal() {
  if (!terminal || !selected || $('output').classList.contains('hidden')) return;
  const screen=terminal.element?.querySelector('.xterm-screen');
  if (!screen || !screen.clientWidth || !screen.clientHeight) return;
  const container=$('output'), css=getComputedStyle(container);
  const width=container.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight)-16;
  const height=container.clientHeight-parseFloat(css.paddingTop)-parseFloat(css.paddingBottom);
  const cols=Math.max(30,Math.min(300,Math.floor(width/(screen.clientWidth/terminal.cols))));
  const rows=Math.max(10,Math.min(150,Math.floor(height/(screen.clientHeight/terminal.rows))));
  if(cols!==terminal.cols || rows!==terminal.rows) terminal.resize(cols,rows);
  const sid=selected.id;
  clearTimeout(resizeTimer);
  resizeTimer=setTimeout(()=>{if(selected?.id===sid && selected.state==='running') api('/api/resize',{id:sid,cols,rows}).catch(e=>{$('terminal-error').textContent=e.message;});},150);
}
async function pollOutput() {
  if (!selected || polling) return;
  polling=true;
  const sid=selected.id, current=generation, view=terminal, controller=new AbortController();
  outputRequest=controller;
  try {
    const response=await fetch('/api/output?id='+encodeURIComponent(sid)+'&offset='+offset,{signal:controller.signal});
    const result=await response.json();
    if (!response.ok) {if(response.status===401) showAuth(); throw new Error(result.error || 'Output disconnected');}
    if (generation!==current || selected?.id!==sid) return;
    const binary=atob(result.data), bytes=new Uint8Array(binary.length);
    for(let i=0;i<binary.length;i++) bytes[i]=binary.charCodeAt(i);
    if(result.snapshot && lastSnapshot!==result.revision){view.reset();lastSnapshot=result.revision;}
    if(bytes.length && (!result.snapshot || view._aterusSnapshot!==result.revision)){await new Promise(resolve=>view.write(bytes,resolve));if(result.snapshot)view._aterusSnapshot=result.revision;}
    if(generation!==current) return;
    offset=result.offset; selected.state=result.state;
    $('terminal-error').textContent=result.hint || '';
    $('terminal-status').textContent=result.state;
    $('terminal-input').disabled=result.state!=='running';
    $('send-input').disabled=result.state!=='running';
    $('stop-session').disabled=!['running','viewing'].includes(result.state);
    document.querySelectorAll('[data-key]').forEach(b=>b.disabled=result.state!=='running');
    view.options.disableStdin=result.state!=='running';
  } catch(error) {
    if(error.name!=='AbortError' && generation===current) $('terminal-error').textContent=error.message+' · reconnecting…';
  } finally { if(generation===current) {polling=false; outputRequest=null;} }
}
async function openTerminal(session) {
  closeTerminal(); selected={...session}; offset=0; lastSnapshot=null;
  const current=generation;
  const controls=await api('/api/agent-controls?agent='+encodeURIComponent(session.agent));
  if(generation!==current || selected?.id!==session.id) return;
  selected.controls=controls;
  $('opencode-keys').classList.toggle('hidden',controls.variant!=='legacy-go');
  $('terminal-help').textContent=session.attachment_kind==='terminal-view' ? 'Read-only Terminal snapshot. Input is unavailable; Detach leaves the original agent running.' : session.attachment_kind==='opencode-live' ? 'Live shared OpenCode session. Detach closes this frontend; the original session remains running.' : controls.notice || 'Interactive terminal · tap for keyboard input, or use the prompt field. Normal agent approvals remain enabled.';
  $('stop-session').textContent=session.attachment_kind ? 'Detach' : 'End session';
  $('output').replaceChildren(); $('terminal-error').textContent='';
  $('terminal-title').textContent=session.title; $('terminal-agent').textContent=state.agents.find(a=>a.id===session.agent).name.toUpperCase();
  $('terminal-dialog').showModal(); showTab('output');
  if(typeof Terminal==='undefined') throw new Error('Terminal library could not load. Reload the app.');
  terminal=new Terminal({cols:100,rows:30,scrollback:10000,fontSize:13,fontFamily:'Menlo, monospace',lineHeight:1.2,convertEol:false,disableStdin:session.state!=='running',theme:{background:'#111b16',foreground:'#cfd9bf',cursor:'#d7f477'}});
  terminal.open($('output'));
  terminal.onData(text=>send(text).catch(error=>{$('terminal-error').textContent=error.message;}));
  terminalObserver=new ResizeObserver(fitTerminal);terminalObserver.observe($('output'));
  fitTerminal(); await pollOutput();
  outputTimer=setInterval(pollOutput,500);
}
function showTab(tab) { $('output').classList.toggle('hidden',tab!=='output'); $('file-list').classList.toggle('hidden',tab!=='files'); $('file-tools').classList.toggle('hidden',tab!=='files'); $('show-output').classList.toggle('active',tab==='output'); $('show-files').classList.toggle('active',tab==='files'); if(tab==='output') requestAnimationFrame(fitTerminal); }
function send(text) {
  const sid=selected?.id, current=generation;
  if(!sid || selected.state!=='running') return Promise.reject(new Error('This terminal is no longer running'));
  const task=inputQueue.catch(()=>{}).then(()=>{
    if(generation!==current || selected?.id!==sid) throw new Error('Terminal changed; input discarded');
    return api('/api/input',{id:sid,text});
  });
  inputQueue=task; return task;
}
$('pair-form').onsubmit=protect(async e=>{e.preventDefault(); await api('/api/pair',{code:$('pair-code').value,name:$('device-name').value}); await boot();},'auth-error');
$('new-session').onclick=openCreate; $('empty-new').onclick=openCreate;
$('close-create').onclick=()=>$('create-dialog').close();
$('create-form').onsubmit=protect(async e=>{e.preventDefault();await launch('chat');},'create-error');
$('login-agent').onclick=protect(()=>launch('login'),'create-error');
$('close-terminal').onclick=()=>$('terminal-dialog').close();
$('terminal-dialog').addEventListener('close',()=>{if(selected && !$('terminal-dialog').open) closeTerminal();});
$('input-form').onsubmit=protect(async e=>{e.preventDefault();const field=$('terminal-input');await send(promptInput(field.value));field.value='';},'terminal-error');
document.querySelectorAll('[data-key]').forEach(b=>b.onclick=protect(()=>send(JSON.parse('"'+b.dataset.key+'"')),'terminal-error'));
$('stop-session').onclick=protect(async()=>{await api('/api/stop',{id:selected.id});toast(selected.attachment_kind ? 'Detaching frontend…' : 'Stopping terminal…');},'terminal-error');
$('show-output').onclick=()=>showTab('output');
async function loadFiles() {
  const sid=selected.id;
  showTab('files'); $('file-preview').classList.add('hidden');
  const files=await api('/api/files?id='+sid);
  if(selected?.id!==sid) return;
  $('file-list').replaceChildren(...files.map(f=>{
    const row=element('div','project-file');
    const preview=element('button','link-button',f.path+' · '+Math.ceil(f.size/1024)+' KB');
    preview.onclick=protect(async()=>{const result=await api('/api/preview?id='+sid+'&path='+encodeURIComponent(f.path));if(selected?.id!==sid)return;$('file-preview').textContent=result.text+(result.truncated?'\n[Preview truncated]':'');$('file-preview').classList.remove('hidden');},'terminal-error');
    const download=element('a','','Download');download.href='/api/file?id='+sid+'&path='+encodeURIComponent(f.path);download.download=f.path.split('/').pop();
    row.append(preview,download);return row;
  }));
  if(!files.length) $('file-list').textContent='No visible project files.';
}
$('show-files').onclick=protect(loadFiles,'terminal-error');
$('upload-file').onchange=protect(async()=>{
  const file=$('upload-file').files[0], sid=selected?.id;
  if(!file || !sid) return;
  if(file.size>4*1024*1024) throw new Error('Upload limit is 4 MiB');
  $('upload-file').disabled=true;$('upload-status').textContent='Uploading…';
  try{
    const bytes=new Uint8Array(await file.arrayBuffer());
    let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
    const result=await api('/api/upload',{id:sid,name:file.name,data:btoa(binary)});
    $('upload-status').textContent='Uploaded '+result.path;
    if(selected?.id===sid) await loadFiles();
  }finally{$('upload-file').disabled=false;$('upload-file').value='';}
},'upload-status');

async function loadDevices(){const list=$('devices-list');list.replaceChildren();if(!state.owner){list.textContent='Device management is available on the owner Mac.';return;}const devices=await api('/api/devices');devices.forEach(d=>{const row=element('div','device-row');row.append(element('span','',d.name+(d.owner?' · owner':'')));const revoke=element('button','secondary','Revoke');revoke.disabled=d.owner;revoke.onclick=protect(async()=>{await api('/api/revoke',{hash:d.hash});await loadDevices();});row.append(revoke);list.append(row);});}
$('devices-nav').onclick=protect(async()=>{$('workspace-page').classList.add('hidden');$('devices-page').classList.remove('hidden');$('workspace-nav').classList.remove('active');$('devices-nav').classList.add('active');$('page-name').textContent='Devices';await loadDevices();});
$('workspace-nav').onclick=()=>{$('devices-page').classList.add('hidden');$('workspace-page').classList.remove('hidden');$('devices-nav').classList.remove('active');$('workspace-nav').classList.add('active');$('page-name').textContent='Workspace';};
$('logout').onclick=protect(async()=>{await api('/api/logout',{});showAuth();});
async function boot(){clearInterval(stateTimer);const token=new URLSearchParams(location.hash.slice(1)).get('owner');if(token){history.replaceState(null,'',location.pathname);await api('/api/bootstrap',{token});}await refresh();stateTimer=setInterval(protect(refresh),4000);}
boot().catch(error=>{showAuth();$('auth-error').textContent=error.message;});

$('discover-models').onclick=protect(async()=>{
  const agent=$('agent-select').value, cwd=$('cwd').value;
  $('discover-models').disabled=true;
  try {
    const result=await api('/api/models?agent='+encodeURIComponent(agent)+'&cwd='+encodeURIComponent(cwd));
    if($('agent-select').value!==agent || $('cwd').value!==cwd)return;
    $('available-models').replaceChildren(...(result.items || []).map(item=>{const option=element('option','',typeof item==='string'?item:item.name || item.id);option.value=typeof item==='string'?item:item.id;return option;}));
    $('model-status').textContent=result.error || (result.supported ? result.items.length+' models discovered' : 'Automatic discovery is unavailable for this installed CLI. Enter a model ID supported by your account.');
  } finally {$('discover-models').disabled=false;}
},'model-status');
$('handoff-open').onclick=()=>{
  $('handoff-agent').replaceChildren(...state.agents.filter(a=>a.installed).map(a=>{const option=element('option','',a.name);option.value=a.id;return option;}));
  $('handoff-error').textContent='';$('handoff-context').value='';$('handoff-dialog').showModal();
};
$('handoff-close').onclick=()=>$('handoff-dialog').close();
$('handoff-form').onsubmit=protect(async event=>{
  event.preventDefault();const sid=selected?.id;if(!sid)throw new Error('Open a source session first');
  $('handoff-submit').disabled=true;
  try {
    const session=await api('/api/handoff',{id:sid,agent:$('handoff-agent').value,context:$('handoff-context').value});
    $('handoff-dialog').close();await refresh();await openTerminal(session);
    $('terminal-input').value=session.handoff_prompt || '';
    toast('Review the handoff prompt and send when the target agent is ready.');
  } finally {$('handoff-submit').disabled=false;}
},'handoff-error');



$('attach-existing').onclick=()=>{liveSource=null;$('attach-session').replaceChildren();$('attach-submit').disabled=true;$('attach-password').value='';$('attach-status').textContent='Only sessions within the authorized workspace root are eligible.';$('attach-dialog').showModal();};
$('attach-close').onclick=()=>{$('attach-password').value='';$('attach-dialog').close();};
$('attach-dialog').addEventListener('close',()=>{$('attach-password').value='';liveSource=null;});
$('attach-kind').onchange=()=>{const view=$('attach-kind').value==='terminal-view';$('attach-server-fields').classList.toggle('hidden',view);$('attach-explanation').textContent=view ? 'Optional macOS Terminal.app history view. Start the host with --external-terminal-view; owner and foreground-process checks apply. This view cannot send keys or stop the original process.' : 'A second frontend for the same running OpenCode server/session. No shell injection. Detach leaves the original session running.';liveSource=null;$('attach-session').replaceChildren();$('attach-submit').disabled=true;};
$('attach-origins').onchange=()=>{if($('attach-origins').value)$('attach-origin').value=$('attach-origins').value;};
$('attach-scan').onclick=protect(async()=>{const result=await api('/api/external/candidates');$('attach-origins').replaceChildren(...result.origins.map(origin=>{const option=element('option','',origin);option.value=origin;return option;}));if(result.origins.length)$('attach-origin').value=result.origins[0];$('attach-status').textContent=result.origins.length+' owned loopback servers found. If none appear, the original OpenCode may not expose a local server.';},'attach-status');
$('attach-discover').onclick=protect(async()=>{
  $('attach-discover').disabled=true;$('attach-submit').disabled=true;
  try {
    const view=$('attach-kind').value==='terminal-view';
    const result=view ? await api('/api/external/terminals') : await api('/api/external/discover',{origin:$('attach-origin').value,password:$('attach-password').value,username:$('attach-username').value});
    $('attach-password').value='';liveSource=result.source || null;
    const rows=view ? result.items : result.sessions;
    $('attach-session').replaceChildren(...rows.map(row=>{const option=element('option','',(row.title || row.agent || row.id)+' · '+row.cwd);option.value=row.id;return option;}));
    $('attach-submit').disabled=!rows.length;$('attach-status').textContent=rows.length+' eligible sessions found. '+(view ? 'Read-only; no terminal injection.' : 'Live attachment uses the same backend and native session, without resuming a separate conversation.');
  } finally {$('attach-discover').disabled=false;}
},'attach-status');
$('attach-form').onsubmit=protect(async event=>{event.preventDefault();$('attach-submit').disabled=true;try{const view=$('attach-kind').value==='terminal-view';const session=await api(view ? '/api/external/view' : '/api/external/attach',view ? {reference:$('attach-session').value} : {source:liveSource,native:$('attach-session').value});$('attach-dialog').close();await refresh();await openTerminal(session);}finally{$('attach-submit').disabled=false;}},'attach-status');
