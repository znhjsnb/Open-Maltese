/* Exercises the same worker engine shipped to the browser, without external packages. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {makeSearchEngine,exact,ascii,stripArticle,createWorkerHandler} from '../app/static/worker.js';
import {pronunciationGraphemes,currentWorkerError,renderAnalyses,exportText} from '../app/static/app.js';
import {createPronouncer,malteseVoice,availableVoice} from '../app/static/audio.js';
import {loadEntry} from '../app/static/db.js';
import vm from 'node:vm';
const entries=JSON.parse(fs.readFileSync('app/static/data/index_lite.json','utf8'));
const lookup=JSON.parse(fs.readFileSync('app/static/data/wordforms_lookup.json','utf8'));
const engine=makeSearchEngine(entries,lookup);
let count=0;
function test(name,run) { run(); count++; }
test('normalization',()=>{
  assert.equal(exact(' M’GĦANDIX '),"m'għandix");
  assert.equal(ascii('ĊĠĦŻ Għ IE'),'cghzghie');
  assert.equal(exact('G\u0127ajn'),'għajn');
  assert.equal(ascii('cañon'),'cañon');
});
for (const [query,target] of [['ktibt','kiteb'],['kotba','ktieb'],['kun','kien'],['jiktbu','kiteb'],['ix-xemx','xemx'],['l-iskola','skola'],['il-ktieb','ktieb'],['fil-ktieb','ktieb'],["m'għandix",'għand'],["m’għandix",'għand'],['mghandix','għand']]) {
  test(query,()=>{
    const result=engine.search({query});
    const e=result.results.find(e=>e.id===target);
    assert.ok(e,query); assert.ok(e.trace,query); assert.ok(e.trace.tags.length);
  });
}
test('exact glyphs outrank tolerant matches',()=>{
  assert.equal(engine.search({query:'għajn'}).results[0].id,'għajn');
  assert.equal(engine.search({query:'ghajn'}).results[0].id,'għajn');
});
test('nonexistent prefix stem cannot create a lemma',()=>{
  assert.equal(engine.resolve('il-zzzzzzzz').size,0);
  assert.equal(engine.resolve('__proto__').size,0);
  assert.equal(engine.resolve('constructor').size,0);
});
test('root family',()=>{
  const result=engine.search({query:'#root:k-t-b'});
  assert.ok(result.results.some(e=>e.id==='kiteb'));
  assert.ok(result.results.every(e=>e.roots.includes('k-t-b')));
});
test('prefix I ie',()=>{
  const result=engine.search({bucket:'I',prefix:'ie'});
  assert.ok(result.total>0); assert.ok(result.results.every(e=>e.bucket==='I' && e.sub_prefix==='ie'));
});
test('tiers strata and pagination',()=>{
  const core=engine.search({tier:'core'});
  assert.equal(core.total,5051); assert.ok(core.results.every(e=>e.tier===1));
  assert.ok(engine.search({tier:'rich'}).results.every(e=>e.tier<=2));
  assert.ok(engine.search({stratum:'english'}).results.every(e=>e.stratum==='english'));
  const all=engine.search({}); const next=engine.search({offset:60});
  assert.equal(all.total,24045); assert.equal(next.offset,60); assert.notEqual(all.results[0].id,next.results[0].id);
  assert.equal(engine.search({query:'zzzzzzzz',offset:1000}).total,0);
});
test('all feature filters',()=>{
  assert.equal(engine.search({feature:'showcase'}).total,25);
  assert.ok(engine.search({feature:'showcase'}).results.every(e=>e.is_showcase));
  assert.ok(engine.search({feature:'root'}).results.every(e=>e.roots.length));
  assert.ok(engine.search({feature:'audio'}).results.every(e=>e.has_audio));
  assert.equal(engine.search({feature:'audio'}).total,597);
  const loans=engine.search({feature:'loans'});
  assert.ok(loans.total>0);
  assert.ok(loans.results.every(e=>(e.strata || [e.stratum]).some(s=>['romance_sicilian_italian','english'].includes(s))));
});
test('context-checked articles and euphonic vowel',()=>{
  const basic=makeSearchEngine(entries);
  for (const [q,target] of [['fix-xemx','xemx'],['bid-dar','dar'],['x-xemx','xemx'],['d-dar','dar'],['lill-kelb','kelb'],['fl-iskola','skola'],['l-iskola','skola']]) {
    assert.ok(basic.resolve(q).has(target),q);
    assert.ok(basic.resolve(q).get(target).every(t=>t.includes('grammar_rule')));
  }
  for (const q of ['ix-ktieb','fix-ktieb','bid-xemx','il-dar','fil-xemx','lill-dar']) assert.equal(basic.resolve(q).size,0,q);
  const known=new Set(['skola','iskola','għajn','sħab']);
  assert.deepEqual(stripArticle('l-iskola',known),['iskola','l-']);
  known.delete('iskola');
  assert.deepEqual(stripArticle('l-iskola',known),['skola','l-i']);
  assert.deepEqual(stripArticle('l-isħab',known),['sħab','l-i']);
  for (const base of ['','i','fi','bi','ma','ta','għa','li']) for (const c of 'ċdnrstxżz') {
    const prefix=base+c+'-';
    assert.deepEqual(stripArticle(prefix+c+'a',new Set()),[c+'a',prefix]);
    assert.deepEqual(stripArticle(prefix+'kelb',new Set()),[prefix+'kelb',null]);
  }
});
test('longest-match pronunciation graphemes and stale worker errors',()=>{
  assert.deepEqual(pronunciationGraphemes('GĦAJN'),['għ','a','j','n']);
  assert.ok(!pronunciationGraphemes('għajn').includes('ħ'));
  assert.deepEqual(pronunciationGraphemes('qiegħed'),['q','ie','għ','e','d']);
  assert.equal(currentWorkerError({type:'error',requestId:1},2),false);
  assert.equal(currentWorkerError({type:'error',requestId:2},2),true);
  assert.equal(currentWorkerError({type:'error'},2),true);
});
// A pending stage 2 promise must not hold the first search response.
{
  let finishReverse;
  const messages=[],calls=[];
  const staged=createWorkerHandler(m=>messages.push(m),async(meta,version)=>{
    calls.push([meta.file,version]);
    return meta.file==='index' ? entries : new Promise(resolve=>{finishReverse=resolve;});
  });
  const generation='test-generation';
  await staged({data:{type:'init',manifest:{version:generation,index_lite:{file:'index'},wordforms_lookup:{file:'reverse'}}}});
  assert.equal(messages[0].type,'ready');
  assert.deepEqual(calls,[['index',generation],['reverse',generation]]);
  await staged({data:{type:'search',query:'fix-xemx',requestId:71}});
  assert.ok(messages.at(-1).results.some(e=>e.id==='xemx'));
  await staged({data:{type:'search',query:'ktibt',requestId:72}});
  assert.ok(!messages.at(-1).results.some(e=>e.id==='kiteb'));
  finishReverse({...lookup,version:generation});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.ok(messages.some(m=>m.type==='wordforms-ready'));
  assert.equal(messages.at(-1).requestId,72);
  assert.ok(messages.at(-1).results.some(e=>e.id==='kiteb'));
  count++;
  const failed=[];
  const wrong=createWorkerHandler(m=>failed.push(m),async meta=>meta.file==='index' ? entries : {...lookup,version:'old'});
  await wrong({data:{type:'init',manifest:{version:generation,index_lite:{file:'index'},wordforms_lookup:{file:'reverse'}}}});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.ok(failed.some(m=>m.type==='wordforms-error'));
  await wrong({data:{type:'search',query:'ktieb',requestId:73}});
  assert.equal(failed.at(-1).results[0].id,'ktieb');count++;
}
test('native language validation',()=>{
  assert.equal(malteseVoice([{lang:'en-US',name:'Maltese fake label'}]),null);
  assert.equal(malteseVoice([{lang:'it-IT',name:'Italian'}]),null);
  assert.equal(malteseVoice([{lang:'mt-MT',name:'Grace'}]).name,'Grace');
  assert.ok(malteseVoice([{lang:'mlt',name:'Maltese'}]));
  assert.ok(malteseVoice([{lang:'mt',name:'eSpeak'}]));
});
class Synth extends EventTarget {
  constructor(voices=[]) { super(); this.voices=voices; this.spoken=[]; }
  getVoices() { return this.voices; }
  cancel() {}
  speak(u) { this.spoken.push(u); }
}
class Utterance { constructor(text) { this.text=text; } }
class Recording extends EventTarget {
  constructor(url) { super();this.url=url; Recording.last=this; }
  async play() { return undefined; }
  pause() {}
}
const voice={lang:'mt-MT',name:'Native Maltese'};
const synth=new Synth([voice]); let guides=[],statuses=[];
const player=createPronouncer({synth,AudioClass:Recording,Utterance,guide:t=>guides.push(t),status:t=>statuses.push(t)});
await player.play('ktieb','https://upload.wikimedia.org/test.mp3');
assert.equal(synth.spoken.length,0); assert.equal(Recording.last.url,'https://upload.wikimedia.org/test.mp3'); count++;
await player.play('kiteb'); assert.equal(synth.spoken.length,1); assert.equal(synth.spoken[0].lang,'mt-MT'); assert.equal(synth.spoken[0].voice,voice); count++;
class FailedRecording extends Recording { async play() { throw new Error('offline'); } }
const fallback=createPronouncer({synth,AudioClass:FailedRecording,Utterance,guide:t=>guides.push(t),status:()=>{}});
await fallback.play('ktieb','https://upload.wikimedia.org/test.mp3'); assert.equal(synth.spoken.length,2); count++;
const foreign=new Synth([{lang:'en-US',name:'English'},{lang:'it-IT',name:'Italian'}]);
const honest=createPronouncer({synth:foreign,AudioClass:Recording,Utterance,guide:t=>guides.push(t),status:()=>{}});
await honest.play('skola'); assert.equal(foreign.spoken.length,0); assert.equal(guides.at(-1),'skola'); count++;
const delayed=new Synth(); const waiting=availableVoice(delayed); delayed.voices=[voice]; delayed.dispatchEvent(new Event('voiceschanged')); assert.equal(await waiting,voice); count++;
const stale=new Synth(); const cancel=createPronouncer({synth:stale,AudioClass:Recording,Utterance,guide:t=>guides.push(t),status:()=>{}});
const before=guides.length;const pending=cancel.play('old'); cancel.stop(); await pending;assert.equal(guides.length,before);count++;
const manifest=JSON.parse(fs.readFileSync('app/static/data/manifest.json','utf8'));
const shardEntries=manifest.shards.flatMap(s=>JSON.parse(fs.readFileSync(`app/static/data/${s.file}`,'utf8')));
test('homograph cards and exports preserve analysis boundaries and evidence',()=>{
  const dar=shardEntries.find(e=>e.id==='dar');
  const html=renderAnalyses(dar.lexeme_analyses);
  const sections=html.split('<section class="lexeme-analysis">').slice(1);
  assert.equal(sections.length,dar.lexeme_analyses.length);
  const noun=sections[dar.lexeme_analyses.findIndex(a=>a.source==='kaikki' && a.pos==='noun')];
  const verb=sections[dar.lexeme_analyses.findIndex(a=>a.source==='kaikki' && a.pos==='verb')];
  assert.ok(noun.includes('djar'));assert.ok(!noun.includes('jdur'));assert.ok(!noun.includes('midur'));
  assert.ok(verb.includes('jdur'));assert.ok(verb.includes('midur'));assert.ok(!verb.includes('djar'));
  const recorded=shardEntries.find(e=>e.headword.audio_commons_url && e.dual_scenarios);
  for (const anki of [false,true]) {
    const text=exportText(recorded,anki,manifest);
    assert.ok(text.includes('CC BY 3.0'));
    assert.ok(text.includes('source_attested'));
    assert.ok(text.includes('pending_linguistic_review'));
    assert.ok(text.includes(recorded.headword.audio_commons_url));
    assert.ok(text.includes('https://mlrs.research.um.edu.mt/'));
    assert.ok(text.includes('aħwa'));
    if (anki) assert.equal(text.split('\t').length,9);
  }
});
// Minimal event-based IndexedDB fixture. Fresh module imports simulate reloads;
// only the persisted database survives, with network and Cache API unavailable.
const idbRecords=new Map(); let created=false;
globalThis.indexedDB={open(){
  const request={};
  queueMicrotask(()=>{
    request.result={createObjectStore(){created=true;},transaction(){
      const tx={objectStore(){return {
        get(key){const r={};queueMicrotask(()=>{r.result=structuredClone(idbRecords.get(key));r.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.());});return r;},
        put(value,key){const r={};queueMicrotask(()=>{idbRecords.set(key,structuredClone(value));r.result=key;r.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.());});return r;}
      };}};return tx;
    }};
    if(!created) request.onupgradeneeded?.();
    request.onsuccess?.();
  });return request;
}};
const index=entries.find(e=>e.id==='kiteb');
const meta=manifest.shards.find(s=>s.bucket===index.bucket);
const originalFetch=globalThis.fetch;let fetched=0;
try {
  globalThis.fetch=async()=>{fetched++;return new Response(fs.readFileSync(`app/static/data/${meta.file}`));};
  assert.equal((await loadEntry(index,manifest)).headword.word,'kiteb');
  assert.equal((await loadEntry(index,manifest)).headword.word,'kiteb');
  assert.equal(fetched,1);count++;
  const corrupt={...manifest,shards:manifest.shards.map(s=>s.bucket===index.bucket ? {...s,sha256:'0'.repeat(64)} : s)};
  await assert.rejects(loadEntry(index,corrupt),/更新|损坏/);count++;
} finally {globalThis.fetch=originalFetch;}
try {
  globalThis.fetch=async url=>new Response(fs.readFileSync(`app/static/data/${String(url).replace('./data/','').split('?')[0]}`));
  const online=await import('../app/static/db.js?online');
  assert.equal((await online.loadManifest()).version,manifest.version);
  await online.loadDataset(manifest.index_lite,manifest.version);
  await online.loadDataset(manifest.wordforms_lookup,manifest.version);
  await online.loadEntry(index,manifest);
  globalThis.fetch=async()=>{throw new Error('offline');};
  const offline=await import('../app/static/db.js?offline');
  const savedManifest=await offline.loadManifest();
  const savedIndex=await offline.loadDataset(savedManifest.index_lite,savedManifest.version);
  const savedLookup=await offline.loadDataset(savedManifest.wordforms_lookup,savedManifest.version);
  assert.equal(makeSearchEngine(savedIndex,savedLookup).search({query:'ktibt'}).results[0].id,'kiteb');
  assert.equal((await offline.loadEntry(index,savedManifest)).id,'kiteb');count++;
  await assert.rejects(offline.loadDataset(manifest.index_lite,'other-generation'),/offline/);count++;
  idbRecords.set(`${manifest.version}:${manifest.index_lite.sha256}`,new TextEncoder().encode('[]').buffer);
  await assert.rejects(offline.loadDataset(manifest.index_lite,manifest.version),/更新|损坏/);count++;
} finally {globalThis.fetch=originalFetch;delete globalThis.indexedDB;}
try {
  globalThis.indexedDB={open(){throw new Error('storage denied');}};
  globalThis.fetch=async()=>new Response(fs.readFileSync('app/static/data/index_lite.json'));
  const privateMode=await import('../app/static/db.js?storage-denied');
  assert.equal((await privateMode.loadDataset(manifest.index_lite,manifest.version)).length,24045);count++;
} finally {globalThis.fetch=originalFetch;delete globalThis.indexedDB;}
// Execute the shipped Service Worker with a network/cache harness, including
// offline shell/module and manifest fetches (not a browser E2E claim).
{
  const listeners={},saved=new Map();let disconnected=false;
  const cache={addAll:async urls=>{for(const u of urls) saved.set(u,new Response('shell'));},put:async(k,v)=>saved.set(k,v.clone())};
  const context={URL,Response,self:{location:{origin:'http://localhost'},clients:{claim:async()=>{}},addEventListener:(type,handler)=>listeners[type]=handler},
    caches:{open:async()=>cache,match:async key=>saved.get(key)?.clone()},
    fetch:async()=>{if(disconnected)throw new Error('offline');return new Response('asset');}};
  vm.runInNewContext(fs.readFileSync('app/static/sw.js','utf8'),context);
  async function fire(type,extra={}) {
    const waits=[];let result;
    listeners[type]({...extra,waitUntil:p=>waits.push(p),respondWith:p=>{result=p;}});
    const response=await result;await Promise.all(waits);return response;
  }
  await fire('install');await fire('activate');
  for (const path of ['app.js','db.js','worker.js','data/manifest.json','data/index_lite.json?sha=x&version=v','data/wordforms_lookup.json?sha=y&version=v']) {
    const request={method:'GET',url:'http://localhost/'+path};
    assert.equal((await fire('fetch',{request})).status,200);
    disconnected=true;
    assert.equal(await (await fire('fetch',{request})).text(),'asset');
    disconnected=false;
  }
  count++;
}
console.log(`${count} client checks passed`);
