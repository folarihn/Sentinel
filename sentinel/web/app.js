'use strict';
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const EVENT_WINDOW = 2000;
function storedToken() { try { return sessionStorage.getItem('sentinel-token') || ''; } catch { return ''; } }
const state = {token:storedToken(), connected:false, status:{}, events:[], cursor:0, eventsLoaded:false, dropped:0, sessions:[], missions:[], checkpoints:[], policies:[], query:'', session:'', busy:false, pendingRefresh:false, needsRender:false, generation:0, drafts:{}, evaluation:null, noticeKind:'', replay:{events:[], cursor:0, loaded:false, busy:false, more:true, dropped:0, generation:0}};
const templates=Object.create(null);
const views={overview:['COMMAND CENTER','Operational overview','A clear view of the autonomy you authorize.'],guard:['POLICY ENFORCEMENT','Guard','Inspect decisions before an operation reaches the runtime.'],watch:['RUNTIME OBSERVABILITY','Watch','Actual runtime events, in the order Sentinel recorded them.'],replay:['FORENSIC INVESTIGATION','Replay','Reconstruct execution history. Investigation never re-executes a tool.'],missions:['BOUNDED AUTHORITY','Mission Control','Give autonomous work an explicit scope and lifecycle.'],recovery:['CONTROLLED RESTORATION','Recovery','Restore supported file changes with integrity and conflict checks.'],mesh:['SESSION REGISTRY','Mesh','One operational picture across recorded Hermes sessions.'],settings:['LOCAL CONFIGURATION','Settings','Connect this browser to your local Sentinel service.']};
function route(){const key=location.hash.slice(1);return Object.hasOwn(views,key)?key:'overview'}
function notice(message, kind='operation') { $('#notice').textContent=message; $('#notice').dataset.tone=kind; state.noticeKind=kind; }
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
function badge(text){const t=String(text||'recorded'),c=/block|fail|denied|^deny$|invalid/i.test(t)?'bad':/approv|pause|draft|pending|expired|open/i.test(t)?'warn':/allow|success|complete|active|sealed|restored|connected|observed/i.test(t)?'good':'';return `<span class="badge ${c}">${esc(t.replaceAll('_',' '))}</span>`}
function empty(title,description){return `<div class="empty"><span class="cross">⌖</span><h3>${esc(title)}</h3><p>${esc(description)}</p></div>`}
function panel(title,body,extra=''){return `<section class="panel"><div class="panel-title"><h2>${esc(title)}</h2>${extra}</div>${body}</section>`}
function time(v){if(!v)return '—';const d=new Date(typeof v==='number'&&v<1e12?v*1000:v);return Number.isNaN(d.getTime())?'—':d.toLocaleTimeString([], {hour12:false})}
function date(v){if(!v)return 'Not recorded';const d=new Date(typeof v==='number'&&v<1e12?v*1000:v);return Number.isNaN(d.getTime())?String(v):d.toLocaleString()}
function eventType(e){return e.event_type||e.type||'event'}
function identity(e){return e.identity||e}
function eventHtml(e){
  const type=eventType(e),data=e.data||e,ident=identity(e),session=ident.session_id||ident.session_key||'Unattributed';
  const fresh=state.newEventSeqs?.includes(e.seq)?' new-event':'';
  return `<div class="event ${/block/.test(type)?'block':/fail/.test(type)?'failed':/approv/.test(type)?'approval':''}${fresh}" tabindex="0" role="button" data-event="${esc(e.id||e.seq)}" aria-label="Inspect ${esc(type)}, session ${esc(ident.session_id||ident.session_key||'unattributed')}, event ${esc(e.seq||e.id)}"><time>${esc(time(e.timestamp))}</time><span class="dot" aria-hidden="true"></span><div><strong>${esc(data.tool_name||e.tool_name||type.replaceAll('_',' '))}</strong>${data.reason||data.summary?`<small>${esc(data.reason||data.summary)}</small>`:''}<span class="event-kind">${esc(type)} · ${esc(session)} · #${esc(e.seq||'—')}</span></div>${badge(data.decision||data.choice||type)}</div>`;
}
function filteredEvents(){if(route()==='replay')return state.replay.events;return state.events.filter(e=>(!state.session||identity(e).session_id===state.session)&&(!state.query||JSON.stringify(e).toLowerCase().includes(state.query.toLowerCase())))}
function eventFeed(events=filteredEvents()){const filtered=['watch','replay'].includes(route())&&Boolean(state.query||state.session);return events.length?events.slice().reverse().map(eventHtml).join(''):filtered?empty('No matching events','No records match the selected session and search. Clear the filters to inspect other recorded activity.'):empty('No recorded activity','Events appear here when the Sentinel plugin observes Hermes. No synthetic telemetry is generated.')}
function toolbar(){return `<div class="toolbar"><input id="event-search" type="search" value="${esc(state.query)}" placeholder="Search tools, decisions, sessions…" aria-label="Search recorded events"><select id="session-filter" aria-label="Filter session"><option value="">All sessions</option>${(state.session&&!state.sessions.some(s=>(s.session_id||s.id)===state.session)?[{session_id:state.session},...state.sessions]:state.sessions).map(s=>`<option value="${esc(s.session_id||s.id)}" ${(s.session_id||s.id)===state.session?'selected':''}>${esc(s.session_id||s.id)}</option>`).join('')}</select><button id="export" class="secondary small">Export loaded JSON</button></div>`}
function missionState(m,now=Date.now()){if(m.status==='ACTIVE'&&m.expires_at){const expiry=Date.parse(m.expires_at);if(!Number.isFinite(expiry))return 'INVALID EXPIRY';if(expiry<=now)return 'EXPIRED';}return m.status;}
function missionClock(){return state.missions.map(m=>missionState(m)+':'+missionActivationBlocked(m)).join('|');}
function missionActivationBlocked(m){if(!m.expires_at)return false;const expiry=Date.parse(m.expires_at);return !Number.isFinite(expiry)||expiry<=Date.now();}
function compactPath(value){const text=String(value||'');if(!text)return 'Not recorded';const parts=text.replaceAll('\\','/').split('/').filter(Boolean);return parts.length>2?'…/'+parts.slice(-2).join('/'):text;}
function permissionList(values, fallback='None configured'){return esc((values||[]).join(', ')||fallback);}
function overviewValues(){const stats=state.status.stats||state.status;return {events:stats.events??stats.total_events??(state.eventsLoaded?state.events.length:'—'),sessions:state.connected||state.eventsLoaded?state.sessions.length:'—',blocked:stats.blocked??(stats.by_type?Object.entries(stats.by_type).filter(([key])=>/block/.test(key)).reduce((n,[,value])=>n+value,0):'—')};}
function overview(){
  const values=overviewValues(),events=state.events,stats=state.status.stats||{},active=state.missions.filter(m=>missionState(m)==='ACTIVE'),decisions=events.filter(e=>/blocked|approval_decided|approval_required|failed/.test(eventType(e))).slice(-4);
  const metric=(key,label,context,tone='')=>`<div class="telemetry-stat"><span class="label">${label}</span><strong class="${tone} ${state.changedMetrics?.includes(key)?'metric-changed':''}">${esc(values[key])}</strong><small>${context}</small></div>`;
  return `<div class="telemetry"><div class="telemetry-main"><span class="label">LOCAL SERVICE / TRANSPORT</span><h2 class="connection-state ${state.connected?'':'offline'}">${state.connected?'Service connected':'Awaiting connection'}</h2><p>${state.connected?'Recorded data synchronized. Runtime health is not attested.':state.eventsLoaded?'Offline. Last recorded snapshot retained.':'Authenticate in Settings to inspect recorded runtime activity.'}</p></div>${metric('events','Recorded events','Persisted journal total')}${metric('sessions','Observed sessions','Recorded, not live agents','teal')}${metric('blocked','Blocked operations','Recorded policy blocks','red')}</div>
  <div class="grid"><div>${panel('Recent execution',eventFeed(events.slice(-6)),`<a class="label" href="#watch">OPEN WATCH ↗</a>`)}<div class="module-list">${[['GUARD','Policy workbench'],['WATCH','Observed execution'],['REPLAY','Read-only investigation'],['MISSIONS','Bounded authority'],['RECOVERY','File checkpoints'],['MESH','Session registry']].map(([name,description])=>`<a class="module" href="#${name.toLowerCase()}"><strong>${name} ↗</strong><small>${description}</small></a>`).join('')}</div>${panel('Recent security decisions',decisions.length?eventFeed(decisions):empty('No decisions in the loaded window','No blocked, failed or approval records are present in this browser window.'),'<a class="label" href="#replay">INVESTIGATE ↗</a>')}</div>
  <aside>${panel('Authority & boundaries',`<div class="panel-body"><p class="subhead">HOOK-LEVEL CONTROL</p><p class="section-note">Sentinel evaluates supported tool requests. It cannot isolate the host, cancel an executing tool, or undo external side effects.</p><div class="row"><span>Dashboard transport</span>${badge(state.connected?'connected':'offline')}</div><div class="row"><span>Active missions</span><code>${state.connected||state.eventsLoaded||state.missions.length?active.length:'—'}</code></div><div class="row"><span>Approval requests recorded</span><code>${esc(stats.by_type?.approval_requested??'Not reported')}</code></div><p class="hint">Hermes resolves native approvals. Requests in the journal do not imply a decision is still pending. <a href="#settings">Connection details ↗</a></p></div>`)}${panel('Mission focus',active.length?active.slice(0,3).map(m=>`<article class="item"><div class="item-head"><h3>${esc(m.name)}</h3>${badge(missionState(m))}</div><p>${esc(m.description||'Bounded session authority')}</p><code>${esc(m.session_id||'Unassigned')}</code><p><a class="label" href="#missions">REVIEW SCOPE ↗</a></p></article>`).join(''):state.connected||state.eventsLoaded||state.missions.length?empty('No active mission','Create a mission to bind permissions to a session.'):empty('Mission data unavailable','Authenticate to inspect recorded mission authority.'),'<a class="label" href="#missions">MANAGE ↗</a>')}</aside></div>`;
}
function evaluationMarkup(){const result=state.evaluation;if(!result)return `<p class="section-note">Evaluate an operation to inspect its decision, rule and explanation.</p><p class="hint">Dry run only. No tool executes and no approval is granted.</p>`;return `<div class="evaluation-summary" data-decision="${esc(result.decision)}">${badge(result.decision)}<h3>${esc(result.reason||'Policy decision recorded')}</h3><code>${esc(result.rule||'No rule identifier')}</code><p>This is a policy inspection, not execution authorization. Hermes still owns native approval.</p></div>`;}
function guard(){return `<div class="guard-layout"><div class="guard-editor">${panel('Policy workbench',`<form id="evaluate" class="panel-body"><p class="section-note">Inspect a proposed request against mandatory protections and its session's mission.</p><div class="fields"><label>Tool name<input name="tool_name" value="terminal" required></label><label>Session identity<input name="session_id" placeholder="Exact session ID, if available"></label></div><label>Tool arguments · JSON<textarea name="args" rows="5" spellcheck="false">{ "command": "git status" }</textarea></label><button>Evaluate operation</button><p class="section-note">Evaluation is a dry run. It does not execute the tool or grant authorization.</p></form>`, '<span class="label">DRY RUN</span>')}</div><div class="guard-decision">${panel('Decision explanation',`<div class="panel-body"><div id="evaluation-summary">${evaluationMarkup()}</div><details class="metadata" data-disclosure="evaluation-raw"><summary>Inspect raw decision JSON</summary><pre id="evaluation-result" tabindex="0" aria-live="polite">${state.evaluation?esc(JSON.stringify(state.evaluation,null,2)):'No evaluation yet.'}</pre></details></div>`)}</div><div class="guard-rules">${panel('Operator rules',`<form id="policy-form" class="panel-body"><p class="section-note">Add restrictions using tool-name globs. Rules may BLOCK or require native approval; they cannot override a mandatory denial.</p><label>Rules · JSON array<textarea name="rules" rows="9" spellcheck="false">${esc(JSON.stringify(state.policies,null,2))}</textarea></label><button>Validate &amp; save rules</button><p class="section-note">Required: id, priority, enabled, tools, decision, reason. Saving changes subsequent requests; it does not alter past events.</p></form>`)}</div><div class="guard-boundary">${panel('Mandatory protections',`<div class="panel-body">${['Destructive shell operations','Secret and sensitive paths','Privilege escalation','Repository mutations','Deployment and financial activity','Mission directory and tool scope'].map(t=>`<div class="row"><span>${t}</span><span class="label">POLICY</span></div>`).join('')}<p class="hint">Trusted hooks, not an OS sandbox. Mission permissions never relax mandatory protections.</p></div>`)}</div></div>`;}
function missionActions(m){
  const expired=missionActivationBlocked(m),conflict=state.missions.some(other=>other.id!==m.id&&other.session_id===m.session_id&&other.status==='ACTIVE');
  const targets={DRAFT:['ACTIVE','CANCELLED'],ACTIVE:['PAUSED','COMPLETED','CANCELLED'],PAUSED:['ACTIVE','COMPLETED','CANCELLED'],COMPLETED:['ACTIVE','CANCELLED'],CANCELLED:['ACTIVE']}[m.status]||[];
  return `<div class="actions">${targets.map(target=>`<button class="secondary small" data-mission="${esc(m.id)}" data-status="${target}" ${(target==='ACTIVE'&&(expired||conflict))?'disabled':''}>${target==='ACTIVE'?(m.status==='COMPLETED'||m.status==='CANCELLED'?'Reactivate':'Activate'):target==='PAUSED'?'Pause':target==='COMPLETED'?'Complete':'Cancel'}</button>`).join('')}</div>${expired&&m.status!=='ACTIVE'?'<p class="section-note">Activation unavailable: the stored expiration has passed or is invalid. Create a new draft with a reviewed expiry.</p>':''}${conflict&&m.status!=='ACTIVE'?'<p class="section-note">Activation unavailable: another active mission is associated with this session. Pause or complete it first.</p>':''}`;
}
function missions(){return `<div class="grid"><div>${panel('Mission registry',state.missions.length?state.missions.map(m=>`<article class="item"><div class="item-head"><div><h3>${esc(m.name)}</h3><code>${esc(m.id)}</code></div>${badge(missionState(m))}</div>${missionState(m)!==m.status?'<p class="hint">Recorded status is ACTIVE, but the expiry prevents further mission execution. Update its expiration before reactivating.</p>':''}<p>${esc(m.description||'No description')}</p><dl class="facts"><dt>Session</dt><dd><code>${esc(m.session_id||'Unassigned')}</code></dd><dt>Expires</dt><dd>${esc(m.expires_at?date(m.expires_at):'Not set')}</dd><dt>Allowed roots</dt><dd><code>${esc((m.display_allowed_directories||m.allowed_directories||[]).map(compactPath).join(', ')||'No mission path restriction')}</code></dd><dt>Approved tools</dt><dd><code>${permissionList(m.approved_tools,'No tools configured')}</code></dd></dl><details class="metadata" data-disclosure="mission-${esc(m.id)}"><summary>Full authority &amp; identifiers</summary><dl><dt>Allowed paths</dt><dd><code>${permissionList(m.allowed_directories,'No mission path restriction')}</code></dd><dt>Restricted paths</dt><dd><code>${permissionList(m.restricted_directories)}</code></dd><dt>Restricted tools</dt><dd><code>${permissionList(m.restricted_tools)}</code></dd><dt>Network domains</dt><dd><code>${permissionList(m.allowed_domains,'No explicit destinations permitted')}</code></dd></dl></details>${missionActions(m)}</article>`).join(''):empty('No missions configured','Create a bounded assignment using the form. Mission authority is enforced by the backend.'),`<span class="label">${state.missions.length} RECORDED</span>`)}</div><aside><section class="panel"><details class="creation-disclosure" data-disclosure="mission-creation" ${!state.missions.length?'open':''}><summary>Create a draft mission</summary><form id="mission-form" class="panel-body"><fieldset><legend>01 / ASSIGNMENT</legend><label>Mission name<input name="name" required placeholder="Investigate a build failure"></label><label>Session ID<input name="session_id" required placeholder="Exact Hermes session identifier"></label><label>Description<textarea name="description" placeholder="Describe the assignment and its boundaries"></textarea></label><label>Template<select name="template">${Object.entries(templates).map(([key,t])=>`<option value="${key}">${esc(t.name)}</option>`).join('')}</select></label></fieldset><fieldset><legend>02 / FILE AUTHORITY</legend><label>Allowed directories · one per line<textarea name="allowed_directories" required placeholder="Absolute workspace path"></textarea></label><label>Restricted directories · one per line<textarea name="restricted_directories" placeholder="Protected absolute paths"></textarea></label></fieldset><fieldset><legend>03 / TOOL &amp; NETWORK AUTHORITY</legend><label>Approved tools · comma separated<input name="approved_tools" value="terminal, read_file, write_file, search_files, patch"></label><label>Restricted tools · comma separated<input name="restricted_tools" placeholder="Optional restricted tool names"></label><label>Network domains · comma separated<input name="network_domains" placeholder="Explicitly permitted destinations"></label><p class="hint">Templates narrow permissions; they do not bypass mandatory policy. Unconfined shell execution may be blocked.</p></fieldset><fieldset><legend>04 / EXPIRATION</legend><label>Expiration<input name="expires_at" type="datetime-local" required></label><p class="section-note">Expiration prevents future mission calls. It does not cancel a running tool.</p></fieldset><button>Create draft mission</button></form></details></section></aside></div>`;}
function checkpointAdvice(c){return {OPEN:'Seal the observed file state before restoring.',SEALED:'Ready for an authorized restore; current-file and backup hashes will be checked.',RESTORED:'Already restored. This checkpoint cannot be restored again.',RESTORING:'A restoration claim is in progress. Inspect the file before taking further action.',FAILED:'Restoration failed. Inspect file state and recorded details before proceeding.'}[c.status]||'This checkpoint is not ready for restoration.';}
function recovery(){return `<div class="grid"><div>${panel('Checkpoint ledger',state.checkpoints.length?state.checkpoints.map(c=>`<article class="item"><div class="item-head"><div><h3>${esc(c.display_path||compactPath(c.path||c.file_path))}</h3>${c.display_path?'<small>Workspace-relative path</small>':''}<code>${esc(c.id||c.checkpoint_id)}</code></div>${badge(c.status||c.restoration_status||'checkpoint')}</div><dl class="facts"><dt>Created</dt><dd>${esc(date(c.timestamp||c.created_at))}</dd>${c.restored_at?`<dt>Restored</dt><dd>${esc(date(c.restored_at))}</dd>`:''}<dt>Session</dt><dd><code>${esc(c.session_id||c.identity?.session_id||'Unattributed')}</code></dd></dl><details class="metadata" data-disclosure="checkpoint-${esc(c.id)}"><summary>File path &amp; integrity hashes</summary><dl><dt>File</dt><dd><code>${esc(c.display_path||c.path||c.file_path)}</code></dd><dt>Original hash</dt><dd><code>${esc(c.original_hash||c.original_content_hash||c.before_hash||'New file checkpoint')}</code></dd><dt>Post-write hash</dt><dd><code>${esc(c.post_hash||'Not sealed')}</code></dd></dl></details><p class="section-note">${esc(checkpointAdvice(c))}</p><div class="actions">${c.status==='OPEN'?`<button class="secondary small" data-seal="${esc(c.id)}">Seal current file state</button>`:''}<button class="danger small" data-restore="${esc(c.id||c.checkpoint_id)}" ${c.status!=='SEALED'?'disabled':''}>Restore checkpoint</button></div></article>`).join(''):empty('No recovery checkpoints','Supported file operations create checkpoints through the runtime integration. No files have been restored.'),`<span class="label">${state.checkpoints.length} RECORDED</span>`)}</div><aside>${panel('Manual checkpoint',`<form id="checkpoint-form" class="panel-body"><p class="section-note">Capture an original file before a controlled change, then seal the observed result.</p><label>File path<input name="path" required placeholder="Path inside the configured workspace"></label><button>Create checkpoint</button><p class="hint">Only individual workspace files are supported. Symlinks and Sentinel state are rejected.</p></form>`)}${panel('Restoration boundary',`<div class="panel-body"><p class="section-note">Restoring requires explicit confirmation and backend conflict checks. Newer edits are not silently overwritten.</p><p class="hint">Original bytes are not exposed through this interface. Hashes are available; a content diff is not.</p><p class="section-note">External APIs, deployments, database changes, emails and arbitrary shell side effects cannot be undone.</p></div>`)}</aside></div>`;}
function mesh(){return `<div class="mesh-layout">${panel('Observed session registry',`<p class="registry-note">Sessions derived from persisted events. No parent-child topology is inferred when the host has not recorded those relationships. “Observed” does not mean a process is live.</p>${state.sessions.length?`<div class="mesh-grid">${state.sessions.map(session=>`<article class="session-card"><div class="item-head"><h3>${esc(session.agent_id||'Recorded session')}</h3>${badge(session.status||'recorded')}</div><code class="session-id" title="${esc(session.session_id||session.id)}">${esc(session.session_id||session.id)}</code><dl class="facts"><dt>Last event</dt><dd>${esc(date(session.last_seen||session.updated_at))}</dd><dt>Events</dt><dd>${esc(session.event_count??'Not reported')}</dd><dt>Event type</dt><dd><code>${esc(session.last_event||'Not recorded')}</code></dd><dt>Mission</dt><dd><code>${esc(session.mission_id||'No recorded association')}</code></dd></dl><details class="metadata" data-disclosure="session-${esc(session.session_id||session.id)}"><summary>Full session identity</summary><code>${esc(session.session_id||session.id)}</code><p class="section-note">Agent: ${esc(session.agent_id||'Not supplied by the host')}</p></details><div class="actions"><button class="secondary small" data-session="${esc(session.session_id||session.id)}">Investigate session ↗</button></div></article>`).join('')}</div>`:empty('No sessions recorded','The registry is populated from actual runtime events. A connected dashboard alone does not mean Hermes is active.')}`,`<span class="label">${state.sessions.length} OBSERVED</span>`)}</div>`;}
function settings(){return `<div class="grid settings-grid"><div>${panel('Local service connection',`<form id="connect-form" class="panel-body connection-form"><p class="section-note">Use the token printed by this local server. It is kept in this tab's session storage and sent only to this origin.</p><label>Service token<input name="token" type="password" autocomplete="off" required placeholder="Paste the local service token" value=""></label><button>Connect service</button> <button type="button" class="secondary" id="disconnect">Disconnect</button><p class="hint">Disconnecting the browser does not disable runtime enforcement. This interface never modifies the primary Hermes profile.</p></form>`)}<section class="panel danger-panel"><div class="panel-title"><h2>Event retention</h2><span class="label">DESTRUCTIVE</span></div><form id="retention-form" class="panel-body connection-form"><p class="section-note">Permanently remove records older than the selected date. Confirmation is required. Checkpoints and tool effects are not removed or undone.</p><label>Delete events recorded before<input name="before" type="datetime-local" required></label><button class="danger">Delete older events</button></form></section></div><aside>${panel('Connection diagnostics',`<div class="panel-body"><p class="section-note">${state.connected?'Authenticated local snapshot.':'Offline. Diagnostics below are the last authenticated snapshot, if available.'}</p><div class="row"><span>Browser transport</span>${badge(state.connected?'connected':'offline')}</div><div class="row"><span>Service endpoint</span><code>${esc(location.origin)}</code></div><div class="row"><span>Service version</span><code>${esc(state.status.version||'Unavailable')}</code></div><div class="row"><span>SQLite journal</span><code>${esc(state.status.stats?.journal_mode||'Unavailable')}</code></div><div class="row"><span>Approval transport</span><code>${esc(state.status.approval_transport||'Not reported')}</code></div><p class="hint">Dashboard connectivity is not a runtime-health assertion. Inspect Hermes' plugin diagnostics to verify loading.</p><p class="section-note">Recorded events, policies, missions and checkpoint originals remain local. Keep the token and state directory private.</p></div>`)}</aside></div>`;}
function saveDisclosures(){state.disclosures ||= Object.create(null);document.querySelectorAll('#content details[data-disclosure]').forEach(el=>{state.disclosures[el.dataset.disclosure]=el.open;});}
function restoreDisclosures(){document.querySelectorAll('#content details[data-disclosure]').forEach(el=>{if(Object.hasOwn(state.disclosures||{},el.dataset.disclosure))el.open=state.disclosures[el.dataset.disclosure];});}
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
  if(preserveDrafts){saveDrafts();saveDisclosures();}
  const enteredToken=preserveDrafts&&$('#connect-form')?.elements.namedItem('token')?.value;
  const r=route(),v=views[r],focused=document.activeElement,focusId=focused?.id,focusForm=focused?.form?.id,focusName=focused?.name,focusKey=['event','mission','restore','seal','session'].find(key=>focused?.dataset?.[key]),focusValue=focusKey?focused.dataset[focusKey]:null,focusStatus=focused?.dataset?.status;
  const selection=focused && typeof focused.selectionStart==='number'?[focused.selectionStart,focused.selectionEnd]:null;
  $('#section-label').textContent=v[0]; $('#page-title').textContent=v[1]; $('#page-description').textContent=v[2];
  document.querySelectorAll('nav a').forEach(a=>{const active=a.hash===`#${r}`;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  $('#content').dataset.view=r;
  $('#content').innerHTML=r==='overview'?overview():r==='guard'?guard():r==='watch'||r==='replay'?panel(r==='watch'?'Live event stream':'Recorded execution timeline',toolbar()+`<div class="stream-note ${state.connected?'':'stale'}"><i aria-hidden="true"></i>${r==='replay'?'HISTORICAL RECORDS / READ ONLY':state.connected?'POLLING PERSISTED EVENTS / 3 SECOND SYNC':'OFFLINE / LAST RECORDED SNAPSHOT'}</div>`+historyNote()+eventFeed()+(r==='replay'?`<div class="panel-body"><button id="load-history" class="secondary" ${state.replay.busy||!state.replay.more?'disabled':''}>${state.replay.busy?'Loading history…':state.replay.more?'Load next page':'End of recorded history'}</button></div>`:''),`<span class="label">${r==='watch'?'3 SECOND SYNC':'READ ONLY'}</span>`):r==='missions'?missions():r==='recovery'?recovery():r==='mesh'?mesh():settings();
  state.newEventSeqs=[];state.changedMetrics=[];
  state.missionClock=missionClock();restoreDrafts();restoreDisclosures();if(enteredToken&&$('#connect-form'))$('#connect-form').elements.namedItem('token').value=enteredToken;bind();state.needsRender=false;
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
  const wasLoaded=state.eventsLoaded;
  const existing=new Set(state.events.map(e=>e.seq));
  const unique=incoming.filter(e=>!existing.has(e.seq));
  state.newEventSeqs=wasLoaded?unique.map(e=>e.seq):[];
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
    const priorMetrics=overviewValues(),hadSnapshot=state.connected;
    state.status=snapshot.status;state.policies=snapshot.policies;
    for(const key of Object.keys(templates))delete templates[key];Object.assign(templates,snapshot.templates);
    mergeEvents(snapshot.events);state.sessions=snapshot.sessions;state.missions=snapshot.missions;state.checkpoints=snapshot.checkpoints;state.connected=true;
    const nextMetrics=overviewValues();state.changedMetrics=hadSnapshot?Object.keys(nextMetrics).filter(key=>nextMetrics[key]!==priorMetrics[key]):[];
    if(state.noticeKind==='connection'||!quiet)notice('');
    $('#last-update').textContent=`LAST SYNC ${new Date().toLocaleTimeString([], {hour12:false})}`;
    // Form drafts survive polling; do not dismiss a focused native select or move an open dialog's focus.
    if((!quiet||state.needsRender) && !$('#details').open && document.activeElement?.tagName!=='SELECT')render();
    return true;
  } catch(error) {
    if(generation===state.generation){state.connected=false;state.needsRender=true;notice(`Service unavailable: ${error.message}. Recorded data may be stale.`,'connection');if(!$('#details').open&&document.activeElement?.tagName!=='SELECT')render();}
    return false;
  } finally {
    state.busy=false;$('#refresh').disabled=false;$('#refresh').textContent='↻ Refresh';updateConnection();
    if(state.pendingRefresh){state.pendingRefresh=false;queueMicrotask(()=>refresh({quiet:true}));}
  }
}
function updateConnection(){ $('#connection').textContent=state.connected?'SERVICE CONNECTED':'DISCONNECTED';$('#connection').classList.toggle('offline',!state.connected);const version=$('#service-version');if(version)version.textContent=state.status.version?'v'+state.status.version:'VERSION —'; }
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
    await api(path,body);if(formId)forgetDraft(formId);const synced=await refresh({quiet:true});if(success)notice(success+(synced?'':' Refresh to verify the recorded state.'),'success');return true;
  }catch(error){notice(error.message,'error');return false;}
}
async function submitting(form,action){
  if(form.dataset.submitting==='true')return;
  form.dataset.submitting='true';const buttons=[...form.querySelectorAll('button[type="submit"],button:not([type])')];buttons.forEach(b=>b.disabled=true);
  try{await action();}catch(error){notice(error.message,'error');}finally{delete form.dataset.submitting;buttons.forEach(b=>b.disabled=false);}
}
function disconnect(){
  state.generation++;state.token='';state.connected=false;state.status={};state.events=[];state.cursor=0;state.eventsLoaded=false;state.dropped=0;state.sessions=[];state.missions=[];state.checkpoints=[];state.policies=[];state.drafts={};state.disclosures={};state.evaluation=null;resetReplay();
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
  const connect=$('#connect-form');if(connect)connect.onsubmit=e=>{e.preventDefault();submitting(connect,async()=>{const token=String(new FormData(connect).get('token')||'').trim();if(!token)throw Error('Enter the local service token.');connect.elements.namedItem('token').value='';state.generation++;state.token=token;state.events=[];state.cursor=0;state.eventsLoaded=false;state.dropped=0;resetReplay();try{sessionStorage.setItem('sentinel-token',token);}catch{}await refresh();});};
  const disconnectButton=$('#disconnect');if(disconnectButton)disconnectButton.onclick=disconnect;
  const policy=$('#policy-form');if(policy)policy.onsubmit=e=>{e.preventDefault();submitting(policy,async()=>{const rules=JSON.parse(new FormData(policy).get('rules'));if(!Array.isArray(rules))throw Error('Rules must be a JSON array.');await mutate('/api/policies',{rules},{formId:policy.id,success:'Validated policy rules saved. Subsequent operations use the new rules.'});});};
  const evaluate=$('#evaluate');if(evaluate)evaluate.onsubmit=e=>{e.preventDefault();submitting(evaluate,async()=>{const form=new FormData(evaluate),args=JSON.parse(form.get('args'));if(!args||typeof args!=='object'||Array.isArray(args))throw Error('Arguments must be a JSON object.');state.evaluation=await api('/api/evaluate',{tool_name:form.get('tool_name'),args,identity:{session_id:form.get('session_id')}});const output=$('#evaluation-result');if(output)output.textContent=JSON.stringify(state.evaluation,null,2);const summary=$('#evaluation-summary');if(summary)summary.innerHTML=evaluationMarkup();notice('');});};
  const mission=$('#mission-form');
  if(mission){
    mission.elements.template.onchange=()=>{const template=templates[mission.elements.template.value];if(!template)return;mission.dataset.dirty='true';mission.elements.approved_tools.value=(template.approved_tools||[]).join(', ');mission.elements.restricted_tools.value=(template.restricted_tools||[]).join(', ');mission.elements.network_domains.value=(template.allowed_domains||[]).join(', ');};
    mission.onsubmit=e=>{e.preventDefault();submitting(mission,async()=>{const f=new FormData(mission),body={name:f.get('name'),description:f.get('description'),session_id:f.get('session_id'),template:f.get('template'),status:'DRAFT',allowed_directories:split(f.get('allowed_directories')),restricted_directories:split(f.get('restricted_directories')),approved_tools:split(f.get('approved_tools')),restricted_tools:split(f.get('restricted_tools')),allowed_domains:split(f.get('network_domains')),allow_deployment:false,expires_at:new Date(f.get('expires_at')).toISOString()};await mutate('/api/missions',body,{formId:mission.id,success:'Mission saved as draft. Activate it when its scope is ready.'});});};
  }
  document.querySelectorAll('[data-mission]').forEach(b=>b.onclick=async()=>{b.disabled=true;await mutate(`/api/missions/${encodeURIComponent(b.dataset.mission)}`,{status:b.dataset.status},{success:'Mission status updated.'});b.disabled=false;});
  document.querySelectorAll('[data-restore]').forEach(b=>b.onclick=async()=>{if(!confirm('Restore this checkpoint? The backend will reject changed files or invalid checkpoint data. This changes the local file.'))return;b.disabled=true;await mutate('/api/restore',{id:b.dataset.restore,authorized:true},{success:'Checkpoint restored.'});b.disabled=false;});
  document.querySelectorAll('[data-session]').forEach(b=>b.onclick=()=>{state.session=b.dataset.session;resetReplay();if(route()==='replay')loadReplay();else location.hash='replay';});
}
function closeNavigation(returnFocus=true){document.body.dataset.navOpen='false';const toggle=$('#nav-toggle'),scrim=$('#nav-scrim');if(toggle){toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-label','Open module navigation');}const workspace=document.querySelector('.workspace-shell');if(workspace)workspace.inert=false;if(scrim)scrim.hidden=true;if(returnFocus&&toggle)toggle.focus();}
const navigationToggle=$('#nav-toggle');if(navigationToggle)navigationToggle.onclick=()=>{const open=document.body.dataset.navOpen!=='true';document.body.dataset.navOpen=String(open);navigationToggle.setAttribute('aria-expanded',String(open));navigationToggle.setAttribute('aria-label',open?'Close module navigation':'Open module navigation');const workspace=document.querySelector('.workspace-shell');if(workspace)workspace.inert=open;const scrim=$('#nav-scrim');if(scrim)scrim.hidden=!open;if(open){const first=document.querySelector('nav a');if(first)first.focus();}};
const navigationClose=$('#nav-close');if(navigationClose)navigationClose.onclick=()=>closeNavigation();
window.addEventListener('resize',()=>{if(window.innerWidth>900)closeNavigation(false);});
document.querySelectorAll('nav a').forEach(link=>{link.onclick=()=>{closeNavigation(false);$('#page-title').focus({preventScroll:true});window.scrollTo?.({top:0,behavior:'instant'});};});
const navigationScrim=$('#nav-scrim');if(navigationScrim)navigationScrim.onclick=()=>closeNavigation();
const collapseToggle=$('#collapse-nav');if(collapseToggle)collapseToggle.onclick=()=>{const collapsed=document.body.dataset.navCollapsed!=='true';document.body.dataset.navCollapsed=String(collapsed);collapseToggle.setAttribute('aria-expanded',String(!collapsed));collapseToggle.setAttribute('aria-label',collapsed?'Expand sidebar':'Collapse sidebar');};
window.addEventListener('keydown',event=>{if(document.body.dataset.navOpen!=='true')return;if(event.key==='Escape'){event.preventDefault();closeNavigation();}if(event.key==='Tab'){const targets=[...document.querySelectorAll('#sidebar a, #sidebar button')].filter(el=>!el.getClientRects||el.getClientRects().length);if(!targets.length)return;const first=targets[0],last=targets[targets.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
$('.skip').onclick=event=>{event.preventDefault();$('#main').focus();};
$('#refresh').onclick=()=>refresh().then(()=>{if(route()==='replay')loadReplay(true);});
$('#close-details').onclick=()=>$('#details').close();
$('#details').addEventListener('close',()=>{render();const trigger=[...document.querySelectorAll('[data-event]')].find(el=>el.dataset.event===detailEventId);if(trigger)trigger.focus();else $('#page-title').focus();});
window.addEventListener('hashchange',()=>{closeNavigation(false);clearTimeout(searchTimer);notice('');render();$('#page-title').focus({preventScroll:true});window.scrollTo?.({top:0,behavior:'instant'});if(route()==='replay'&&(!state.replay.loaded||state.replay.query!==state.query||state.replay.session!==state.session))loadReplay();});
function tick(){$('#clock').textContent=new Date().toLocaleTimeString([], {hour12:false});if(state.missionClock!==missionClock()){state.needsRender=true;if(['overview','missions'].includes(route())&&!$('#details').open&&document.activeElement?.tagName!=='SELECT')render();}}
tick();setInterval(tick,1000);render();refresh().then(()=>{if(route()==='replay')loadReplay();});setInterval(()=>refresh({quiet:true}),3000);
