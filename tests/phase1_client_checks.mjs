/* Exercises the same worker engine shipped to the browser, without external packages. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {makeSearchEngine,exact,ascii,stripArticle,createWorkerHandler} from '../app/static/worker.js';
import {pronunciationGraphemes,currentWorkerError,renderAnalyses,renderInflections,renderEtymology,renderSenses,mergeResultPage,exportText,sourceChain,posClass,learnerSenses} from '../app/static/app.js';
import {createPronouncer,malteseVoice,availableVoice} from '../app/static/audio.js';
import {loadEntry} from '../app/static/db.js';
import vm from 'node:vm';
const manifest=JSON.parse(fs.readFileSync('app/static/data/manifest.json','utf8'));
const entries=JSON.parse(fs.readFileSync('app/static/data/index_lite.json','utf8'));
const lookup=JSON.parse(fs.readFileSync('app/static/data/wordforms_lookup.json','utf8'));
const engine=makeSearchEngine(entries,lookup);
let count=0;
function test(name,run) { run(); count++; }
test('UTF-8 shell preserves legacy and new selector contracts without duplicate ids',()=>{
  const html=fs.readFileSync('app/static/index.html','utf8');
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  assert.equal(ids.length,new Set(ids).size);
  for(const id of ['theme','font-down','font-up','language-mode','search','clear','search-key','letter-bar','sub-prefix-bar','tier-filters','stratum-filters','feature-filters','result-count','search-time','wordforms-status','headword-list','previous-page','page-number','next-page','page-input','page-go','bookmarks','bookmark-count','sort-order','offline','entry-card','save','copy-markdown','copy-anki','pronunciation-guide-popover','pronunciation-content','close-pronunciation','toast','inventory-note','word-sidebar','resizer','content','toolbar-pinned-word','focus','study','typography-panel','typography-btn','typography-close','font-decrease','font-increase','font-size-value','typo-reset','lang-trilingual','lang-bilingual','lang-en','theme-toggle'])assert.ok(ids.includes(id),id);
  assert.ok(html.includes('Ġabra') && html.includes('马耳他语认知词典'));
  assert.ok(!/<details\b/i.test(html));
  for(const file of ['app/static/index.html','app/static/app.js','app/static/styles.css','tests/frontend.browser.mjs']) {
    const text=fs.readFileSync(file,'utf8');
    assert.ok(!/[?]{3,}|\uFFFD/.test(text),`Damaged UTF-8: ${file}`);
  }
});
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
  assert.ok(manifest.showcase_count>=100);
  assert.equal(engine.search({feature:'showcase'}).total,manifest.showcase_count);
  assert.ok(engine.search({feature:'showcase'}).results.every(e=>e.is_showcase));
  assert.ok(engine.search({feature:'root'}).results.every(e=>e.roots.length));
  assert.ok(engine.search({feature:'audio'}).results.every(e=>e.has_audio));
  assert.equal(engine.search({feature:'audio'}).total,597);
  const loans=engine.search({feature:'loans'});
  assert.ok(loans.total>0);
  assert.ok(loans.results.every(e=>(e.strata || [e.stratum]).some(s=>['romance_sicilian_italian','english'].includes(s))));
});
test('bookmarks filter uses ids before slicing, including an explicitly empty list',()=>{
  assert.equal(engine.search({bookmarks:[]}).total,0);
  assert.deepEqual(engine.search({bookmarks:[]}).results,[]);
  assert.equal(engine.search({bookmarks:null}).total,entries.length);
  assert.equal(engine.search({}).total,entries.length);
  const ids=entries.slice(120,245).map(e=>e.id);
  const result=engine.search({bookmarks:[...ids,'__nonexistent_bookmark__',ids[0]],offset:60});
  assert.equal(result.total,125);assert.equal(result.results.length,60);
  assert.deepEqual(result.results.map(e=>e.id),ids.slice(60,120));
  assert.ok(engine.search({query:'ktibt',bookmarks:['kiteb']}).results[0].trace);
});
test('sort retains DMS order within relevance and tier, 60 results per page',()=>{
  const ids=rows=>rows.map(e=>e.id);
  assert.deepEqual(ids(engine.search({sort:'alpha'}).results),ids(entries.slice(0,60)));
  assert.deepEqual(ids(engine.search({sort:'alpha-desc'}).results),ids(entries.slice().reverse().slice(0,60)));
  const ordered=entries.slice().sort((a,b)=>a.tier-b.tier);
  for(const offset of [0,60,5040,11400]) assert.deepEqual(ids(engine.search({sort:'tier',offset}).results),ids(ordered.slice(offset,offset+60)));
  for(const sort of ['alpha','alpha-desc','tier']) assert.equal(engine.search({query:'dar',sort}).results[0].id,'dar');
});
test('stream pages replace stage-2 replays and deduplicate ids across offsets',()=>{
  const pages=new Map();
  const first=engine.search({requestId:88}),next=engine.search({requestId:89,offset:60});
  assert.equal(mergeResultPage(pages,first).length,60);
  assert.equal(mergeResultPage(pages,next).length,120);
  assert.equal(mergeResultPage(pages,next).length,120);
  const replay={...first,results:first.results.map(e=>({...e,trace:{surface:'replayed'}}))};
  const result=mergeResultPage(pages,replay);
  assert.equal(result.length,120);assert.equal(result[0].trace.surface,'replayed');
  assert.equal(mergeResultPage(pages,{offset:120,results:[next.results[0]]}).length,120);
});
test('context-checked articles and euphonic vowel',()=>{
  const basic=makeSearchEngine(entries);
  for (const [q,target] of [['fix-xemx','xemx'],['bid-dar','dar'],['x-xemx','xemx'],['d-dar','dar'],['lill-kelb','kelb'],['fl-iskola','skola'],['l-iskola','skola']]) {
    assert.ok(basic.resolve(q).has(target),q);
    assert.ok(basic.resolve(q).get(target).every(t=>t.includes('grammar_rule')));
  }
  for (const q of ['ix-ktieb','fix-ktieb','bid-xemx','il-dar','fil-xemx','lill-dar','l-iktieb','l-iżmien','l-itriq','ij-jum','l-iżgħir']) assert.equal(basic.resolve(q).size,0,q);
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
{
  const activity=[],voices=new Synth([voice]);
  const meter=createPronouncer({synth:voices,AudioClass:Recording,Utterance,guide:()=>{},status:()=>{},activity:value=>activity.push(value)});
  await meter.play('ktieb','https://upload.wikimedia.org/test.mp3');
  assert.equal(activity.at(-1),true);
  const first=Recording.last;first.dispatchEvent(new Event('ended'));assert.equal(activity.at(-1),false);
  await meter.play('kiteb');assert.equal(activity.at(-1),false);
  voices.spoken[0].onstart();assert.equal(activity.at(-1),true);
  const beforeStaleEnd=activity.length;first.dispatchEvent(new Event('ended'));assert.equal(activity.length,beforeStaleEnd);
  voices.spoken[0].onend();assert.equal(activity.at(-1),false);
  meter.stop();assert.equal(activity.at(-1),false);count++;
}
class FailedRecording extends Recording { async play() { throw new Error('offline'); } }
const fallback=createPronouncer({synth,AudioClass:FailedRecording,Utterance,guide:t=>guides.push(t),status:()=>{}});
await fallback.play('ktieb','https://upload.wikimedia.org/test.mp3'); assert.equal(synth.spoken.length,2); count++;
const foreign=new Synth([{lang:'en-US',name:'English'},{lang:'it-IT',name:'Italian'}]);
const honest=createPronouncer({synth:foreign,AudioClass:Recording,Utterance,guide:t=>guides.push(t),status:()=>{}});
await honest.play('skola'); assert.equal(foreign.spoken.length,0); assert.equal(guides.at(-1),'skola'); count++;
const delayed=new Synth(); const waiting=availableVoice(delayed); delayed.voices=[voice]; delayed.dispatchEvent(new Event('voiceschanged')); assert.equal(await waiting,voice); count++;
const stale=new Synth(); const cancel=createPronouncer({synth:stale,AudioClass:Recording,Utterance,guide:t=>guides.push(t),status:()=>{}});
const before=guides.length;const pending=cancel.play('old'); cancel.stop(); await pending;assert.equal(guides.length,before);count++;
const shardEntries=manifest.shards.flatMap(s=>JSON.parse(fs.readFileSync(`app/static/data/${s.file}`,'utf8')));
test('homograph cards and exports preserve analysis boundaries and evidence',()=>{
  const dar=shardEntries.find(e=>e.id==='dar');
  const html=renderAnalyses(dar.lexeme_analyses);
  const sections=html.split('<section class="lexeme-analysis morphology-subentry"').slice(1);
  assert.equal(sections.length,dar.lexeme_analyses.length);
  const noun=sections[dar.lexeme_analyses.findIndex(a=>a.source==='kaikki' && a.pos==='noun')];
  const verb=sections[dar.lexeme_analyses.findIndex(a=>a.source==='kaikki' && a.pos==='verb')];
  assert.ok(noun.includes('djar'));assert.ok(!noun.includes('jdur'));assert.ok(!noun.includes('midur'));
  assert.ok(noun.includes('房屋')); assert.ok(!verb.includes('房屋'));
  assert.ok(verb.includes('转动')); assert.ok(!html.includes('class="sense"'));
  const mtSense=structuredClone(dar.lexeme_analyses[0]);
  mtSense.senses[0].mt_definition='Definizzjoni <sigura>';
  assert.ok(!renderAnalyses([mtSense]).includes('Definizzjoni'));
  assert.ok(verb.includes('jdur'));assert.ok(verb.includes('midur'));assert.ok(!verb.includes('djar'));
  const recorded=shardEntries.find(e=>e.id==='abjad');
  for (const anki of [false,true]) {
    const text=exportText(recorded,anki,manifest);
    assert.ok(text.includes('CC BY 3.0'));
    assert.ok(text.includes('source_attested'));
    assert.ok(text.includes('phase2_reviewed'));
    assert.ok(text.includes(recorded.headword.audio_commons_url));
    assert.ok(text.includes('https://mlrs.research.um.edu.mt/'));
    assert.ok(text.includes('aħwa'));
    if (anki) assert.equal(text.split('\t').length,9);
  }
});
test('dimensions 06 and 08 use each exact analysis id without aggregate fallback',()=>{
  for(const word of ['abaku','dar']) {
    const entry=shardEntries.find(e=>e.id===word),six=renderInflections(entry),eight=renderEtymology(entry);
    assert.ok(!six.includes('lexeme-analysis'));assert.ok(!eight.includes('lexeme-analysis'));
    for(const [html,css] of [[six,'inflection-subentry'],[eight,'etymology-subentry']]) {
      const blocks=html.split(`<section class="${css}"`).slice(1);
      const expected=css==='etymology-subentry' ? entry.lexeme_analyses.filter(a=>a.source==='kaikki') : entry.lexeme_analyses.filter(a=>a.attested_forms?.length || a.definite_article || a.pronomi_mehmuzin?.length || Object.values(a.verb_paradigm || {}).some(Boolean));
      assert.equal(blocks.length,expected.length);
      expected.forEach((a,i)=>assert.ok(blocks[i].startsWith(` data-analysis-id="${a.id}"`)));
      assert.ok(!/列于上方|分列如下/.test(html));
    }
    if(word==='abaku') {
      assert.ok(six.includes('abaki'));assert.ok(six.includes('l-abaku'));
      assert.ok(!six.includes('Perfett 3sg.m'));
      assert.ok(!six.includes('Pronomi Mehmużin'));
      assert.ok(eight.includes('gabra:') && eight.includes('未单列历史词源'));
      assert.equal((eight.match(/<li>/g)||[]).length,1);
      const morph=renderAnalyses(entry.lexeme_analyses);
      assert.equal((morph.match(/class="lexeme-analysis morphology-subentry"/g)||[]).length,1);
      assert.ok(!/not recorded|未完成体|过去分词|动名词/.test(morph));
      const gabra=six.split('<section class="inflection-subentry"')[1];
      assert.ok(!gabra.includes('abaki'));
      assert.ok(eight.includes('Borrowed from Italian abaco.'));assert.ok(eight.includes('学习助记：'));
      assert.ok(eight.includes('authored_pedagogical · phase2_reviewed'));
    } else {
      const blocks=six.split('<section class="inflection-subentry"').slice(1);
      const noun=blocks.find(b=>b.startsWith(' data-analysis-id="kaikki:dar:0"'));
      const verb=blocks.find(b=>b.startsWith(' data-analysis-id="kaikki:dar:1"'));
      assert.ok(noun.includes('djar')&&noun.includes('id-dar')&&!/jdur|midur/.test(noun));
      assert.ok(verb.includes('jdur')&&verb.includes('midur')&&!verb.includes('djar'));
      assert.ok(verb.includes('已展示 24 / 共 55 项'));
      // Poison the aggregates: neither dimension is allowed to use them.
      const changed=structuredClone(entry);changed.inflection_and_clitics.plural=['POISON'];changed.etymology.etymology_text_en='POISON';
      assert.ok(!renderInflections(changed).includes('POISON'));assert.ok(!renderEtymology(changed).includes('POISON'));
    }
  }
});
test('empty paradigms and empty analyses stay compact; clitics and templates retain evidence',()=>{
  const entry=structuredClone(shardEntries.find(e=>e.id==='dar'));
  entry.lexeme_analyses=entry.lexeme_analyses.slice(0,2).map(a=>({...a,roots:[],root_consonants:null,pattern_type:'unspecified',word_family:null,verb_forms_attested:[],plural_forms:null,collective_forms:null,singulative_forms:null,verb_paradigm:{perfett_3sg_m:null,imperfett_3sg_m:'',imperattiv_2sg:null,past_participle:null,verbal_noun:null},attested_forms:[],pronomi_mehmuzin:[],definite_article:null,etymology_text:'',etymology_templates:[],source_chain:[],stratum:'unspecified'}));
  assert.ok(!renderAnalyses(entry.lexeme_analyses).includes('morphology-subentry'));
  assert.ok(!renderInflections(entry).includes('inflection-subentry'));
  assert.ok(!renderEtymology(entry).includes('etymology-subentry'));
  assert.equal((renderEtymology(entry).match(/not recorded/g)||[]).length,1);
  const ghand=shardEntries.find(e=>e.id==='għand');
  assert.ok(renderInflections(ghand).includes('Pronomi Mehmużin'));
  for(const form of ['għandi','għandek','għandu'])assert.ok(ghand.inflection_and_clitics.pronomi_mehmuzin.some(f=>f.form===form));
  const t={template:'etymon',args:{'1':'mt','2':':bor','3':'it:abaco'}};
  const formatted=sourceChain([t,{...t,args:{'3':'it:abaco','2':':bor','1':'mt'}},{template:'bor',args:{'1':'mt','2':'it','3':'abaco'}}]);
  assert.equal((formatted.match(/<li>/g)||[]).length,1);assert.ok(formatted.includes('borrowed'));
  for(const relation of ['inh','der','cog'])assert.ok(sourceChain([{template:relation,args:{'1':'mt','2':'ar','3':'x'}}]).includes({inh:'inherited',der:'derived',cog:'cognate'}[relation]));
  const unknown={template:'unknown',args:{x:'<evidence>'}};
  assert.equal((sourceChain([unknown,unknown]).match(/<li>/g)||[]).length,1);
  assert.ok(sourceChain([unknown]).includes('&lt;evidence&gt;'));
});
test('source English and pedagogical translations have distinct provenance',()=>{
  const dar=shardEntries.find(e=>e.id==='dar'),html=renderSenses(dar.senses);
  assert.equal((html.match(/class="sense sense-card"/g)||[]).length,dar.senses.length);
  assert.ok(html.includes('来源释义 (licensed_source) · source_attested'));
  assert.ok(html.includes('译释：authored_pedagogical · phase2_reviewed'));
  assert.ok(html.includes('id="sense-0"'));
  const teaching=renderSenses([{definition_origin:'authored_pedagogical',en_definition:'<safe>'}]);
  assert.ok(teaching.includes('教学编写 · authored_pedagogical · phase2_reviewed'));
  assert.ok(teaching.includes('&lt;safe&gt;'));
});
test('all display POS values are canonical and source POS remains auditable',()=>{
  for (const index of entries) {
    assert.deepEqual(index.pos_list,[...new Set(index.pos_list.map(posClass))]);
    assert.ok(index.pos_list.every(p=>p && p===p.trim().toLowerCase()));
  }
  assert.deepEqual(entries.find(e=>e.id==='abaku').pos_list,['noun']);
  assert.deepEqual(entries.find(e=>e.id==='abbanduna').pos_list,['verb']);
  assert.equal(shardEntries.find(e=>e.id==='abaku').lexeme_analyses[0].pos,'NOUN');
  for (const [pos,expected] of [['name','propn'],['SCONJ','conj'],['PART','part'],['article','art'],[' AUX ','aux'],['X-Custom','x-custom']])assert.equal(posClass(pos),expected);
});
test('fusion and every consumer use the same numbered groups with scoped teaching',()=>{
  const abaku=shardEntries.find(e=>e.id==='abaku'),abbanduna=shardEntries.find(e=>e.id==='abbanduna'),dar=shardEntries.find(e=>e.id==='dar');
  for (const [entry,expected] of [[abaku,1],[abbanduna,3]]) {
    const view=learnerSenses(entry),html=renderSenses(view,entry.sense_guide);
    assert.equal(view.length,expected);assert.equal((html.match(/class="sense sense-card"/g)||[]).length,expected);
    assert.ok(!renderAnalyses(entry.lexeme_analyses).includes('class="sense"'));
    assert.equal((exportText(entry,false,manifest).split('03 · Senses')[1].split('04 · Collocations')[0].match(/\n- /g)||[]).length,expected);
    const fields=exportText(entry,true,manifest).split('\t');assert.equal(fields.length,9);
    assert.ok(fields[3].includes(entry.display_senses[0].zh_definition));
  }
  const one=renderSenses(abaku.display_senses);
  assert.ok(one.includes('A counting tool with movable beads') && one.includes('Għodda bi żibeġ') && one.includes('算盘'));
  assert.ok(one.includes('原文简释：abacus') && one.includes('gabra · kaikki'));
  assert.ok(!one.includes('核心词义导览'));
  assert.ok(!renderSenses(abbanduna.display_senses,abbanduna.sense_guide).includes('核心词义导览'));
  assert.equal(dar.sense_guide,null);
  const bound=dar.display_senses.filter(s=>s.teaching);
  assert.equal(bound.length,1);assert.equal(bound[0].pos,'noun');assert.equal(bound[0].en_definition,'house');
  const verbs=dar.display_senses.filter(s=>s.pos==='verb');
  assert.ok(verbs.length>1);assert.ok(!renderSenses(verbs).includes('Bini fejn jgħixu n-nies.'));
  const poisoned=structuredClone(abaku);poisoned.senses.push({id:'poison',en_definition:'POISON'});
  assert.ok(!exportText(poisoned,false,manifest).includes('POISON'));
  const safe=structuredClone(abaku.display_senses);safe[0].en_explanation='<unsafe>';safe[0].mt_definition='Definizzjoni <sigura>';
  const html=renderSenses(safe,null,'study-sense');
  assert.ok(html.includes('&lt;unsafe&gt;') && html.includes('Definizzjoni &lt;sigura&gt;'));
  assert.ok(html.includes('id="study-sense-0"') && !html.includes('id="sense-0"'));
});
test('single lexeme only renders applicable source forms and safe etymology',()=>{
  const entry=structuredClone(shardEntries.find(e=>e.id==='abaku'));
  entry.lexeme_analyses=entry.lexeme_analyses.filter(a=>a.source==='kaikki');
  const noun=renderInflections(entry);assert.ok(noun.includes('abaki'));assert.ok(!noun.includes('Perfett 3sg.m'));
  const etymology=renderEtymology(entry);assert.ok(etymology.includes('etymology-card'));assert.ok(etymology.includes('Borrowed from Italian abaco.'));
  entry.lexeme_analyses[0].pos='verb';
  entry.lexeme_analyses[0].verb_paradigm={perfett_3sg_m:'source-only-form'};
  const verb=renderInflections(entry);assert.ok(!verb.includes('复数 / plural'));assert.ok(!verb.includes('定冠词 L-Artiklu'));
  assert.ok(verb.includes('source-only-form'));
  entry.etymology.etymology_text_en='<script>alert(1)</script>';
  assert.ok(renderEtymology(entry).includes('&lt;script&gt;'));
});
// Minimal event-based IndexedDB fixture. Fresh module imports simulate reloads;
// only the persisted database survives, with network and Cache API unavailable.
const idbRecords=new Map(),legacyRecords=new Map(); let created=false,dropWrites=false,dropReads=false,corruptReads=false,hasLegacy=false;
globalThis.indexedDB={open(){
  const request={};
  queueMicrotask(()=>{
    request.result={objectStoreNames:{contains:name=>(created && name==='files') || (hasLegacy && name==='assets')},createObjectStore(){created=true;},transaction(name){
      const records=name==='assets' ? legacyRecords : idbRecords;
      const tx={objectStore(){return {
        get(key){const r={};queueMicrotask(()=>{r.result=dropReads ? undefined : structuredClone(records.get(key));if(corruptReads && r.result instanceof ArrayBuffer)r.result=new TextEncoder().encode('[]').buffer;r.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.());});return r;},
        put(value,key){const r={};queueMicrotask(()=>{if(!dropWrites)records.set(key,structuredClone(value));r.result=key;r.onsuccess?.();queueMicrotask(()=>tx.oncomplete?.());});return r;}
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
  // Real shipped bytes with a deterministic event-based storage fixture.
  idbRecords.clear();let downloads=0;
  globalThis.fetch=async url=>{downloads++;return new Response(fs.readFileSync(`app/static/data/${String(url).replace('./data/','').split('?')[0]}`));};
  const persistent=await import('../app/static/db.js?prepare');
  const progress=[];
  const paused=await persistent.prepareOffline(manifest,{onProgress:p=>progress.push(p),shouldPause:()=>progress.length===3});
  assert.equal(paused.paused,true);assert.equal(paused.completed,3);assert.equal(downloads,3);count++;
  const finished=await persistent.prepareOffline(manifest,{onProgress:p=>progress.push(p)});
  assert.equal(finished.completed,32);assert.equal(finished.paused,false);assert.equal(downloads,32);
  for(const meta of [manifest.index_lite,manifest.wordforms_lookup,...manifest.shards])assert.ok(idbRecords.get(`${manifest.version}:${meta.sha256}`));
  assert.equal(idbRecords.get('manifest').version,manifest.version);
  const beforeResume=downloads;await persistent.prepareOffline(manifest);assert.equal(downloads,beforeResume);count++;
  for(const [key,value] of idbRecords)legacyRecords.set(key,structuredClone(value));
  idbRecords.clear();hasLegacy=true;
  globalThis.fetch=async()=>{throw new Error('offline legacy cache');};
  const migrated=await import('../app/static/db.js?legacy-migration');
  assert.equal((await migrated.loadManifest()).version,manifest.version);
  await migrated.prepareOffline(manifest);
  assert.equal(downloads,beforeResume);
  assert.equal(idbRecords.size,33);hasLegacy=false;count++;
  const mutable=structuredClone(manifest);
  const pinned=await persistent.prepareOffline(mutable,{onProgress:()=>{mutable.version='changed-during-preparation';}});
  assert.equal(pinned.version,manifest.version);assert.equal(idbRecords.get('manifest').version,manifest.version);count++;
  // A reload can read every asset with both network and Cache API unavailable.
  globalThis.fetch=async()=>{throw new Error('offline');};
  const completeOffline=await import('../app/static/db.js?complete-offline');
  for(const meta of [manifest.index_lite,manifest.wordforms_lookup,...manifest.shards])await completeOffline.loadJson(meta,manifest.version);
  count++;
  idbRecords.clear();dropWrites=true;
  globalThis.fetch=async url=>new Response(fs.readFileSync(`app/static/data/${String(url).replace('./data/','').split('?')[0]}`));
  await assert.rejects(persistent.prepareOffline(manifest),/IndexedDB.*回读/);dropWrites=false;count++;
  dropReads=true;
  await assert.rejects(persistent.prepareOffline(manifest),/IndexedDB.*回读/);dropReads=false;count++;
  idbRecords.clear();corruptReads=true;
  await assert.rejects(persistent.prepareOffline(manifest),/更新|损坏/);corruptReads=false;count++;
  idbRecords.clear();
  const badManifest={...manifest,index_lite:{...manifest.index_lite,sha256:'0'.repeat(64)}};
  await assert.rejects(persistent.prepareOffline(badManifest),/更新|损坏/);count++;
} finally {globalThis.fetch=originalFetch;delete globalThis.indexedDB;}
try {
  globalThis.indexedDB={open(){throw new Error('storage denied');}};
  globalThis.fetch=async()=>new Response(fs.readFileSync('app/static/data/index_lite.json'));
  const privateMode=await import('../app/static/db.js?storage-denied');
  assert.equal((await privateMode.loadDataset(manifest.index_lite,manifest.version)).length,24045);count++;
  await assert.rejects(privateMode.prepareOffline(manifest),/IndexedDB 不可用/);count++;
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
