'use strict';
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const EVENT_WINDOW = 2000;
function storedToken() { try { return sessionStorage.getItem('sentinel-token') || ''; } catch { return ''; } }
const state = {token:storedToken(), connected:false, status:{}, events:[], cursor:0, eventsLoaded:false, dropped:0, sessions:[], missions:[], checkpoints:[], policies:[], query:'', session:'', busy:false, pendingRefresh:false, needsRender:false, generation:0, drafts:{}, evaluation:null, noticeKind:'', replay:{events:[], cursor:0, loaded:false, busy:false, more:true, dropped:0, generation:0}};
const templates=Object.create(null);
const views={overview:['COMMAND CENTER','Operational overview','A clear view of the autonomy you authorize.'],guard:['POLICY ENFORCEMENT','Guard','Inspect decisions before an operation reaches the runtime.'],watch:['RUNTIME OBSERVABILITY','Watch','Actual runtime events, in the order Sentinel recorded them.'],replay:['FORENSIC INVESTIGATION','Replay','Reconstruct execution history. Investigation never re-executes a tool.'],missions:['BOUNDED AUTHORITY','Mission Control','Give autonomous work an explicit scope and lifecycle.'],recovery:['CONTROLLED RESTORATION','Recovery','Restore supported file changes with integrity and conflict checks.'],mesh:['SESSION REGISTRY','Mesh','One operational picture across recorded Hermes sessions.'],settings:['LOCAL CONFIGURATION','Settings','Connect this browser to your local Sentinel service.']};
function route(){const key=location.hash.slice(1);return Object.hasOwn(views,key)?key:'overview'}
function notice(message, kind='operation') { $('#notice').textContent=message; state.noticeKind=kind; }
function list(value,key) {
  const result=Array.isArray(value)?value:value?.[key];
  if (!Array.isArray(result) || result.some(item=>!item || typeof item!=='object' || Array.isArray(item))) throw Error(`Invalid ${key} response from service`);
  return result;
}
async function api(path,body) {
  if(typeof path!=='string'||!path.startsWith('/api/')||path.includes('\\'))throw Error('Only local Sentinel API routes are permitted');
  const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),12000);
  try {
    const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{Authorization:`Bearer ${state.token}`,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store',signal:controller.signal});
    let data;
    try { data=await response.json(); } catch { throw Error(`Invalid JSON response (${response.status})`); }
    if (!response.ok) throw Error(typeof data?.error==='string'?data.error:`Request failed (${response.status})`);
    if (!data || typeof data!=='object') throw Error('Invalid service response');
    return data;
  } catch(error) {
    if (error.name==='AbortError') throw Error('Request timed out. Check the local service and retry.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function badge(text){const t=String(text||'recorded'),c=/block|fail|denied|cancel|expired|invalid/i.test(t)?'bad':/approv|pause|draft|pending/i.test(t)?'warn':/allow|success|complete|active|start/i.test(t)?'good':'';return `<span class="badge ${c}">${esc(t.replaceAll('_',' '))}</span>`}
function empty(title,description){return `<div class="empty"><span class="cross">⌖</span><h3>${esc(title)}</h3><p>${esc(description)}</p></div>`}
function panel(title,body,extra=''){return `<section class="panel"><div class="panel-title"><h2>${esc(title)}</h2>${extra}</div>${body}</section>`}
function time(v){if(!v)return '—';const d=new Date(typeof v==='number'&&v<1e12?v*1000:v);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString([], {hour12:false})}
function date(v){if(!v)return 'Not recorded';const d=new Date(typeof v==='number'&&v<1e12?v*1000:v);return Number.isNaN(d.getTime())?String(v):d.toLocaleString()}
function eventType(e){return e.event_type||e.type||'event'}
function identity(e){return e.identity||e}
function eventHtml(e){const type=eventType(e),data=e.data||e,ident=identity(e);return `<div class="event ${/block/.test(type)?'block':/fail/.test(type)?'failed':/approv/.test(type)?'approval':''}" tabindex="0" role="button" data-event="${esc(e.id||e.seq)}" aria-label="Inspect ${esc(type)}, session ${esc(ident.session_id||'unattributed')}, event ${esc(e.seq||e.id)}"><time>${esc(time(e.timestamp))}</time><span class="dot"></span><div><strong>${esc(data.tool_name||e.tool_name||type.replaceAll('_',' '))}</strong><small>${esc(data.reason||data.summary||ident.session_id||'No session attribution')}</small></div>${badge(data.decision||type)}</div>`}
function filteredEvents(){if(route()==='replay')return state.replay.events;return state.events.filter(e=>(!state.session||identity(e).session_id===state.session)&&(!state.query||JSON.stringify(e).toLowerCase().includes(state.query.toLowerCase())))}
function eventFeed(events=filteredEvents()){const filtered=['watch','replay'].includes(route())&&Boolean(state.query||state.session);return events.length?events.slice().reverse().map(eventHtml).join(''):filtered?empty('No matching events','No records match the selected session and search. Clear the filters to inspect other recorded activity.'):empty('No recorded activity','Events appear here when the Sentinel plugin observes Hermes. No synthetic telemetry is generated.')}
function toolbar(){return `<div class="toolbar"><input id="event-search" type="search" value="${esc(state.query)}" placeholder="Search tools, decisions, sessions…" aria-label="Search recorded events"><select id="session-filter" aria-label="Filter session"><option value="">All sessions</option>${(state.session&&!state.sessions.some(s=>(s.session_id||s.id)===state.session)?[{session_id:state.session},...state.sessions]:state.sessions).map(s=>`<option value="${esc(s.session_id||s.id)}" ${(s.session_id||s.id)===state.session?'selected':''}>${esc(s.session_id||s.id)}</option>`).join('')}</select><button id="export" class="secondary small">Export loaded JSON</button></div>`}
function missionState(m,now=Date.now()){if(m.status==='ACTIVE'&&m.expires_at){const expiry=Date.parse(m.expires_at);if(!Number.isFinite(expiry))return 'INVALID EXPIRY';if(expiry<=now)return 'EXPIRED';}return m.status;}
function missionClock(){return state.missions.map(m=>missionState(m)).join('|');}
function overview(){const stats=state.status.stats||state.status,events=state.events,blocked=stats.blocked??Object.entries(stats.by_type||{}).filter(([k])=>/block/.test(k)).reduce((n,[,v])=>n+v,0),approvals=stats.by_type?.approval_requested??events.filter(e=>/approval_requested/.test(eventType(e))).length;return `<div class="telemetry"><div class="telemetry-main"><span class="label">CONTROL PLANE / RUNTIME VISIBILITY</span><h2>${state.connected?'Service connected':'Awaiting connection'}</h2><p>${state.connected?'Policy enforcement runs independently of this dashboard.':'Authenticate in Settings to inspect recorded runtime activity.'}</p></div><div class="telemetry-stat"><span class="label">Recorded events</span><strong>${esc(stats.events??stats.total_events??events.length)}</strong></div><div class="telemetry-stat"><span class="label">Sessions observed</span><strong class="teal">${state.sessions.length}</strong></div><div class="telemetry-stat"><span class="label">Blocked actions</span><strong class="amber">${esc(blocked)}</strong></div></div><div class="grid"><div>${panel('Runtime activity',eventFeed(events.slice(-8)),`<a class="label" href="#watch">OPEN WATCH ↗</a>`)}<div class="module-list">${[['GUARD','Deterministic policy decisions'],['WATCH','Persistent runtime events'],['REPLAY','Read-only investigation'],['MISSIONS','Scoped session permissions'],['RECOVERY','Supported file checkpoints'],['MESH','Multi-session visibility']].map(([a,b])=>`<div class="module"><strong>${a}</strong><small>${b}</small></div>`).join('')}</div></div><aside>${panel('Authority & boundaries',`<div class="panel-body"><div class="row"><span>Dashboard transport</span>${badge(state.connected?'connected':'offline')}</div><div class="row"><span>Sessions recorded</span><code>${state.sessions.length}</code></div><div class="row"><span>Active missions</span><code>${state.missions.filter(m=>missionState(m)==='ACTIVE').length}</code></div><div class="row"><span>Approval requests recorded</span><code>${approvals}</code></div><p class="hint">Human approvals are resolved through Hermes’ native approval gate. Recorded requests do not imply a pending decision.</p></div>`)}${panel('Mission focus',state.missions.filter(m=>missionState(m)==='ACTIVE').length?state.missions.filter(m=>missionState(m)==='ACTIVE').slice(0,3).map(m=>`<div class="item"><h3>${esc(m.name)}</h3><code>${esc(m.session_id)}</code><p>${esc(m.description||'Bounded session authority')}</p></div>`).join(''):empty('No active mission','Create a mission to bind permissions to a session.'))}</aside></div>`}
function guard(){return `<div class="grid"><div>${panel('Policy decision laboratory',`<form id="evaluate" class="panel-body"><div class="fields"><label>Tool name<input name="tool_name" value="terminal" required></label><label>Session identity<input name="session_id" placeholder="A real session ID"></label></div><label>Tool arguments · JSON<textarea name="args" spellcheck="false">{ "command": "git status" }</textarea></label><button>Evaluate operation</button><p class="section-note">Evaluation inspects policy only. It does not execute the tool or grant authorization.</p></form>`)}${panel('Decision explanation',`<div class="panel-body"><pre id="evaluation-result" tabindex="0" aria-live="polite">${state.evaluation?esc(JSON.stringify(state.evaluation,null,2)):'Evaluate an operation to inspect its decision, rule and explanation.'}</pre></div>`)}${panel('Custom policy rules',`<form id="policy-form" class="panel-body"><p class="section-note">Add restrictive rules using tool-name globs. Custom decisions can block or require native approval; they cannot allow an operation that mandatory protections reject.</p><label>Rules · JSON array<textarea name="rules" rows="12" spellcheck="false" placeholder='[{"id":"review-writes","priority":100,"enabled":true,"tools":["write_*"],"decision":"APPROVAL_REQUIRED","reason":"Review file writes"}]'>${esc(JSON.stringify(state.policies,null,2))}</textarea></label><button>Validate &amp; save rules</button><p class="section-note">Fields: id, priority, enabled, tools, decision, reason. Save applies validated rules to subsequent tool calls.</p></form>`)}</div><aside>${panel('Mandatory protections',`<div class="panel-body">${['Destructive shell operations','Sensitive and secret paths','Privilege escalation','Repository mutations','Deployment and financial activity','Mission directory and tool scope'].map(t=>`<div class="row"><span>${t}</span>${badge('policy class')}</div>`).join('')}<p class="hint">Hook enforcement applies to the tool surfaces Hermes exposes. It is not an operating-system sandbox.</p><p class="section-note">Mission restrictions may narrow authority. They cannot override mandatory protections. Policy configuration currently uses the local service configuration.</p></div>`)}</aside></div>`}
function missions(){return `<div class="grid"><div>${panel('Mission registry',state.missions.length?state.missions.map(m=>`<article class="item"><div class="item-head"><div><h3>${esc(m.name)}</h3><code>${esc(m.id)}</code></div>${badge(missionState(m))}</div>${missionState(m)!==m.status?'<p class="hint">Recorded status is ACTIVE, but the expiry prevents further mission execution. Update its expiration before reactivating.</p>':''}<p>${esc(m.description||'No description')}</p><p>SESSION <code>${esc(m.session_id||'Unassigned')}</code> · EXPIRES <code>${esc(m.expires_at?date(m.expires_at):'Not set')}</code></p><p>ALLOWED PATHS <code>${esc((m.display_allowed_directories||m.allowed_directories||[]).join(', ')||'No mission path restriction')}</code></p><div class="actions">${['ACTIVE','PAUSED','COMPLETED','CANCELLED'].filter(s=>s!==m.status&&!(s==='ACTIVE'&&missionState(m)!==m.status)).map(s=>`<button class="secondary small" data-mission="${esc(m.id)}" data-status="${s}">${s==='ACTIVE'?'Activate':s==='PAUSED'?'Pause':s==='COMPLETED'?'Complete':'Cancel'}</button>`).join('')}</div></article>`).join(''):empty('No missions configured','Create a bounded assignment using the form. Mission authority is enforced by the backend.'))}</div><aside>${panel('Create mission',`<form id="mission-form" class="panel-body"><label>Mission name<input name="name" required placeholder="Investigate a build failure"></label><label>Description<textarea name="description" placeholder="Describe the assignment and its boundaries"></textarea></label><label>Session ID<input name="session_id" required placeholder="Exact Hermes session identifier"></label><label>Template<select name="template">${Object.entries(templates).map(([key,t])=>`<option value="${key}">${esc(t.name)}</option>`).join('')}</select></label><label>Allowed directories · one per line<textarea name="allowed_directories" required placeholder="Absolute workspace path"></textarea></label><label>Restricted directories · one per line<textarea name="restricted_directories" placeholder="Protected absolute paths"></textarea></label><label>Approved tools · comma separated<input name="approved_tools" value="terminal, read_file, write_file, search_files, patch" placeholder="terminal, read_file, write_file"></label><label>Restricted tools · comma separated<input name="restricted_tools" placeholder="Optional restricted tool names"></label><label>Network domains · comma separated<input name="network_domains" placeholder="Explicitly permitted destinations"></label><label>Expiration<input name="expires_at" type="datetime-local" required></label><button>Create draft mission</button></form>`)}</aside></div>`}
function recovery(){return `<div class="grid"><div>${panel('File checkpoint ledger',`<div class="panel-body"><p class="hint">Recovery covers supported local file checkpoints. External API changes, deployments, database writes and arbitrary shell side effects cannot be undone here. Restoration requires an explicit confirmation and backend conflict checks.</p></div>${state.checkpoints.length?state.checkpoints.map(c=>`<article class="item"><div class="item-head"><div><h3>${esc(c.display_path||c.path||c.file_path)}</h3>${c.display_path?'<small>Workspace-relative path</small>':''}<code>${esc(c.id||c.checkpoint_id)}</code></div>${badge(c.status||c.restoration_status||'checkpoint')}</div><p>${esc(date(c.timestamp||c.created_at))} · SESSION <code>${esc(c.session_id||c.identity?.session_id||'Unattributed')}</code></p><p>ORIGINAL HASH <code>${esc(c.original_hash||c.original_content_hash||c.before_hash||'New file checkpoint')}</code></p><div class="actions">${c.status==='OPEN'?`<button class="secondary small" data-seal="${esc(c.id)}">Seal current file state</button>`:''}<button class="danger small" data-restore="${esc(c.id||c.checkpoint_id)}" ${c.status!=='SEALED'?'disabled':''}>Restore checkpoint</button></div></article>`).join(''):empty('No recovery checkpoints','Supported file operations create checkpoints through the runtime integration. No files have been restored.')}`)}</div><aside>${panel('Manual file checkpoint',`<form id="checkpoint-form" class="panel-body"><p class="section-note">Create a checkpoint before a controlled change. After the change, seal the checkpoint to record the file state that restoration may safely replace.</p><label>File path<input name="path" required placeholder="Path inside the configured workspace"></label><button>Create checkpoint</button><p class="hint">Only individual files within the configured workspace are supported. Symlinks and Sentinel state are rejected.</p></form>`)}</aside></div>`}

function mesh(){return panel('Agent / session registry',state.sessions.length?state.sessions.map(s=>`<article class="item"><div class="item-head"><div><h3>${esc(s.agent_id||'Hermes session')}</h3><code>${esc(s.session_id||s.id)}</code></div>${badge(s.status||'recorded')}</div><p>LAST EVENT ${esc(date(s.last_seen||s.updated_at))}</p><p>MISSION <code>${esc(s.mission_id||'No recorded association')}</code> · RECORDED EVENTS <code>${esc(s.event_count??'Not recorded')}</code></p><button class="secondary small" data-session="${esc(s.session_id||s.id)}">Investigate session ↗</button></article>`).join(''):empty('No sessions recorded','The registry is populated from actual runtime events. A connected dashboard alone does not mean Hermes is active.'))}
function settings(){return panel('Local service authentication',`<form id="connect-form" class="panel-body connection-form"><p class="section-note">Enter the token generated by the local Sentinel service. It remains in this browser tab’s session storage and is sent only to this origin.</p><label>Service token<input name="token" type="password" autocomplete="off" required placeholder="Paste the local service token" value=""></label><button>Connect service</button> <button type="button" class="secondary" id="disconnect">Disconnect</button><p class="hint">Closing this page does not disable runtime policy enforcement. This interface never modifies the primary Hermes profile.</p><div class="row"><span>Service endpoint</span><code>${esc(location.origin)}</code></div><div class="row"><span>Browser connection</span>${badge(state.connected?'connected':'offline')}</div><div class="row"><span>Telemetry source</span><code>Persisted Hermes hook events</code></div></form>`)+panel('Event retention',`<form id="retention-form" class="panel-body connection-form"><p class="section-note">Permanently remove event records older than the selected date. This does not undo tool actions or remove file checkpoints.</p><label>Delete events recorded before<input name="before" type="datetime-local" required></label><button class="danger">Delete older events</button></form>`)}
function saveDrafts() {
  document.querySelectorAll('form[data-dirty="true"]').forEach(form=>{
    if (form.id==='connect-form') return;
    state.drafts[form.id]={};
    for (const field of form.elements) if (field.name && field.type!=='password') state.drafts[form.id][field.name]=field.value;
  });
}
function restoreDrafts() {
  for (const [id,values] of Object.entries(state.drafts)) {
    const form=document.getElementById(id);
    if (!form) continue;
    for (const [name,value] of Object.entries(values)) if(form.elements.namedItem(name)) form.elements.namedItem(name).value=value;
    form.dataset.dirty='true';
  }
}
function forgetDraft(id) {
  delete state.drafts[id];
  const form=document.getElementById(id);
  if (form) delete form.dataset.dirty;
}
function historyNote() {
  const replay=route()==='replay', source=replay?state.replay:state, count=replay?source.events.length:state.events.length;
  return `<div class="panel-body section-note">${count} records in this browser window (maximum ${EVENT_WINDOW}). ${replay?'Search and session filters query the persisted journal. Use Load next page to investigate older-to-newer history.':'Watch starts with the latest 500 records and follows new activity. Search filters this loaded window; use Replay to search the full journal.'} ${source.dropped?esc(source.dropped)+' earlier loaded records have left the browser window. ':''}${replay&&source.stale?'Previously loaded records are retained and may be stale; they may reflect the previous filters. ':''}Export includes only the loaded, filtered records.</div>`;
}
function render({preserveDrafts=true}={}) {
  if(preserveDrafts)saveDrafts();
  const enteredToken=preserveDrafts&&$('#connect-form')?.elements.namedItem('token')?.value;
  const r=route(),v=views[r],focused=document.activeElement,focusId=focused?.id,focusForm=focused?.form?.id,focusName=focused?.name,focusKey=['event','mission','restore','seal','session'].find(key=>focused?.dataset?.[key]),focusValue=focusKey?focused.dataset[focusKey]:null,focusStatus=focused?.dataset?.status;
  const selection=focused && typeof focused.selectionStart==='number'?[focused.selectionStart,focused.selectionEnd]:null;
  $('#section-label').textContent=v[0]; $('#page-title').textContent=v[1]; $('#page-description').textContent=v[2];
  document.querySelectorAll('nav a').forEach(a=>{const active=a.hash===`#${r}`;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  $('#content').innerHTML=r==='overview'?overview():r==='guard'?guard():r==='watch'||r==='replay'?panel(r==='watch'?'Live event stream':'Recorded execution timeline',toolbar()+historyNote()+eventFeed()+(r==='replay'?`<div class="panel-body"><button id="load-history" class="secondary" ${state.replay.busy||!state.replay.more?'disabled':''}>${state.replay.busy?'Loading history…':state.replay.more?'Load next page':'End of recorded history'}</button></div>`:''),`<span class="label">${r==='watch'?'3 SECOND SYNC':'READ ONLY'}</span>`):r==='missions'?missions():r==='recovery'?recovery():r==='mesh'?mesh():settings();
  state.missionClock=missionClock();restoreDrafts();if(enteredToken&&$('#connect-form'))$('#connect-form').elements.namedItem('token').value=enteredToken;bind();state.needsRender=false;
  const restored=focusId?document.getElementById(focusId):focusForm?document.getElementById(focusForm)?.elements.namedItem(focusName):focusKey?[...document.querySelectorAll('[data-'+focusKey+']')].find(el=>el.dataset[focusKey]===focusValue&&(!focusStatus||el.dataset.status===focusStatus)):null;
  if (restored && !$('#details').open) {
    restored.focus({preventScroll:true});
    if(selection && typeof restored.setSelectionRange==='function') restored.setSelectionRange(...selection);
  }
}
function validateSnapshot(results) {
  const [status,events,sessions,missions,checkpoints,templateMap,policies]=results;
  if (!status.stats || typeof status.stats!=='object' || !Number.isSafeInteger(status.stats.events)||status.stats.events<0) throw Error('Invalid service status response');
  const nextEvents=list(events,'events');
  if(nextEvents.some(e=>!Number.isSafeInteger(e.seq)||e.seq<1||typeof e.event_type!=='string')) throw Error('Invalid journal event response');
  const nextTemplates=templateMap.templates||templateMap;
  if(Array.isArray(nextTemplates)||Object.values(nextTemplates).some(t=>!t || !Array.isArray(t.approved_tools)||!Array.isArray(t.allowed_domains))) throw Error('Invalid mission template response');
  return {status,events:nextEvents,sessions:list(sessions,'sessions'),missions:list(missions,'missions'),checkpoints:list(checkpoints,'checkpoints'),templates:nextTemplates,policies:list(policies,'rules')};
}
function mergeEvents(incoming) {
  const existing=new Set(state.events.map(e=>e.seq));
  const unique=incoming.filter(e=>!existing.has(e.seq));
  state.events.push(...unique);state.events.sort((a,b)=>a.seq-b.seq);
  if (incoming.length) state.cursor=Math.max(state.cursor,...incoming.map(e=>e.seq));
  const overflow=Math.max(0,state.events.length-EVENT_WINDOW);
  if(overflow){state.events.splice(0,overflow);state.dropped+=overflow;}
  state.eventsLoaded=true;
}
async function refresh({quiet=false}={}) {
  if(state.busy){if(!quiet)state.pendingRefresh=true;return false;}
  if(!state.token){state.connected=false;updateConnection();if(!quiet)notice('Connect the local service in Settings to view runtime data.');return false;}
  state.busy=true;const generation=state.generation;
  $('#refresh').disabled=true;$('#refresh').textContent='Syncing…';
  try {
    const snapshot=validateSnapshot(await Promise.all([api('/api/status'),api(state.eventsLoaded?'/api/events?limit=500&after='+state.cursor:'/api/events?tail=1'),api('/api/sessions'),api('/api/missions'),api('/api/checkpoints'),api('/api/templates'),api('/api/policies')]));
    if(generation!==state.generation)return false;
    state.needsRender ||= !state.connected || snapshot.events.some(e=>e.seq>state.cursor) || JSON.stringify([state.status,state.policies,state.sessions,state.missions,state.checkpoints,templates])!==JSON.stringify([snapshot.status,snapshot.policies,snapshot.sessions,snapshot.missions,snapshot.checkpoints,snapshot.templates]);
    state.status=snapshot.status;state.policies=snapshot.policies;
    for(const key of Object.keys(templates))delete templates[key];Object.assign(templates,snapshot.templates);
    mergeEvents(snapshot.events);state.sessions=snapshot.sessions;state.missions=snapshot.missions;state.checkpoints=snapshot.checkpoints;state.connected=true;
    if(state.noticeKind==='connection'||!quiet)notice('');
    $('#last-update').textContent=`LAST SYNC ${new Date().toLocaleTimeString([], {hour12:false})}`;
    // Form drafts survive polling; do not dismiss a focused native select or move an open dialog's focus.
    if((!quiet||state.needsRender) && !$('#details').open && document.activeElement?.tagName!=='SELECT')render();
    return true;
  } catch(error) {
    if(generation===state.generation){state.connected=false;notice(`Service unavailable: ${error.message}. Recorded data may be stale.`,'connection');}
    return false;
  } finally {
    state.busy=false;$('#refresh').disabled=false;$('#refresh').textContent='↻ Refresh';updateConnection();
    if(state.pendingRefresh){state.pendingRefresh=false;queueMicrotask(()=>refresh({quiet:true}));}
  }
}
function updateConnection(){ $('#connection').textContent=state.connected?'SERVICE CONNECTED':'DISCONNECTED';$('#connection').classList.toggle('offline',!state.connected); }
function split(value){return String(value||'').split(/[\n,]/).map(s=>s.trim()).filter(Boolean);}
function resetReplay(){state.replay={events:[],cursor:0,loaded:false,busy:false,more:true,dropped:0,generation:state.replay.generation+1};}
async function loadReplay(reset=false){
  if(!state.token){notice('Connect the local service in Settings before loading history.');return;}
  const prior=state.replay;
  reset=reset||prior.needsReset||prior.query!==state.query||prior.session!==state.session;
  // Replace history transactionally: failed refreshes must not erase evidence.
  // A distinct object also invalidates older in-flight queries after filter changes.
  if(reset)state.replay={...prior,busy:false,needsReset:true,stale:prior.loaded,generation:prior.generation+1};
  const replay=state.replay;if(replay.busy||(!reset&&!replay.more))return;
  replay.busy=true;render();const generation=state.generation;
  const queryText=state.query,session=state.session;
  try{
    const query=new URLSearchParams({limit:'500',after:String(reset?0:replay.cursor),session_id:session,search:queryText});
    const page=list(await api('/api/events?'+query),'events');
    if(generation!==state.generation||state.replay!==replay)return;
    if(page.some(e=>!Number.isSafeInteger(e.seq)||e.seq<1||typeof e.event_type!=='string'))throw Error('Invalid journal event response');
    if(reset){replay.events=[];replay.cursor=0;replay.dropped=0;}
    const known=new Set(replay.events.map(e=>e.seq));replay.events.push(...page.filter(e=>!known.has(e.seq)));replay.events.sort((a,b)=>a.seq-b.seq);
    if(page.length)replay.cursor=Math.max(...page.map(e=>e.seq));
    const overflow=Math.max(0,replay.events.length-EVENT_WINDOW);if(overflow){replay.events.splice(0,overflow);replay.dropped+=overflow;}
    replay.more=page.length===500;replay.loaded=true;replay.needsReset=false;replay.stale=false;replay.query=queryText;replay.session=session;
    if(state.noticeKind==='history')notice('');
  }catch(error){if(generation===state.generation&&state.replay===replay){replay.stale=replay.loaded;notice(`History unavailable: ${error.message}. Previously loaded records are retained and may be stale.`,'history');}}
  finally{replay.busy=false;if(state.replay===replay&&route()==='replay')render();}
}

async function mutate(path,body,{formId,success}={}){
  try{
    await api(path,body);if(formId)forgetDraft(formId);const synced=await refresh({quiet:true});if(success)notice(success+(synced?'':' Dashboard synchronization is pending; refresh to verify the recorded state.'));return true;
  }catch(error){notice(error.message);return false;}
}
async function submitting(form,action){
  if(form.dataset.submitting==='true')return;
  form.dataset.submitting='true';const buttons=[...form.querySelectorAll('button[type="submit"],button:not([type])')];buttons.forEach(b=>b.disabled=true);
  try{await action();}catch(error){notice(error.message);}finally{delete form.dataset.submitting;buttons.forEach(b=>b.disabled=false);}
}
function disconnect(){
  state.generation++;state.token='';state.connected=false;state.status={};state.events=[];state.cursor=0;state.eventsLoaded=false;state.dropped=0;state.sessions=[];state.missions=[];state.checkpoints=[];state.policies=[];state.drafts={};state.evaluation=null;resetReplay();
  try{sessionStorage.removeItem('sentinel-token');}catch{}
  render({preserveDrafts:false});updateConnection();$('#last-update').textContent='Awaiting authenticated connection';notice('Browser disconnected.');
}
function exportReport(){
  const replay=route()==='replay',scopeSession=replay?state.replay.session:state.session,scopeSearch=replay?state.replay.query:state.query;
  const events=filteredEvents(),blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),mode:'forensic_read_only',scope:'loaded_filtered_records',session_id:scopeSession||null,search_applied:Boolean(scopeSearch),stale:Boolean(replay&&state.replay.stale),record_count:events.length,journal_event_count:state.status.stats?.events??null,events},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='sentinel-execution-report.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
let detailEventId=null,searchTimer=null;
function openEvent(id){
  const event=[...state.events,...state.replay.events].find(e=>String(e.id||e.seq)===id);if(!event)return;
  detailEventId=id;$('#detail-content').textContent=JSON.stringify(event,null,2);$('#details').showModal();$('#close-details').focus();
}
function bind(){
  document.querySelectorAll('#content form').forEach(form=>{
    const dirty=()=>{form.dataset.dirty='true';};form.oninput=dirty;form.onchange=dirty;
  });
  document.querySelectorAll('[data-event]').forEach(el=>{el.onclick=()=>openEvent(el.dataset.event);el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openEvent(el.dataset.event);}};});
  const search=$('#event-search');if(search)search.oninput=()=>{state.query=search.value;clearTimeout(searchTimer);if(route()==='replay')searchTimer=setTimeout(()=>loadReplay(true),250);else render();};
  const selector=$('#session-filter');if(selector)selector.onchange=()=>{state.session=selector.value;if(route()==='replay')loadReplay(true);else render();};
  const load=$('#load-history');if(load)load.onclick=()=>loadReplay();
  const exporter=$('#export');if(exporter)exporter.onclick=exportReport;
  const checkpoint=$('#checkpoint-form');if(checkpoint)checkpoint.onsubmit=e=>{e.preventDefault();submitting(checkpoint,()=>mutate('/api/checkpoints',{path:new FormData(checkpoint).get('path')},{formId:checkpoint.id,success:'Checkpoint created. Seal it after the controlled file change.'}));};
  document.querySelectorAll('[data-seal]').forEach(b=>b.onclick=async()=>{b.disabled=true;await mutate('/api/checkpoints/seal',{id:b.dataset.seal},{success:'Checkpoint sealed against the current file state.'});b.disabled=false;});
  const retention=$('#retention-form');if(retention)retention.onsubmit=e=>{e.preventDefault();submitting(retention,async()=>{const before=new Date(new FormData(retention).get('before')).toISOString();if(!confirm('Permanently delete event records older than '+date(before)+'?'))return;const result=await api('/api/retention',{before});state.generation++;state.events=[];state.cursor=0;state.eventsLoaded=false;state.dropped=0;resetReplay();forgetDraft(retention.id);await refresh({quiet:true});notice('Event retention applied. '+(result.deleted??result.count??'')+' records removed.');});};
  const connect=$('#connect-form');if(connect)connect.onsubmit=e=>{e.preventDefault();submitting(connect,async()=>{const token=String(new FormData(connect).get('token')||'').trim();if(!token)throw Error('Enter the local service token.');state.generation++;state.token=token;state.events=[];state.cursor=0;state.eventsLoaded=false;state.dropped=0;resetReplay();try{sessionStorage.setItem('sentinel-token',token);}catch{}await refresh();});};
  const disconnectButton=$('#disconnect');if(disconnectButton)disconnectButton.onclick=disconnect;
  const policy=$('#policy-form');if(policy)policy.onsubmit=e=>{e.preventDefault();submitting(policy,async()=>{const rules=JSON.parse(new FormData(policy).get('rules'));if(!Array.isArray(rules))throw Error('Rules must be a JSON array.');await mutate('/api/policies',{rules},{formId:policy.id,success:'Validated policy rules saved. Subsequent operations use the new rules.'});});};
  const evaluate=$('#evaluate');if(evaluate)evaluate.onsubmit=e=>{e.preventDefault();submitting(evaluate,async()=>{const form=new FormData(evaluate),args=JSON.parse(form.get('args'));if(!args||typeof args!=='object'||Array.isArray(args))throw Error('Arguments must be a JSON object.');state.evaluation=await api('/api/evaluate',{tool_name:form.get('tool_name'),args,identity:{session_id:form.get('session_id')}});const output=$('#evaluation-result');if(output)output.textContent=JSON.stringify(state.evaluation,null,2);notice('');});};
  const mission=$('#mission-form');
  if(mission){
    mission.elements.template.onchange=()=>{const template=templates[mission.elements.template.value];if(!template)return;mission.dataset.dirty='true';mission.elements.approved_tools.value=(template.approved_tools||[]).join(', ');mission.elements.restricted_tools.value=(template.restricted_tools||[]).join(', ');mission.elements.network_domains.value=(template.allowed_domains||[]).join(', ');};
    mission.onsubmit=e=>{e.preventDefault();submitting(mission,async()=>{const f=new FormData(mission),body={name:f.get('name'),description:f.get('description'),session_id:f.get('session_id'),template:f.get('template'),status:'DRAFT',allowed_directories:split(f.get('allowed_directories')),restricted_directories:split(f.get('restricted_directories')),approved_tools:split(f.get('approved_tools')),restricted_tools:split(f.get('restricted_tools')),allowed_domains:split(f.get('network_domains')),allow_deployment:false,expires_at:new Date(f.get('expires_at')).toISOString()};await mutate('/api/missions',body,{formId:mission.id,success:'Mission saved as draft. Activate it when its scope is ready.'});});};
  }
  document.querySelectorAll('[data-mission]').forEach(b=>b.onclick=async()=>{b.disabled=true;await mutate(`/api/missions/${encodeURIComponent(b.dataset.mission)}`,{status:b.dataset.status},{success:'Mission status updated.'});b.disabled=false;});
  document.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{if(!confirm('Restore this checkpoint? The backend will reject changed files or invalid checkpoint data. This changes the local file.'))return;b.disabled=true;await mutate('/api/restore',{id:b.dataset.restore,authorized:true},{success:'Checkpoint restored.'});b.disabled=false;});
  document.querySelectorAll('[data-session]').forEach(b=>b.onclick=()=>{state.session=b.dataset.session;resetReplay();if(route()==='replay')loadReplay();else location.hash='replay';});
}
$('.skip').onclick=event=>{event.preventDefault();$('#main').focus();};
$('#refresh').onclick=()=>refresh().then(()=>{if(route()==='replay')loadReplay(true);});
$('#close-details').onclick=()=>$('#details').close();
$('#details').addEventListener('close',()=>{render();const trigger=[...document.querySelectorAll('[data-event]')].find(el=>el.dataset.event===detailEventId);if(trigger)trigger.focus();else $('#page-title').focus();});
window.addEventListener('hashchange',()=>{clearTimeout(searchTimer);notice('');render();if(route()==='replay'&&(!state.replay.loaded||state.replay.query!==state.query||state.replay.session!==state.session))loadReplay();});
function tick(){$('#clock').textContent=new Date().toLocaleTimeString([], {hour12:false});if(state.missionClock!==missionClock()){state.needsRender=true;if(['overview','missions'].includes(route())&&!$('#details').open&&document.activeElement?.tagName!=='SELECT')render();}}
tick();setInterval(tick,1000);render();refresh().then(()=>{if(route()==='replay')loadReplay();});setInterval(()=>refresh({quiet:true}),3000);

