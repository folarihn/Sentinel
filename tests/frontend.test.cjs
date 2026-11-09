'use strict';
// Dependency-free DOM contract tests. Real browser layout/interaction QA is separate.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../sentinel/web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../sentinel/web/index.html'), 'utf8');
const decode = text => String(text || '').replace(/&(?:quot|#39|lt|gt|amp);/g, x => ({'&quot;':'"','&#39;':"'",'&lt;':'<','&gt;':'>','&amp;':'&'}[x]));
const attrs = text => Object.fromEntries([...text.matchAll(/([\w-]+)="([^"]*)"/g)].map(([, k, v]) => [k, decode(v)]));

function harness({storageError = false, hash = '#overview'} = {}) {
  const ids = new Map(), all = [], timers = new Map(), calls = [], downloads = [], storage = new Map(), listeners={};
  let nextTimer = 0, responder = () => { throw Error('Unexpected request'); };
  const document = {activeElement:null};
  class Element {
    constructor(tag = 'div', attributes = {}, text = '') {
      this.tagName = tag.toUpperCase(); this.id = attributes.id || ''; this.name = attributes.name || ''; this.type = attributes.type || ''; this.value = attributes.value || text;
      this.dataset = {}; this.listeners = {}; this.textContent = text; this.disabled = false; this.open = false; this.html = ''; this.children = [];
      this.attributes = attributes; this.classList = {toggle(){}};
      for (const [key, value] of Object.entries(attributes)) if(key.startsWith('data-')) this.dataset[key.slice(5)] = value;
      if(this.id) ids.set(this.id, this);
    }
    set innerHTML(value) { this.html = value; if(this.id === 'content') parseContent(value); }
    get innerHTML() { return this.html; }
    addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
    setAttribute(k, v) { this.attributes[k] = v; }
    removeAttribute(k) { delete this.attributes[k]; }
    focus() { document.activeElement = this; }
    setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
    querySelectorAll() { return this.children.filter(e => e.tagName === 'BUTTON'); }
    showModal() { this.open = true; }
    close() { this.open = false; for(const fn of this.listeners.close || []) fn(); }
    click() { if(this.tagName === 'A' && this.download) downloads.push(this); if(this.onclick) return this.onclick({preventDefault(){}}); }
    remove() {}
    appendChild(child) { this.children.push(child); }
  }
  function register(tag, attributes, text = '') { const el = new Element(tag, attributes, text); all.push(el); return el; }
  function parseContent(value) {
    for(const element of all.splice(0)) if(element.id) ids.delete(element.id);
    for(const match of value.matchAll(/<(form|input|textarea|select|button|pre|div|details)\b([^>]*)>/g)) {
      const [, tag, raw] = match, attributes = attrs(raw); if(!attributes.id && !attributes['data-event'] && !attributes['data-mission'] && !attributes['data-restore'] && !attributes['data-seal'] && !attributes['data-disclosure']) continue;
      const parsed=register(tag, attributes);if(tag==='details')parsed.open=/\bopen\b/.test(raw);
    }
    for(const match of value.matchAll(/<form\b([^>]*)>([\s\S]*?)<\/form>/g)) {
      const form = ids.get(attrs(match[1]).id); if(!form) continue;
      form.elements = []; form.elements.namedItem = name => form.elements.find(e => e.name === name) || null;
      for(const field of match[2].matchAll(/<(input)\b([^>]*)>|<(textarea|select|button)\b([^>]*)>([\s\S]*?)<\/\3>/g)) {
        const tag=field[1]||field[3],raw=field[2]||field[4],body=field[5], attributes = attrs(raw), el = new Element(tag, attributes, tag === 'textarea' ? decode(body) : '');
        if(tag === 'select') el.value = attrs((body || '').match(/<option\b([^>]*)>/)?.[1] || '').value || '';
        el.form = form;form.elements.push(el);if(el.name)form.elements[el.name]=el;form.children.push(el);
      }
    }
  }
  for(const id of ['main','notice','content','section-label','page-title','page-description','connection','last-update','clock','refresh','close-details','detail-content','details','nav-toggle','nav-scrim','collapse-nav','service-version','sidebar']) ids.set(id,new Element('div',{id}));
  const navigation=[...html.matchAll(/<a href="#(overview|guard|watch|replay|missions|recovery|mesh|settings)"([^>]*)>/g)].map(match=>{const node=new Element('a',attrs('href="#'+match[1]+'" '+match[2]));node.hash='#'+match[1];return node;});
  const skip = new Element('a'); document.body = new Element('body');
  document.getElementById = id => ids.get(id) || null;
  document.querySelector = selector => selector === '.skip' ? skip : selector === 'nav a' ? navigation[0] : selector.startsWith('#') ? ids.get(selector.slice(1)) || null : null;
  document.querySelectorAll = selector => ['nav a','#sidebar a'].includes(selector) ? navigation : selector === '#content details[data-disclosure]' ? all.filter(e=>e.tagName==='DETAILS'&&Object.hasOwn(e.dataset,'disclosure')) : selector === 'form[data-dirty="true"]' ? all.filter(e => e.tagName === 'FORM' && e.dataset.dirty === 'true') : selector === '#content form' ? all.filter(e => e.tagName === 'FORM') : selector.startsWith('[data-') ? all.filter(e => Object.hasOwn(e.dataset, selector.slice(6,-1))) : [];
  document.createElement = tag => new Element(tag);
  const context = vm.createContext({document, location:{hash,origin:'http://127.0.0.1:8765',pathname:'/',search:''}, window:{addEventListener(name,callback){listeners[name]=callback;}},
    sessionStorage:{getItem:key=>{if(storageError)throw Error('Storage denied');return storage.get(key)||null;},setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    FormData:class {constructor(form){this.form=form;}get(name){return this.form.elements.namedItem(name)?.value || '';}},
    fetch:async (url, options) => { calls.push({url,options}); return responder(url, options); },
    AbortController, URLSearchParams, Blob, URL:{createObjectURL:blob=>{context.exportedBlob=blob;return 'blob:fixture';},revokeObjectURL(){}},
    setInterval(){}, setTimeout:(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),queueMicrotask,console,confirm:()=>true
  });
  vm.runInContext(source, context);
  return {context, ids, all, calls, timers, downloads, skip, document, run:code=>vm.runInContext(code,context), respond:fn=>responder=fn, navigate:value=>{context.location.hash='#'+value;listeners.hashchange();}, route:value=>{context.location.hash='#'+value;vm.runInContext('render()',context);}};
}
const json = (body,status=200) => ({ok:status>=200&&status<300,status,json:async()=>body});
const event = seq => ({seq,id:'e'+seq,event_type:'tool_call_allowed',timestamp:'2026-11-05T12:00:00Z',session_id:'s1',tool_name:'terminal'});
function service(url) {
  if(url === '/api/status')return json({stats:{events:1,by_type:{tool_call_allowed:1}}});
  if(url.startsWith('/api/events'))return json([event(1)]);
  if(url === '/api/templates')return json({'safe-coding':{name:'Safe Coding',approved_tools:['terminal'],restricted_tools:[],allowed_domains:[]}});
  if(url === '/api/policies')return json({rules:[]});
  return json([]);
}

test('all eight views render truthful empty states and survive unavailable session storage', () => {
  const ui=harness({storageError:true});
  for(const route of ['overview','guard','watch','replay','missions','recovery','mesh','settings']){ui.route(route);assert.ok(ui.ids.get('content').innerHTML.length>100,route);}
  ui.route('overview');assert.match(ui.ids.get('content').innerHTML,/Awaiting connection/);assert.doesNotMatch(ui.ids.get('content').innerHTML,/Hermes connected/i);
});

test('event payloads and attributes are escaped, and search filters actual loaded records', () => {
  const ui=harness();ui.run(`state.events=[{...${JSON.stringify(event(1))},tool_name:'<script>alert(1)</script>',reason:'synthetic fixture'}]`);ui.route('watch');
  assert.match(ui.ids.get('content').innerHTML,/&lt;script&gt;/);assert.doesNotMatch(ui.ids.get('content').innerHTML,/<script>/);
  ui.run("state.query='missing'");assert.equal(ui.run('filteredEvents().length'),0);
  ui.run("state.query='synthetic'");assert.equal(ui.run('filteredEvents().length'),1);
});

test('API sends bearer credentials only to relative local routes and rejects malformed/error JSON', async () => {
  const ui=harness();ui.run("state.token='local-fixture'");ui.respond(()=>json({decision:'BLOCK'}));
  await ui.run("api('/api/evaluate',{tool_name:'terminal',args:{command:'git status'}})");
  assert.equal(ui.calls[0].url,'/api/evaluate');assert.equal(ui.calls[0].options.headers.Authorization,'Bearer local-fixture');assert.equal(ui.calls[0].options.method,'POST');assert.equal(ui.calls[0].options.signal.aborted,false);
  await assert.rejects(ui.run("api('https://example.com/api/status')"),/Only local/);
  ui.respond(()=>json(null));await assert.rejects(ui.run("api('/api/status')"),/Invalid service response/);
  ui.respond(()=>json({error:'Authentication required'},401));await assert.rejects(ui.run("api('/api/status')"),/Authentication required/);
  ui.respond(()=>({ok:true,status:200,json:async()=>{throw Error('invalid');}}));await assert.rejects(ui.run("api('/api/status')"),/Invalid JSON/);
});

test('requests time out instead of holding refresh permanently busy', async () => {
  const ui=harness();ui.respond((url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>{const error=Error('aborted');error.name='AbortError';reject(error);})));const result=ui.run("api('/api/status')");
  [...ui.timers.values()].find(timer=>timer.delay===12000).fn();await assert.rejects(result,/timed out/);
});

test('event windows deduplicate and stay bounded while the independent cursor advances', () => {
  const ui=harness();ui.context.fixture=Array.from({length:2300},(_,i)=>event(i+1));ui.run('mergeEvents(fixture);mergeEvents(fixture.slice(-10))');
  assert.equal(ui.run('state.events.length'),2000);assert.equal(ui.run('state.cursor'),2300);assert.equal(ui.run('state.dropped'),300);assert.equal(ui.run('state.events[0].seq'),301);
});

test('quiet refresh updates mission state while preserving dirty mission fields and focus', async () => {
  const ui=harness();ui.respond(service);ui.run("state.token='fixture'");ui.route('missions');
  const form=ui.ids.get('mission-form');form.elements.name.value='Unsaved investigation';form.dataset.dirty='true';form.elements.name.focus();
  ui.respond(url=>url==='/api/missions'?json([{id:'m1',name:'Persisted mission',status:'PAUSED',session_id:'s1'}]):service(url));
  assert.equal(await ui.run('refresh({quiet:true})'),true);
  assert.match(ui.ids.get('content').innerHTML,/PAUSED/);assert.equal(ui.ids.get('mission-form').elements.name.value,'Unsaved investigation');assert.equal(ui.document.activeElement.name,'name');
  assert.ok(ui.calls.some(c=>c.url==='/api/events?tail=1'));
});

test('invalid network snapshots keep the previous journal and surface an actionable error', async () => {
  const ui=harness();ui.run(`state.token='fixture';state.events=[${JSON.stringify(event(4))}]`);ui.respond(url=>url==='/api/sessions'?json({unexpected:true}):service(url));
  assert.equal(await ui.run('refresh()'),false);assert.equal(ui.run('state.events[0].seq'),4);assert.equal(ui.run('state.busy'),false);assert.match(ui.ids.get('notice').textContent,/Invalid sessions/);
});

test('disconnect prevents an in-flight response from restoring authenticated data', async () => {
  const ui=harness();let resolveStatus;ui.respond(url=>url==='/api/status'?new Promise(resolve=>resolveStatus=resolve):service(url));ui.run("state.token='fixture'");const pending=ui.run('refresh()');
  ui.run('disconnect()');resolveStatus(json({stats:{events:1}}));await pending;
  assert.equal(ui.run('state.token'),'');assert.equal(ui.run('state.connected'),false);assert.equal(ui.run('state.events.length'),0);assert.equal(ui.ids.get('last-update').textContent,'Awaiting authenticated connection');
});

test('Replay queries persistent history with server-side session and search filters', async () => {
  const ui=harness();ui.run("state.token='fixture';state.session='s&1';state.query='git status'");ui.route('replay');ui.respond(()=>json([event(10)]));
  await ui.run('loadReplay(true)');const url=new URL(ui.calls.at(-1).url,'http://localhost');assert.equal(url.searchParams.get('session_id'),'s&1');assert.equal(url.searchParams.get('search'),'git status');
  assert.equal(ui.run('state.replay.events[0].seq'),10);assert.equal(ui.run('state.replay.more'),false);assert.equal(ui.run('state.events.length'),0);
});

test('failed Replay refresh retains loaded evidence and discloses stale records', async () => {
  const ui=harness();ui.run("state.token='fixture'");ui.route('replay');ui.respond(()=>json([event(1),event(2),event(3),event(4)]));await ui.run('loadReplay(true)');
  ui.respond(()=>{throw Error('Service stopped');});await ui.run('loadReplay(true)');
  assert.equal(ui.run('state.replay.events.length'),4);assert.equal(ui.run('state.replay.cursor'),4);assert.equal(ui.run('state.replay.stale'),true);assert.equal(ui.run('state.replay.busy'),false);
  assert.match(ui.ids.get('content').innerHTML,/4 records in this browser window/);assert.match(ui.ids.get('content').innerHTML,/Previously loaded records are retained and may be stale/);assert.match(ui.ids.get('notice').textContent,/Service stopped/);
  ui.respond(()=>json([event(9)]));await ui.run('loadReplay(true)');assert.equal(ui.run('state.replay.events.length'),1);assert.equal(ui.run('state.replay.events[0].seq'),9);assert.equal(ui.run('state.replay.stale'),false);
});

test('failed Replay filter change retries from the beginning rather than reusing another query cursor', async () => {
  const ui=harness();ui.run("state.token='fixture'");ui.route('replay');ui.respond(()=>json([event(20)]));await ui.run('loadReplay(true)');
  ui.run("state.query='new filter'");ui.respond(()=>{throw Error('Offline');});await ui.run('loadReplay(true)');assert.equal(ui.run('state.replay.events[0].seq'),20);
  ui.respond(()=>json([event(3)]));await ui.run('loadReplay()');const request=new URL(ui.calls.at(-1).url,'http://localhost');assert.equal(request.searchParams.get('after'),'0');assert.equal(request.searchParams.get('search'),'new filter');assert.equal(ui.run('state.replay.events[0].seq'),3);
});

test('templates apply returned permissions and line/comma separation preserves path text', async () => {
  const ui=harness();ui.run("Object.assign(templates,{research:{name:'Research',approved_tools:['read_file'],restricted_tools:['terminal'],allowed_domains:['example.com']}})");ui.route('missions');const form=ui.ids.get('mission-form');form.elements.template.value='research';form.elements.template.onchange();
  assert.equal(form.elements.restricted_tools.value,'terminal');assert.equal(form.elements.network_domains.value,'example.com');assert.equal(form.dataset.dirty,'true');
  assert.equal(JSON.stringify(ui.run("split('C:/sentinel\\nD:/workspace, E:/another')")),JSON.stringify(['C:/sentinel','D:/workspace','E:/another']));
});

test('dialog has a programmatic name, keyboard activation, and returns focus after closing', () => {
  assert.match(html,/<dialog[^>]+aria-labelledby="details-title"/);assert.match(html,/<pre id="detail-content"[^>]+tabindex="0"/);
  const ui=harness();ui.run(`state.events=[${JSON.stringify(event(1))}]`);ui.route('watch');const trigger=ui.all.find(e=>e.dataset.event==='e1');let prevented=false;trigger.onkeydown({key:'Enter',preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(ui.ids.get('details').open,true);assert.equal(ui.document.activeElement.id,'close-details');ui.ids.get('details').close();assert.equal(ui.document.activeElement.dataset.event,'e1');
});

test('export includes filtered records and explicit scope without executing any operation', async () => {
  const ui=harness();ui.run(`state.events=[${JSON.stringify(event(1))}, {...${JSON.stringify(event(2))},session_id:'s2'}];state.session='s1'`);ui.route('watch');ui.run('exportReport()');
  const report=JSON.parse(await ui.context.exportedBlob.text());assert.equal(report.mode,'forensic_read_only');assert.equal(report.scope,'loaded_filtered_records');assert.equal(report.record_count,1);assert.equal(report.events[0].session_id,'s1');assert.equal(ui.calls.length,0);assert.equal(ui.downloads.length,1);
});

test('restore requires confirmation and unsealed checkpoints cannot be restored', () => {
  const ui=harness();ui.run("state.checkpoints=[{id:'open',path:'fixture',status:'OPEN'},{id:'sealed',path:'fixture',status:'SEALED'}]");ui.route('recovery');assert.match(ui.ids.get('content').innerHTML,/data-restore="open" disabled/);
  ui.context.confirm=()=>false;ui.all.find(e=>e.dataset.restore==='sealed').onclick();assert.equal(ui.calls.length,0);
});

test('skip navigation focuses the main region without changing the selected screen', () => {
  const ui=harness();ui.route('guard');let prevented=false;ui.skip.onclick({preventDefault(){prevented=true;}});assert.equal(prevented,true);assert.equal(ui.document.activeElement.id,'main');assert.equal(ui.context.location.hash,'#guard');
});

test('unknown and inherited-property routes safely resolve to Overview', () => {
  const ui=harness();for(const value of ['missing','constructor','toString','__proto__']){ui.route(value);assert.equal(ui.run('route()'),'overview');assert.equal(ui.ids.get('page-title').textContent,'Overview');}
});

test('disconnect clears unsaved form drafts and never echoes the stored bearer token', () => {
  const ui=harness();ui.route('missions');const form=ui.ids.get('mission-form');form.elements.name.value='Private draft';form.dataset.dirty='true';ui.run('disconnect()');assert.equal(Object.keys(ui.run('state.drafts')).length,0);assert.equal(ui.ids.get('mission-form').elements.name.value,'');
  ui.run("state.token='private-bearer-fixture'");ui.route('settings');assert.doesNotMatch(ui.ids.get('content').innerHTML,/private-bearer-fixture/);
});

test('export metadata does not expose potentially sensitive search text', async () => {
  const ui=harness();ui.run("state.query='private-query-fixture'");ui.run('exportReport()');const text=await ui.context.exportedBlob.text();assert.doesNotMatch(text,/private-query-fixture/);assert.equal(JSON.parse(text).search_applied,true);
});


test('returning from Watch to Replay reloads changed persistent query filters', async () => {
  const ui=harness();ui.run("state.token='fixture'");ui.route('replay');ui.respond(()=>json([event(10)]));await ui.run('loadReplay(true)');
  ui.route('watch');ui.run("state.query='different operation';state.session='s2'");ui.respond(()=>json([{...event(20),session_id:'s2'}]));ui.navigate('replay');
  await new Promise(resolve=>setImmediate(resolve));
  const query=new URL(ui.calls.at(-1).url,'http://localhost').searchParams;
  assert.equal(query.get('search'),'different operation');assert.equal(query.get('session_id'),'s2');assert.equal(query.get('after'),'0');
  assert.equal(ui.run('state.replay.events[0].seq'),20);assert.equal(ui.run('state.replay.query'),'different operation');
});

test('filtered empty results distinguish absent matches from an empty journal', () => {
  const ui=harness();ui.route('watch');assert.match(ui.ids.get('content').innerHTML,/No recorded activity/);
  ui.run("state.query='no match'");ui.route('watch');assert.match(ui.ids.get('content').innerHTML,/No matching events/);assert.doesNotMatch(ui.ids.get('content').innerHTML,/No recorded activity/);
  ui.route('replay');assert.match(ui.ids.get('content').innerHTML,/No matching events/);
});

test('event controls have distinct accessible names without argument contents', () => {
  const ui=harness();ui.run(`state.events=[${JSON.stringify(event(1))},${JSON.stringify(event(2))}]`);ui.route('watch');
  const labels=ui.all.filter(el=>el.dataset.event).map(el=>el.attributes['aria-label']);
  assert.equal(new Set(labels).size,2);assert.ok(labels.every(label=>label.includes('session s1')));assert.ok(labels.some(label=>label.includes('event 2')));
});

test('expired active missions are shown as expired and excluded from active counts', () => {
  const ui=harness();ui.run("state.missions=[{id:'expired',name:'Past mission',status:'ACTIVE',session_id:'s1',expires_at:'2000-01-01T00:00:00Z'}]");ui.route('missions');
  assert.match(ui.ids.get('content').innerHTML,/EXPIRED/);assert.match(ui.ids.get('content').innerHTML,/expiry prevents further mission execution/);
  ui.route('overview');assert.match(ui.ids.get('content').innerHTML,/No active mission/);assert.doesNotMatch(ui.ids.get('content').innerHTML,/Past mission/);
  assert.equal(ui.run("missionState({status:'ACTIVE',expires_at:'2000-01-01T00:00:00Z'})"),'EXPIRED');
});

test('Recovery prefers a derived workspace-relative display path without changing actual records', () => {
  const ui=harness();ui.run("state.checkpoints=[{id:'relative',path:'C:/local/workspace/example.txt',display_path:'example.txt',status:'SEALED'}]");ui.route('recovery');
  assert.match(ui.ids.get('content').innerHTML,/<h3>example.txt<\/h3>/);assert.match(ui.ids.get('content').innerHTML,/Workspace-relative path/);assert.doesNotMatch(ui.ids.get('content').innerHTML,/C:\/local/);
  assert.equal(ui.run('state.checkpoints[0].path'),'C:/local/workspace/example.txt');
});


test('mission expiry updates the visible state when the clock advances without a backend mutation', () => {
  const ui=harness();ui.run("state.missions=[{id:'clock',name:'Clock mission',status:'ACTIVE',session_id:'s1',expires_at:'2099-01-01T00:00:00Z'}]");ui.route('missions');
  assert.doesNotMatch(ui.ids.get('content').innerHTML,/EXPIRED/);ui.run("state.missions[0].expires_at='2000-01-01T00:00:00Z';tick()");assert.match(ui.ids.get('content').innerHTML,/EXPIRED/);
});

test('interface symbols preserve Unicode encoding', () => {
  assert.ok(source.includes('\u21bb'));assert.ok(source.includes('\u2197'));assert.ok(source.includes('\u2026'));assert.ok(!source.includes('\u00e2\u20ac'));
});


test('sidebar retains all eight routes and exposes active navigation state', () => {
  const ui=harness();assert.equal(ui.document.querySelectorAll('nav a').length,8);
  for(const route of ['overview','guard','watch','replay','missions','recovery','mesh','settings']){
    ui.navigate(route);const links=ui.document.querySelectorAll('nav a');assert.equal(links.filter(link=>link.attributes['aria-current']==='page').length,1);assert.equal(links.find(link=>link.attributes['aria-current']==='page').hash,'#'+route);
  }
});

test('mobile drawer opens accessibly, closes on navigation and Escape returns focus', () => {
  const ui=harness(),toggle=ui.ids.get('nav-toggle');toggle.onclick();assert.equal(toggle.attributes['aria-expanded'],'true');assert.equal(ui.document.body.dataset.navOpen,'true');
  ui.navigate('mesh');assert.equal(toggle.attributes['aria-expanded'],'false');assert.equal(ui.ids.get('nav-scrim').hidden,true);
  toggle.onclick();ui.run("closeNavigation()");assert.equal(ui.document.activeElement.id,'nav-toggle');assert.equal(ui.document.body.dataset.navOpen,'false');
  ui.ids.get('collapse-nav').onclick();assert.equal(ui.document.body.dataset.navCollapsed,'true');assert.equal(ui.ids.get('collapse-nav').attributes['aria-label'],'Expand sidebar');
});

test('Mesh keeps complete escaped identities in accessible details and a dedicated full-width layout', () => {
  const ui=harness(),id='session-'+('long-identifier-'.repeat(24))+'<script>';
  ui.context.longSession=id;ui.run("state.sessions=[{session_id:longSession,event_count:3,status:'observed'}]");ui.route('mesh');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/class="mesh-layout"/);assert.match(content,/class="mesh-grid"/);assert.match(content,/Full session identity/);assert.ok(content.includes(id.replace('<script>','&lt;script&gt;')));assert.doesNotMatch(content,/<script>/);assert.match(content,/No parent-child topology is inferred/);
  const css=fs.readFileSync(path.join(__dirname,'../sentinel/web/style.css'),'utf8');assert.match(css,/\.mesh-grid\{[^}]*grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);assert.match(css,/@media\(max-width:680px\)/);assert.match(css,/\.mesh-layout\{[^}]*width:100%/);
});

test('mission creation exposes grouped security scope and explains activation conflicts', () => {
  const ui=harness();ui.run("state.missions=[{id:'one',name:'Active',session_id:'same',status:'ACTIVE'},{id:'two',name:'Draft',session_id:'same',status:'DRAFT'}]");ui.route('missions');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/FILE AUTHORITY/);assert.match(content,/TOOL &amp; NETWORK AUTHORITY/);assert.match(content,/data-mission="two" data-status="ACTIVE" disabled/);assert.match(content,/another active mission/);assert.ok(ui.ids.get('mission-form').elements.namedItem('restricted_directories'));assert.ok(ui.ids.get('mission-form').elements.namedItem('expires_at'));
});

test('policy evaluation remains a dry run and renders escaped decision explanations', async () => {
  const ui=harness();ui.route('guard');ui.respond(()=>json({decision:'BLOCK',rule:'fixture-rule',reason:'<script>denied</script>'}));const form=ui.ids.get('evaluate');form.elements.tool_name.value='terminal';form.elements.args.value='{ "command": "rm -rf example" }';form.onsubmit({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.calls.length,1);assert.equal(ui.calls[0].url,'/api/evaluate');assert.match(ui.ids.get('evaluation-summary').innerHTML,/&lt;script&gt;/);assert.doesNotMatch(ui.ids.get('evaluation-summary').innerHTML,/<script>/);assert.match(ui.ids.get('content').innerHTML,/does not execute/);
});

test('Recovery discloses actual status, timestamps and hashes without a fabricated content diff', () => {
  const ui=harness();ui.run("state.checkpoints=[{id:'restored',display_path:'note.txt',path:'C:/private/note.txt',status:'RESTORED',original_hash:'abc',post_hash:'def',restored_at:'2026-11-05T12:00:00Z'}]");ui.route('recovery');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/Already restored/);assert.match(content,/Post-write hash/);assert.match(content,/abc/);assert.match(content,/def/);assert.match(content,/content diff is not/);assert.doesNotMatch(content,/C:\/private/);
});

test('disconnected overview does not invent totals or a healthy runtime', () => {
  const ui=harness();ui.route('overview');const content=ui.ids.get('content').innerHTML;assert.match(content,/Awaiting connection/);assert.match(content,/—/);assert.doesNotMatch(content,/Hermes connected|100%|risk score|uptime/i);
  ui.run("state.connected=true;state.status={stats:{events:4,by_type:{tool_call_blocked:2}}};state.sessions=[{session_id:'actual'}]");ui.route('overview');assert.match(ui.ids.get('content').innerHTML,/>4<\/strong>/);assert.match(ui.ids.get('content').innerHTML,/Runtime health is not attested/);
});

test('Settings never reveals bearer credentials and retention requires confirmation', async () => {
  const ui=harness();ui.run("state.token='synthetic-private-token';state.connected=true");ui.route('settings');assert.doesNotMatch(ui.ids.get('content').innerHTML,/synthetic-private-token/);assert.match(ui.ids.get('content').innerHTML,/does not disable runtime enforcement/);
  const form=ui.ids.get('retention-form');form.elements.before.value='2026-11-01T12:00';ui.context.confirm=()=>false;await form.onsubmit({preventDefault(){}});assert.equal(ui.calls.length,0);
});

test('new-event highlights apply only to new persisted records after an initial load', () => {
  const ui=harness();ui.context.page=[event(1)];ui.run('mergeEvents(page)');assert.equal(ui.run('state.newEventSeqs.length'),0);ui.context.page=[event(1),event(2)];ui.run('mergeEvents(page)');assert.equal(ui.run('state.newEventSeqs.join()'),'2');ui.route('watch');assert.match(ui.ids.get('content').innerHTML,/new-event/);ui.route('watch');assert.doesNotMatch(ui.ids.get('content').innerHTML,/new-event/);
});


test('selecting the already active mobile module also closes the drawer', () => {
  const ui=harness();ui.route('mesh');ui.ids.get('nav-toggle').onclick();ui.document.querySelectorAll('nav a').find(link=>link.hash==='#mesh').onclick();assert.equal(ui.document.body.dataset.navOpen,'false');assert.equal(ui.document.activeElement.id,'page-title');
});


test('mission disclosure and unsaved scope survive polling renders', () => {
  const ui=harness();ui.run("state.missions=[{id:'prior',name:'Prior',status:'COMPLETED'}]");ui.route('missions');const disclosure=ui.all.find(el=>el.dataset.disclosure==='mission-creation');disclosure.open=true;const form=ui.ids.get('mission-form');form.elements.name.value='Retained draft';form.dataset.dirty='true';ui.run('render()');assert.equal(ui.all.find(el=>el.dataset.disclosure==='mission-creation').open,true);assert.equal(ui.ids.get('mission-form').elements.name.value,'Retained draft');ui.run('disconnect()');assert.equal(ui.run('Object.keys(state.disclosures).length'),0);
});

test('successful authentication clears the password field while preserving tab-session auth', async () => {
  const ui=harness();ui.route('settings');ui.respond(service);const form=ui.ids.get('connect-form');form.elements.token.value='synthetic-auth-token';form.onsubmit({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));assert.equal(ui.run('state.token'),'synthetic-auth-token');assert.equal(ui.ids.get('connect-form').elements.token.value,'');assert.doesNotMatch(ui.ids.get('content').innerHTML,/synthetic-auth-token/);
});

test('motion is limited to real changes and can be disabled by reduced-motion preference', () => {
  const css=fs.readFileSync(path.join(__dirname,'../sentinel/web/style.css'),'utf8');assert.match(css,/@media\(prefers-reduced-motion:reduce\)\{[^]*animation:none!important/);assert.match(css,/\.metric-changed/);assert.match(css,/\.event\.new-event/);assert.doesNotMatch(css,/WebGL|canvas|backdrop-filter/);
});


test('expired draft activation is disabled with an actionable explanation', () => {
  const ui=harness();ui.run("state.missions=[{id:'expired-draft',name:'Expired draft',status:'DRAFT',expires_at:'2000-01-01T00:00:00Z'}]");ui.route('missions');assert.match(ui.ids.get('content').innerHTML,/data-mission="expired-draft" data-status="ACTIVE" disabled/);assert.match(ui.ids.get('content').innerHTML,/Create a new draft with a reviewed expiry/);
});


test('a failed poll immediately replaces connected labels with an offline retained snapshot', async () => {
  const ui=harness();ui.run(`state.token='fixture';state.connected=true;state.eventsLoaded=true;state.events=[${JSON.stringify(event(1))}];state.status={stats:{events:1}}`);ui.route('overview');assert.match(ui.ids.get('content').innerHTML,/Service connected/);ui.respond(()=>{throw Error('Service stopped');});await ui.run('refresh({quiet:true})');assert.equal(ui.run('state.events.length'),1);assert.match(ui.ids.get('content').innerHTML,/Offline. Last recorded snapshot retained/);assert.doesNotMatch(ui.ids.get('content').innerHTML,/Service connected/);ui.route('watch');assert.match(ui.ids.get('content').innerHTML,/OFFLINE \/ LAST RECORDED SNAPSHOT/);
});

const linked = () => `state.connected=true;state.eventsLoaded=true;state.status={stats:{events:5,by_type:{tool_call_allowed:1,tool_call_blocked:1,tool_execution_failed:1}}};state.events=[{...${JSON.stringify(event(1))},event_type:'tool_call_requested',tool_call_id:'c1'},{...${JSON.stringify(event(2))},event_type:'tool_call_blocked',tool_call_id:'c1',rule:'protected-secrets',reason:'<b>denied</b>'},{...${JSON.stringify(event(3))},event_type:'tool_execution_failed',tool_call_id:'c1'},{...${JSON.stringify(event(4))},tool_call_id:'c2',timestamp:'2026-11-05T12:05:00Z'},{...${JSON.stringify(event(5))},event_type:'session_started',session_id:'s2',tool_name:undefined,timestamp:'2026-11-05T12:10:00Z'}]`;

test('Overview activity filters actual loaded records and exposes investigation actions', () => {
  const ui=harness();ui.run(linked());ui.route('overview');
  let content=ui.ids.get('content').innerHTML;assert.match(content,/Agent activity &amp; policy decisions/);assert.match(content,/data-inspect="e2"/);assert.match(content,/&lt;b&gt;denied/);assert.doesNotMatch(content,/<b>denied/);assert.match(content,/Showing 5 of 5 matching/);
  ui.run("state.scope='blocked'");ui.route('overview');content=ui.ids.get('content').innerHTML;assert.match(content,/Showing 1 of 1 matching/);assert.match(content,/protected-secrets/);
  ui.run("state.scope='all';state.activityQuery='no such record'");ui.route('overview');assert.match(ui.ids.get('content').innerHTML,/No matching activity/);
  ui.run('disconnect()');assert.equal(ui.run('state.activityQuery'),'');assert.equal(ui.run('state.scope'),'all');assert.equal(ui.run('state.inspector'),null);
});

test('decision flow links decisions to outcomes only through recorded tool call identifiers', () => {
  const ui=harness();ui.run(linked());ui.route('overview');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/Decision flow/);assert.match(content,/data-flow="blocked&gt;failed"/);assert.match(content,/Reported failed/);assert.match(content,/No outcome recorded/);assert.match(content,/2 tool calls in the loaded window/);
  ui.run("state.flow='blocked>failed'");ui.route('overview');const filtered=ui.ids.get('content').innerHTML;assert.match(filtered,/Showing 3 of 3 matching/);assert.match(filtered,/Clear path filter/);const list=filtered.slice(filtered.indexOf('activity-list'),filtered.indexOf('panel-foot'));assert.doesNotMatch(list,/data-inspect="e5"/);assert.match(list,/data-inspect="e2"/);
  assert.match(content,/1 allowed, 1 blocked, 0 approval events/);
});

test('session timeline plots one lane per recorded session and never uses inline style attributes', () => {
  const ui=harness();ui.run(linked());ui.route('overview');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/Session timeline/);assert.equal((content.match(/class="tl-track"/g)||[]).length,2);assert.match(content,/data-session="s2"/);assert.match(content,/5 events · 2 sessions/);
  assert.doesNotMatch(content,/style="/);assert.doesNotMatch(content,/100%|risk score|uptime|healthy/i);
  ui.run("state.zoom=[Date.parse('2026-11-05T12:04:00Z'),Date.parse('2026-11-05T12:06:00Z')]");ui.route('overview');assert.match(ui.ids.get('content').innerHTML,/Reset zoom/);
});

test('inspector shows the recorded tool-call chain and steps through visible records', () => {
  const ui=harness();ui.run(linked());ui.ids.set('inspector',new (ui.ids.get('main').constructor)('aside',{id:'inspector'}));ui.route('overview');
  ui.run("openInspector('e2')");const html=ui.ids.get('inspector').innerHTML;assert.match(html,/Tool call chain/);assert.match(html,/protected-secrets/);assert.match(html,/&lt;b&gt;denied/);assert.match(html,/Investigate in Replay/);assert.equal(ui.ids.get('inspector').dataset.open,'true');
  ui.run('stepInspector(1)');assert.equal(ui.run('state.inspector'),'e1');ui.run('stepInspector(-1)');assert.equal(ui.run('state.inspector'),'e2');
  ui.run('closeInspector()');assert.equal(ui.ids.get('inspector').dataset.open,'false');assert.equal(ui.ids.get('inspector').innerHTML,'');
});

test('command palette searches modules, sessions, rules and loaded events', () => {
  const ui=harness();ui.run(linked());ui.run("state.sessions=[{session_id:'s1',event_count:4}]");
  const labels=q=>ui.run(`paletteItems(${JSON.stringify(q)}).map(i=>i.group+':'+i.label)`);
  assert.ok(labels('guard').includes('Modules:Guard'));assert.ok(labels('s1').includes('Sessions:s1'));assert.ok(labels('protected').includes('Policy rules:protected-secrets'));assert.ok(labels('#2').some(l=>l.startsWith('Events:#2')));assert.equal(labels('zzz-no-match').length,0);
});

test('authenticated first load shows a loading skeleton instead of empty claims', () => {
  const ui=harness();ui.run("state.token='fixture'");ui.route('overview');const content=ui.ids.get('content').innerHTML;assert.match(content,/aria-busy="true"/);assert.doesNotMatch(content,/No activity loaded|Awaiting connection/);
  const offline=harness();offline.route('overview');assert.match(offline.ids.get('content').innerHTML,/Flow unavailable/);assert.match(offline.ids.get('content').innerHTML,/Timeline unavailable/);assert.match(offline.ids.get('content').innerHTML,/Recovery data unavailable/);
});

test('Guard rule activity counts recorded decisions per rule and examples only fill the dry-run form', () => {
  const ui=harness();ui.run(linked());ui.route('guard');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/Rule activity/);assert.match(content,/data-rule="protected-secrets"/);assert.match(content,/1 blocked, 0 approval required, 0 allowed/);assert.match(content,/data-example="1"/);assert.match(content,/does not execute/);
  assert.equal(ui.calls.length,0);
});

test('Watch and Replay summarise loaded records and Replay plots its own history', async () => {
  const ui=harness();ui.run(linked());ui.route('watch');let content=ui.ids.get('content').innerHTML;
  assert.match(content,/class="stream-stats"/);assert.match(content,/Outcome mix/);assert.doesNotMatch(content,/Replay timeline/);
  ui.run("state.token='fixture'");ui.route('replay');ui.respond(()=>json([event(10),{...event(11),event_type:'tool_call_blocked'}]));await ui.run('loadReplay(true)');
  content=ui.ids.get('content').innerHTML;assert.match(content,/Replay timeline/);assert.match(content,/data-inspect="e11"/);assert.match(content,/2 records in this browser window/);
});

test('Recovery stepper reflects recorded checkpoint status without inventing progress', () => {
  const ui=harness();ui.run("state.checkpoints=[{id:'a',path:'x',status:'OPEN'},{id:'b',path:'y',status:'SEALED'},{id:'c',path:'z',status:'FAILED'}]");ui.route('recovery');const content=ui.ids.get('content').innerHTML;
  assert.match(content,/Checkpoint lifecycle: OPEN/);assert.match(content,/Restored · ready/);assert.match(content,/Restored · failed/);assert.match(content,/Ready to restore/);
});

test('mission expiry is described relative to now and tools render as scope tags', () => {
  const ui=harness();assert.equal(ui.run("relTime('2026-01-01T02:00:00Z',Date.parse('2026-01-01T00:00:00Z'))"),'in 2 h');assert.equal(ui.run("relTime('2026-01-01T00:00:00Z',Date.parse('2026-01-01T00:30:00Z'))"),'30 min ago');
  ui.run("state.missions=[{id:'m',name:'Scoped',status:'DRAFT',approved_tools:['read_file','<x>']}]");ui.route('missions');const content=ui.ids.get('content').innerHTML;assert.match(content,/class="scope-tag">read_file/);assert.match(content,/&lt;x&gt;/);
});

test('one-time login link stores the token for this tab and leaves the address bar', () => {
  const ui=harness({hash:'#login=abcDEF0123456789_-xyz'});
  assert.equal(ui.run('state.token'),'abcDEF0123456789_-xyz');assert.equal(ui.context.location.hash,'overview');assert.equal(ui.run('route()'),'overview');
  const bad=harness({hash:'#login=short'});assert.equal(bad.run('state.token'),'');
  const injected=harness({hash:'#login=abcdefghijklmnop<script>'});assert.equal(injected.run('state.token'),'');
});

test('Overview shows a live plugin heartbeat and paused sessions only from service data', () => {
  const ui=harness();ui.run("state.connected=true;state.eventsLoaded=true;state.status={stats:{events:1,by_type:{}},plugin_heartbeats:[{role:'gateway',pid:42,age_seconds:12,live:true},{role:'command',pid:7,age_seconds:1,live:true}],paused_sessions:['loop']}");ui.route('overview');
  let content=ui.ids.get('content').innerHTML;assert.match(content,/Plugin active/);assert.match(content,/Heartbeat 12 s ago · gateway pid 42/);assert.match(content,/1 session paused by the breaker/);assert.doesNotMatch(content,/command pid 7/);
  ui.run("state.status.plugin_heartbeats=[{role:'gateway',pid:42,age_seconds:300,live:false}]");ui.route('overview');content=ui.ids.get('content').innerHTML;assert.match(content,/Not attested by dashboard/);assert.match(content,/No plugin heartbeat/);
  ui.run("state.connected=false");ui.route('overview');assert.doesNotMatch(ui.ids.get('content').innerHTML,/Plugin active/);
});
