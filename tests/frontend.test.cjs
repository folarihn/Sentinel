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

function harness({storageError = false} = {}) {
  const ids = new Map(), all = [], timers = new Map(), calls = [], downloads = [], storage = new Map();
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
    for(const match of value.matchAll(/<(form|input|textarea|select|button|pre|div)\b([^>]*)>/g)) {
      const [, tag, raw] = match, attributes = attrs(raw); if(!attributes.id && !attributes['data-event'] && !attributes['data-mission'] && !attributes['data-restore'] && !attributes['data-seal']) continue;
      register(tag, attributes);
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
  for(const id of ['main','notice','content','section-label','page-title','page-description','connection','last-update','clock','refresh','close-details','detail-content','details']) ids.set(id,new Element('div',{id}));
  const skip = new Element('a'); document.body = new Element('body');
  document.getElementById = id => ids.get(id) || null;
  document.querySelector = selector => selector === '.skip' ? skip : selector.startsWith('#') ? ids.get(selector.slice(1)) || null : null;
  document.querySelectorAll = selector => selector === 'form[data-dirty="true"]' ? all.filter(e => e.tagName === 'FORM' && e.dataset.dirty === 'true') : selector === '#content form' ? all.filter(e => e.tagName === 'FORM') : selector.startsWith('[data-') ? all.filter(e => Object.hasOwn(e.dataset, selector.slice(6,-1))) : [];
  document.createElement = tag => new Element(tag);
  const context = vm.createContext({document, location:{hash:'#overview',origin:'http://127.0.0.1:8765'}, window:{addEventListener(){}},
    sessionStorage:{getItem:key=>{if(storageError)throw Error('Storage denied');return storage.get(key)||null;},setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    FormData:class {constructor(form){this.form=form;}get(name){return this.form.elements.namedItem(name)?.value || '';}},
    fetch:async (url, options) => { calls.push({url,options}); return responder(url, options); },
    AbortController, URLSearchParams, Blob, URL:{createObjectURL:blob=>{context.exportedBlob=blob;return 'blob:fixture';},revokeObjectURL(){}},
    setInterval(){}, setTimeout:(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),queueMicrotask,console,confirm:()=>true
  });
  vm.runInContext(source, context);
  return {context, ids, all, calls, timers, downloads, skip, document, run:code=>vm.runInContext(code,context), respond:fn=>responder=fn, route:value=>{context.location.hash='#'+value;vm.runInContext('render()',context);}};
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
  const ui=harness();for(const value of ['missing','constructor','toString','__proto__']){ui.route(value);assert.equal(ui.run('route()'),'overview');assert.equal(ui.ids.get('page-title').textContent,'Operational overview');}
});

test('disconnect clears unsaved form drafts and never echoes the stored bearer token', () => {
  const ui=harness();ui.route('missions');const form=ui.ids.get('mission-form');form.elements.name.value='Private draft';form.dataset.dirty='true';ui.run('disconnect()');assert.equal(Object.keys(ui.run('state.drafts')).length,0);assert.equal(ui.ids.get('mission-form').elements.name.value,'');
  ui.run("state.token='private-bearer-fixture'");ui.route('settings');assert.doesNotMatch(ui.ids.get('content').innerHTML,/private-bearer-fixture/);
});

test('export metadata does not expose potentially sensitive search text', async () => {
  const ui=harness();ui.run("state.query='private-query-fixture'");ui.run('exportReport()');const text=await ui.context.exportedBlob.text();assert.doesNotMatch(text,/private-query-fixture/);assert.equal(JSON.parse(text).search_applied,true);
});
