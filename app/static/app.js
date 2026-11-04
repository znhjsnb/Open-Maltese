import {loadEntry,loadManifest,prepareOffline} from './db.js';
import {createPronouncer} from './audio.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const values = value => Array.isArray(value) ? value.join(' · ') : value;
const strata = {semitic:'闪米特语源',romance_sicilian_italian:'西西里 / 意大利语源',english:'英语借词',other_or_hybrid:'其他 / 混合',unspecified:'词源待核'};
const state = {manifest:null, bucket:'', prefix:'', tier:'', feature:'', stratum:'', query:'', offset:0,
  results:[], pages:new Map(), total:0, current:null, selected:-1, request:0, selection:0, english:false, scale:1,
  bookmarks:[], bookmarksOnly:false, sort:'alpha', loading:false};
let worker, debounce, toastTimer;
const pronunciation = createPronouncer({guide:showGuide,status:toast,activity:active=>{
  if (typeof document==='undefined') return;
  document.querySelectorAll('.audio-pill').forEach(b=>b.classList.remove('playing'));
  if (active) document.querySelector('.audio-pill[data-active="true"]')?.classList.add('playing');
}});

function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 3000); }
function button(label, pressed, onClick, className='') {
  const b = document.createElement('button'); b.textContent = label; b.className = className;
  b.setAttribute('aria-pressed',String(pressed)); b.onclick = onClick; return b;
}
export function mergeResultPage(pages, data) {
  pages.set(data.offset,data.results);
  const seen=new Set();
  return [...pages].sort(([a],[b])=>a-b).flatMap(([,rows])=>rows).filter(e=>!seen.has(e.id) && seen.add(e.id));
}
function requestSearch(reset=true, append=false) {
  if (!worker) return;
  clearTimeout(debounce);
  if (reset) state.offset = 0;
  if (!append) state.pages.clear();
  state.query = $('search').value;
  $('clear').hidden=!state.query;
  // Invalidates any pending shard response before the next worker reply.
  if (!append) state.selection++;
  state.loading=true;
  worker.postMessage({type:'search', requestId:++state.request, query:state.query,
    bucket:state.bucket,prefix:state.prefix,tier:state.tier,feature:state.feature,stratum:state.stratum,offset:state.offset,
    bookmarks:state.bookmarksOnly ? state.bookmarks : null,sort:state.sort});
}
function navigation() {
  $('letter-bar').replaceChildren(...['',...state.manifest.MALTESE_UI_BUCKETS_30].map(b =>
    button(b === '' ? '全部' : b === 'GĦ' ? 'Għ' : b,state.bucket === b,() => {
      state.bucket = b; state.prefix = ''; navigation(); requestSearch();
    })));
  const prefixes = Object.keys(state.manifest.sub_prefix_counts[state.bucket] || {});
  if (state.bucket === 'I') prefixes.sort((a,b) => Number(b === 'ie') - Number(a === 'ie'));
  $('sub-prefix-bar').replaceChildren(...(state.bucket ? [button('全部前缀',!state.prefix,() => {
    state.prefix=''; navigation(); requestSearch(); }),...prefixes.map(p => button(
    `${p} ${state.manifest.sub_prefix_counts[state.bucket][p]}`,state.prefix === p,() => {
      state.prefix=p; navigation(); requestSearch(); },p === 'ie' ? 'ie-prefix' : ''))] : []));
  const t = state.manifest.tier_counts;
  $('tier-filters').replaceChildren(...[['',`全部 ${state.manifest.total_lemmas.toLocaleString()}`],
    ['core',`Tier 1 双源核心 ${t['1'].toLocaleString()}`],['rich',`Tier 1+2 候选池 ${(t['1']+t['2']).toLocaleString()}`]]
    .map(([key,label]) => button(label,state.tier === key,() => {state.tier=key; navigation(); requestSearch();})));
  $('feature-filters').replaceChildren(...[['','全部特征'],['showcase',`精选样板 (${state.manifest.showcase_count})`],['root','有闪米特词根'],['loans','罗曼 / 英语借词'],['audio','有真人发音']]
    .map(([key,label])=>button(label,state.feature===key,()=>{state.feature=key;navigation();requestSearch();})));
  $('feature-filters').title='词根筛选指有实证共时辅音词根，不代表已核实历史闪米特语源。';
  $('stratum-filters').replaceChildren(...[['','全部语源'],...Object.entries(strata)].map(([key,label]) =>
    button(label,state.stratum === key,() => {state.stratum=key; navigation(); requestSearch();})));
}
function traceText(trace) {
  return `${trace.surface} → ${trace.lemma} · ${trace.tags.join(' · ')}`;
}
function renderList() {
  $('result-count').textContent = `${state.total.toLocaleString()} 个词目`;
  $('headword-list').replaceChildren(...state.results.map((entry,i) => {
    const row = document.createElement('button'); row.className='word-row word-item'; row.dataset.id=entry.id;
    row.setAttribute('aria-current',String(i === state.selected));
    row.innerHTML = `<span class="word"><span lang="mt">${esc(entry.word)}</span><span class="tier">T${entry.tier}</span></span><small>${esc(entry.pos_list.join(' / '))}　${esc(state.english ? entry.gloss_en[0] : entry.gloss_zh || entry.gloss_en[0])}</small>${entry.trace ? `<span class="trace-badge">${esc(entry.trace.surface)} → ${esc(entry.word)} · 词形还原</span>` : ''}`;
    row.onclick = () => selectEntry(i,true); return row;
  }));
  if (!state.results.length) $('headword-list').innerHTML='<p class="empty">没有匹配词目。请尝试其他拼写或清除筛选。</p>';
  $('previous-page').disabled = state.offset === 0;
  $('next-page').disabled = state.offset + 60 >= state.total;
  $('page-number').textContent = state.total ? `${Math.floor(state.offset/60)+1} / ${Math.ceil(state.total/60)}` : '0 / 0';
  $('page-input').max=Math.max(1,Math.ceil(state.total/60));
  $('page-input').value=Math.floor(state.offset/60)+1;
  $('page-go').disabled=!state.total;
}
async function selectEntry(i,reveal=false) {
  const index = state.results[i]; if (!index) return;
  state.selected=i; const ticket=++state.selection; pronunciation.stop(); renderList();
  state.current=null;updateBookmarkControls();
  document.querySelector('.word-row[aria-current="true"]')?.scrollIntoView({block:'nearest'});
  $('entry-card').setAttribute('aria-busy','true');
  try {
    const entry = await loadEntry(index,state.manifest);
    if (ticket !== state.selection) return;
    state.current=entry; renderEntry(entry,index.trace);
    $('content').scrollTop=0; if(reveal) document.body.classList.add('reading'); updatePinnedWord();
  } catch (error) {
    if (ticket !== state.selection) return;
    state.current=null; $('entry-card').innerHTML=`<p class="empty">${esc(error.message)}</p><button id="retry-entry">重试</button>`;
    $('retry-entry').onclick=() => selectEntry(i);
    updateBookmarkControls();updatePinnedWord();
  } finally { if (ticket === state.selection) $('entry-card').removeAttribute('aria-busy'); }
}
function section(title,content) { return `<section class="dimension"><h2>${title}</h2>${content}</section>`; }
const hasValue = value => Array.isArray(value) ? value.some(hasValue) : value != null && String(value).trim() !== '';
function dl(pairs) { const recorded=pairs.filter(([,v])=>hasValue(v)); return recorded.length ? `<dl>${recorded.map(([label,value]) => `<dt>${label}</dt><dd>${esc(values(value))}</dd>`).join('')}</dl>` : ''; }
function family(words) { return (words || []).map(w => `<button data-word="${esc(w)}" lang="mt">${esc(w)}</button>`).join(''); }
export function sourceChain(chain) {
  const relations={bor:'借入 / borrowed',inh:'继承 / inherited',der:'源自 / derived',cog:'同源 / cognate',calque:'仿译 / calque'};
  const lines=(chain || []).map(c=>{
    const name=c.template || c.name, a=c.args || {}, base=name?.replace(/\+$/,'');
    let relation=base,terms=[];
    if (['ety','etymon'].includes(base)) {
      relation=String(a['2'] || '').replace(/^:/,'');
      terms=Object.keys(a).filter(k=>/^\d+$/.test(k) && Number(k)>=3).sort((x,y)=>Number(x)-Number(y)).map(k=>a[k]);
    } else if (base==='cog') terms=[a['1'],a['2']].filter(hasValue);
    else if (relations[base]) terms=[a['2'],a['3']].filter(hasValue);
    if (relations[relation] && terms.length) return `${relations[relation]}：${terms.map(t=>String(t).replace(/^([^:]+):/, '$1 · ')).join(' · ')}`;
    return `${name}: ${Object.entries(a).sort(([x],[y])=>x.localeCompare(y)).map(([k,v])=>`${k}=${v}`).join(' · ')}`;
  });
  const unique=[...new Set(lines)];
  return unique.length ? `<ul class="source-chain">${unique.map(line=>`<li>${esc(line)}</li>`).join('')}</ul>` : '';
}
function hasMorphology(a) {
  return [a.roots,a.root_consonants,a.verb_forms_attested,a.plural_forms,a.collective_forms,a.singulative_forms,a.word_family,
    ...Object.values(a.verb_paradigm || {})].some(hasValue) || (hasValue(a.pattern_type) && a.pattern_type!=='unspecified');
}
export function renderAnalyses(analyses) {
  if (!analyses.some(hasMorphology)) return '<p class="muted">暂无已记录构词细分资料 / not recorded</p>';
  const cards=analyses.map((a,i)=>!hasMorphology(a) ? '' : `<section class="lexeme-analysis morphology-subentry" data-analysis-id="${esc(a.id)}"><h3>${analysisHeading(a,i)}</h3>
    ${dl([['性别 / 集合', [a.gender,a.collectivity].filter(Boolean)],['IPA',a.ipa],['共时词根',a.roots],['构词类型',a.pattern_type==='unspecified' ? null : a.pattern_type],['动词派生型',a.verb_forms_attested],['词汇复数',a.plural_forms],['集合形式',a.collective_forms],['个体形式',a.singulative_forms]])}
    ${(a.roots || []).map(r=>`<button data-root="${esc(r)}">#root:${esc(r)}</button>`).join('')}
    ${a.verb_paradigm ? dl(Object.entries(a.verb_paradigm)) : ''}
    ${a.senses.map(s=>`<div class="sense"><p>${esc(s.en_definition)}</p>${s.zh_definition ? `<p class="zh">${esc(s.zh_definition)}</p>` : ''}${s.mt_definition ? `<p lang="mt">${esc(s.mt_definition)}</p>` : ''}<span class="source">${esc(s.source)} · ${esc(s.review_status)}${s.translation_provenance ? ` · 译释：${esc(s.translation_provenance.definition_origin)} · ${esc(s.translation_provenance.review_status)}` : ''}</span></div>`).join('')}
    ${a.word_family?.length ? `<div class="family">${family(a.word_family)}</div>` : ''}
    ${a.definite_article ? dl([['定冠词',a.definite_article.form],['冠词来源',a.definite_article.source_type]]) : ''}
    <p class="source">${esc(a.source_record_id)} · source_attested</p></section>`).join('');
  const missing=analyses.filter(a=>!hasMorphology(a));
  return cards+(missing.length ? `<p class="source">其余共时来源子词位（${missing.map(a=>esc(a.id)).join(' · ')} · source_attested）暂无构词细分记录</p>` : '');
}
function renderMorphology(entry) {
  if(entry.lexeme_analyses.length>1) return renderAnalyses(entry.lexeme_analyses);
  const m=entry.morphology;
  const body=`${m.root_consonants ? `<button class="root-chip" data-root="${esc(m.root_consonants)}">#root:${esc(m.root_consonants)}</button>` : ''}${dl([['构词类型',m.pattern_type==='unspecified' ? null : m.pattern_type],['词根辅音',m.root_radicals],['动词派生型',m.verb_form],['未完成体',m.imperfect],['过去分词',m.past_participle],['动名词',m.verbal_noun],['复数',m.plural_forms],['集合形式',m.collective_form],['个体形式',m.singulative_form]])}${m.word_family?.length ? `<div class="family">${family(m.word_family)}</div>` : ''}${m.root_evidence?.length>1 ? `<div class="family">${m.root_evidence.slice(1).map(r=>`<button data-root="${esc(r.root)}">#root:${esc(r.root)}</button>`).join('')}</div>` : ''}`;
  return body || '<p class="muted">暂无已记录构词细分资料 / not recorded</p>';
}
function analysisHeading(a,i) {return `子词位 ${i+1} · ${esc(a.pos || '词性未标')} · ${esc(a.source)} · ${esc(a.source_record_id)}`;}
function hasInflection(a) {
  const nominal=['noun','adj','adjective','num','n.','n.m.','n.f.','adj.','num.'].includes(String(a.pos).toLowerCase());
  return [a.plural_forms,a.attested_forms,a.pronomi_mehmuzin,...Object.values(a.verb_paradigm || {})].some(hasValue) || (nominal && hasValue(a.definite_article?.form));
}
function inflectionBody(a) {
  const verb=['verb','v.','v'].includes(String(a.pos).toLowerCase()), nominal=['noun','adj','adjective','num','n.','n.m.','n.f.','adj.','num.'].includes(String(a.pos).toLowerCase());
  const v=a.verb_paradigm || {};
  const pairs=verb ? [['Perfett 3sg.m',v.perfett_3sg_m],['Imperfett 3sg.m',v.imperfett_3sg_m],['Imperattiv 2sg',v.imperattiv_2sg],['过去分词',v.past_participle],['动名词',v.verbal_noun]] : [];
  if (nominal) pairs.push(['复数 / plural',a.plural_forms],['定冠词 L-Artiklu',a.definite_article?.form]);
  const recorded=pairs.filter(([,v])=>v != null && v!=='' && (!Array.isArray(v)||v.length));
  const n=a.attested_forms?.length || 0;
  const caption=a.attested_form_count>n ? `来源屈折表节选（已展示 ${n} / 共 ${a.attested_form_count} 项 · 完整词形可通过搜索反查）` : `来源已记录形式（${n} 项）`;
  return `${dl(recorded)}${nominal && a.definite_article ? `<p class="source">${esc(a.definite_article.note)} · ${esc(a.definite_article.source_type)}</p>` : ''}${n ? `<p class="source">${caption}</p>${formsTable(a.attested_forms)}` : ''}${a.pronomi_mehmuzin?.length ? `<h4>Pronomi Mehmużin · 附着代词</h4>${formsTable(a.pronomi_mehmuzin)}` : ''}`;
}
export function renderInflections(entry) {
  if (entry.lexeme_analyses.length>1) {
    if (!entry.lexeme_analyses.some(hasInflection)) return '<p class="muted">暂无已记录屈折与附着形式 / not recorded</p>';
    const cards=entry.lexeme_analyses.map((a,i)=>hasInflection(a) ? `<section class="inflection-subentry" data-analysis-id="${esc(a.id)}"><h3>${analysisHeading(a,i)}</h3>${inflectionBody(a)}</section>` : '').join('');
    const missing=entry.lexeme_analyses.filter(a=>!hasInflection(a));
    return cards+(missing.length ? `<p class="source">其余子词位（${missing.map(a=>esc(a.id)).join(' · ')}）暂无额外屈折记录</p>` : '');
  }
  const a=entry.lexeme_analyses[0];
  if (!a) return '<p class="muted">暂无已记录形式 / not recorded</p>';
  // A sole lexeme can also have source-attested clitics in the compatibility field.
  const f=entry.inflection_and_clitics || {};
  const merged={...a,plural_forms:f.plural ?? a.plural_forms,definite_article:f.definite_article ?? a.definite_article,
    verb_paradigm:{...a.verb_paradigm,perfett_3sg_m:f.perfett_3sg_m ?? a.verb_paradigm?.perfett_3sg_m,
      imperfett_3sg_m:f.imperfett_3sg_m ?? a.verb_paradigm?.imperfett_3sg_m,imperattiv_2sg:f.imperattiv_2sg ?? a.verb_paradigm?.imperattiv_2sg},
    attested_forms:f.attested_forms ?? a.attested_forms,pronomi_mehmuzin:f.pronomi_mehmuzin ?? a.pronomi_mehmuzin};
  return hasInflection(merged) ? inflectionBody(merged) : '<p class="muted">暂无已记录屈折与附着形式 / not recorded</p>';
}
export function renderEtymology(entry) {
  const e=entry.etymology;
  const hasHistory=a=>hasValue(a.etymology_text || a.etymology_text_en) || a.etymology_templates?.length || a.source_chain?.length || (a.stratum && a.stratum!=='unspecified');
  const body=a=>`${a.stratum && a.stratum!=='unspecified' ? `<p>${esc(strata[a.stratum] || a.stratum)}</p>` : ''}${hasValue(a.etymology_text || a.etymology_text_en) ? `<p class="en">${esc(a.etymology_text || a.etymology_text_en)}</p>` : ''}${sourceChain([...(a.source_chain || []),...(a.etymology_templates || [])])}`;
  let text;
  if(entry.lexeme_analyses.length>1) {
    const analyses=entry.lexeme_analyses;
    text=analyses.some(hasHistory) ? analyses.map((a,i)=>hasHistory(a) ? `<section class="etymology-subentry" data-analysis-id="${esc(a.id)}"><h3>${analysisHeading(a,i)}</h3>${body(a)}<p class="source">${esc(a.source)} · source_attested · 共时词根不代表历史词源</p></section>` : '').join('') : '<p class="muted">词源待核 / 暂无历史词源实证 / not recorded</p>';
    const missing=analyses.filter(a=>!hasHistory(a));
    if(missing.length && missing.length<analyses.length) text+=`<p class="source">共时来源子词位（${missing.map(a=>esc(a.id)).join(' · ')}）未单列历史词源</p>`;
  } else text=hasHistory(e) ? `<div class="etymology-card">${body(e)}</div>` : '<p class="muted">词源待核 / 暂无历史词源实证 / not recorded</p>';
  return text+`<aside class="cognitive-aid-box"><p class="zh">学习助记：${esc(e.cognitive_memory_aid || '待补充 / not recorded')}</p>${e.cognitive_memory_aid_provenance ? `<p class="source">${esc(e.cognitive_memory_aid_provenance.source_type)} · ${esc(e.cognitive_memory_aid_provenance.review_status)}</p>` : ''}</aside>`;
}
export function renderSenses(senses) {
  return senses.map((s,i)=>`<div class="sense sense-card" id="sense-${i}" tabindex="-1"><h3>${i+1} · ${esc(s.pos || '')}</h3>${s.zh_definition ? `<p class="zh">${esc(s.zh_definition)}</p>` : ''}<p class="en">${esc(s.en_definition)}</p>${s.mt_definition ? `<p class="mt-definition" lang="mt">${esc(s.mt_definition)}</p>` : ''}<span class="source">${s.definition_origin==='authored_pedagogical' ? '教学编写 · authored_pedagogical · '+esc(s.review_status || 'phase2_reviewed') : `${esc(s.source)} · 来源释义 (licensed_source) · ${esc(s.review_status || 'source_attested')}`}</span>${s.translation_provenance ? `<span class="source translation-source">译释：${esc(s.translation_provenance.definition_origin)} · ${esc(s.translation_provenance.review_status)}</span>` : ''}</div>`).join('');
}
function renderEntry(entry,trace) {
  const h=entry.headword,m=entry.morphology,p=entry.pragmatics_and_cognates,e=entry.etymology;
  const multiple=entry.lexeme_analyses.length>1;
  const sources=h.source_presence.map(s => `<a href="${esc(state.manifest.sources[s]?.url || '#')}" target="_blank" rel="noreferrer">${esc(s)}</a>`).join(' / ');
  const senses=renderSenses(entry.senses);
  const ipa=[...new Set(entry.lexeme_analyses.filter(a=>a.ipa).map(a=>`${a.ipa} (${a.source})`))].join(' · ') || (h.ipa ? `${h.ipa} (${h.ipa_source})` : '音标暂缺 / IPA not recorded');
  const collocations=entry.senses.flatMap(s => s.collocations || []);
  const collocationHtml=collocations.length ? collocations.map(c=>`<p lang="mt">${esc(c.mt)}</p><p>${esc(c.en)}</p><p class="zh">${esc(c.zh)}</p><span class="source">${esc(c.source_type)}</span>`).join('') : '<p class="muted">搭配待补充 / no collocations recorded</p>';
  const scenarios = entry.dual_scenarios ? ['formal','colloquial'].map(key => {
    const s=entry.dual_scenarios[key]; if (!s) return '';
    const turns=key === 'colloquial' && Array.isArray(s.messages) && s.messages.length ? s.messages.map(turn=>`<div class="dialogue-turn"><h4>${esc(turn.speaker)}</h4><p lang="mt">${esc(turn.mt_spoken)}</p><button class="pronunciation" data-speak="${esc(turn.mt_spoken)}">◖♪ 朗读对话</button><p lang="mt">标准表达：${esc(turn.mt_standard)}</p><p>${esc(turn.en)}</p><p class="zh">${esc(turn.zh)}</p></div>`).join('') : `<p lang="mt">${esc(s.mt)}</p><button class="pronunciation" data-speak="${esc(s.mt)}">◖♪ 朗读例句</button><p>${esc(s.en)}</p>${s.zh ? `<p class="zh">${esc(s.zh)}</p>`:''}`;
    return `<div class="scenario"><h3>${key === 'formal' ? '书面表达 / written context' : '日常对话 / conversation'}</h3>${turns}${s.grammar_note ? `<p class="zh">${esc(s.grammar_note)}</p>` : ''}<span class="source">${esc(s.source_type)} · 教学编写 · ${esc(s.review_status || 'source_attested')} · ${esc(entry.dual_scenarios.review_status)}</span></div>`;
  }).join('') : '<p class="muted">暂无已编写语境 / examples not yet enriched</p>';
  $('entry-card').innerHTML = `${trace ? `<div id="morph-trace-banner" role="status">词形还原 / morphological trace<br>${esc(traceText(trace))}</div>` : ''}
    <div class="entry-top"><div><span class="small-label">IL-MALTI · 探索词的来处</span><h1 class="word-title" lang="mt">${esc(h.word)}</h1><p class="ipa">${esc(ipa)}</p></div><button id="pronounce-word" class="pronunciation audio-pill">◖♪ ${h.audio_url ? '真人录音' : '发音 / 指南'}</button></div>
    <div class="entry-meta"><span class="chip">Tier ${h.tier}</span><span class="chip">${esc(multiple ? `${entry.lexeme_analyses.length} 个独立子词位` : h.gender || '性别未标注')}</span><span class="chip">${esc(multiple ? '多来源历史词源' : strata[e.stratum])}</span></div>
    <nav class="sense-quick-chips" aria-label="义项速跳">${entry.senses.map((s,i)=>`<button class="sense-chip" data-sense="sense-${i}">${i+1} · ${esc(s.zh_definition || s.en_definition)}</button>`).join('')}</nav>
    ${section('01 · 词头与发音 / headword',`<p class="source">${sources} · 来源已收录（source_attested）</p>${h.audio_commons_url ? `<p><a href="${esc(h.audio_commons_url)}" target="_blank" rel="noreferrer">Wikimedia Commons · 作者与录音许可</a></p>` : ''}${dl([['音标来源',h.ipa_source],['集合 / 个体',h.collectivity],['录音说明',h.audio_note ? `${h.audio_note.note || ''} ${h.audio_note.file || ''} · 许可见 Commons 文件页` : null]])}`)}
    ${section('02 · 构词与词族 / morphology',renderMorphology(entry))}
    ${section('03 · 三语释义 / senses',senses || '<p class="muted">释义暂无实证 / not recorded</p>')}
    ${section('04 · 实用搭配 / collocations',collocationHtml)}
    ${section('05 · 双境表达 / two contexts',scenarios)}
    ${section('06 · 屈折与附着代词 / inflection & clitics',renderInflections(entry))}
    ${section('07 · 语用与同源词 / pragmatics & cognates',renderPragmatics(p))}
    ${section('08 · 历史词源 / etymology',renderEtymology(entry))}`;
  $('entry-card').querySelectorAll('.sense-chip').forEach(b=>b.onclick=()=>{
    const target=$(b.dataset.sense); target.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    target.focus({preventScroll:true}); target.classList.remove('pulse'); void target.offsetWidth; target.classList.add('pulse');
  });
  $('pronounce-word').onclick=() => playAudio($('pronounce-word'),h.word,h.audio_url);
  $('entry-card').querySelectorAll('[data-speak]').forEach(b => b.onclick=()=>playAudio(b,b.dataset.speak));
  $('entry-card').querySelectorAll('[data-word]').forEach(b => b.onclick=()=>searchDirect(b.dataset.word));
  $('entry-card').querySelectorAll('[data-root]').forEach(b => b.onclick=()=>searchDirect(`#root:${b.dataset.root}`));
  $('copy-markdown').onclick=()=>copyExport(false);
  $('copy-anki').onclick=()=>copyExport(true);
  $('entry-card').querySelectorAll('.pronunciation').forEach(b=>{
    b.classList.add('audio-pill');b.insertAdjacentHTML('beforeend','<span class="wave" aria-hidden="true"><span></span><span></span><span></span></span>');
  });
  updateBookmarkControls();
}
function renderPragmatics(p) {
  if(!p || ![p.register,p.synonyms,p.antonyms,p.cognates_and_false_friends].some(hasValue)) return '<p class="muted">暂无已记录语用资料 / not recorded</p>';
  return dl([['语域',p.register],['同义词',p.synonyms],['反义词',p.antonyms]])+sourceChain(p.cognates_and_false_friends);
}
function playAudio(button,text,url) {
  document.querySelectorAll('[data-active]').forEach(b=>delete b.dataset.active);
  button.dataset.active='true';pronunciation.play(text,url);
}
function formsTable(forms) {
  if (!forms?.length) return '<p class="muted">暂无已记录形式 / not recorded</p>';
  return `<table class="paradigm"><thead><tr><th>形式 / form</th><th>标记与来源 / evidence</th></tr></thead><tbody>${forms.map(f=>`<tr><td lang="mt">${esc(f.form)}</td><td>${esc((f.tags || Object.entries(f.features || {}).map(([k,v])=>`${k}=${v}`)).join(', '))}<br><span class="source">${esc(f.source)}</span></td></tr>`).join('')}</tbody></table>`;
}
function searchDirect(text) {
  state.bucket=state.prefix=state.tier=state.feature=state.stratum=''; $('search').value=text; navigation(); requestSearch();
}
export function currentWorkerError(data,requestId) {
  return data.type==='error' && (data.requestId == null || data.requestId===requestId);
}
export function pronunciationGraphemes(text) {
  return String(text).normalize('NFC').toLowerCase().match(/għ|ie|[\s\S]/gu) || [];
}
function showGuide(text) {
  const entry=state.current, h=entry?.headword;
  const special=[['ċ','/tʃ/ (ch)'],['ġ','/dʒ/ (j)'],['għ','影响邻近元音；音值随位置与语境变化'],['ħ','/h/ 或 /ħ/，取决于分析体系'],['ie','/iː/，部分语境有其他实现'],['q','/ʔ/ 声门塞音'],['x','/ʃ/ (sh)'],['ż','/z/'],['z','/ts/']].filter(([g])=>pronunciationGraphemes(text).includes(g));
  $('pronunciation-content').innerHTML=`<p lang="mt"><strong>${esc(text)}</strong></p><p>${h?.word === text && h.ipa ? `来源音标：${esc(h.ipa)} (${esc(h.ipa_source)})` : '以下是拼写字素提示，不是此词的实证音标。'}</p>${dl(special)}<p>当前未能播放真人录音，浏览器也未提供可用的马耳他语语音。不会使用英语或意大利语代读。</p><p>在 Microsoft Edge 中检查朗读的马耳他语选项（Grace / Joseph）。只有它们实际出现在本页的 speechSynthesis 语音列表时，发音按钮才能调用；Edge 朗读与网页可用语音并不一定相同。</p><p>也可安装 eSpeak-NG，以 <code>espeak-ng -v mt "${esc(h?.word || 'ktieb')}"</code> 测试。命令行安装不保证浏览器自动识别，需要系统语音接口支持。项目 README 与 <code>scripts/check_maltese_tts.ps1</code> 提供检测步骤。</p><p class="source">无可用马语语音时，可保留音标指南，并优先试听带真人录音的词条。</p>`;
  if (!$('pronunciation-guide-popover').open) $('pronunciation-guide-popover').showModal();
}
export function exportText(entry,anki=false,manifest=state.manifest) {
  const h=entry.headword;
  const clean = t => String(t || '').replace(/[\t\r\n]+/g,' ');
  const usedSources=[...new Set([...h.source_presence,...entry.lexeme_analyses.flatMap(a=>(a.attested_forms || []).map(f=>f.source))])];
  const sources=usedSources.map(source=>{
    const meta=manifest?.sources[source];
    return `${source} ${meta?.license || (source==='gabra' ? 'CC BY 3.0' : 'CC BY-SA 4.0')} ${meta?.url || ''}${meta?.license_note ? ' '+meta.license_note : ''}`;
  }).join('; ');
  const review=[h.editorial_status,...entry.senses.map(s=>s.review_status),entry.dual_scenarios?.review_status].filter(Boolean).filter((s,i,a)=>a.indexOf(s)===i).join('; ');
  const analyses=entry.lexeme_analyses.map(a=>`${a.source} [${a.source_record_id}] POS=${a.pos}; etymology=${a.etymology_number ?? 'unspecified'}; gender=${a.gender || 'unspecified'}; collectivity=${a.collectivity || 'unspecified'}; IPA=${a.ipa || 'not recorded'}; roots=${a.roots.join(', ')}; stratum=${a.stratum}; plural=${(a.plural_forms || []).join(', ')}; paradigm=${JSON.stringify(a.verb_paradigm)}; senses=${a.senses.map(s=>`${s.en_definition}${s.zh_definition ? ' / '+s.zh_definition : ''}${s.mt_definition ? ' / '+s.mt_definition : ''}${s.translation_provenance ? ' (authored_pedagogical, phase2_reviewed)' : ''}`).join('; ')}`).join('\n');
  if (anki) return [h.word,h.ipa,entry.senses.map(s=>s.en_definition).join('; '),entry.senses.map(s=>s.zh_definition).filter(Boolean).join('; '),sources,`Tier ${h.tier}`,review,h.audio_commons_url,analyses].map(clean).join('\t');
  const m=entry.morphology,f=entry.inflection_and_clitics,p=entry.pragmatics_and_cognates,e=entry.etymology;
  const multiple=entry.lexeme_analyses.length>1;
  const lines=[`# ${h.word}`,`Sources: ${sources}`,`Review: ${review}`,`Audio attribution: ${h.audio_commons_url || 'not recorded'}`,`Lexeme analyses:\n${analyses}`,`01 · ${h.ipa || 'IPA not recorded'} · Tier ${h.tier} · ${h.source_presence.join(', ')}`,
    multiple ? '02 · Morphology: see each lexeme analysis above' : `02 · Root: ${m.root_consonants || 'not recorded'} · ${m.pattern_type}`, `Family: ${(m.word_family || []).join(', ')}`,
    '03 · Senses',...entry.senses.map(s=>`- ${s.en_definition}${s.zh_definition ? ' / '+s.zh_definition : ''} (${s.pos || 'teaching'}, ${s.source}, ${s.definition_origin}, ${s.review_status || h.editorial_status})`),
    '04 · Collocations',...entry.senses.flatMap(s=>(s.collocations || []).map(c=>`${c.mt} / ${c.en} / ${c.zh} (${c.source_type}, ${c.review_status || 'pending_linguistic_review'})`)),
    '05 · Contexts',...Object.values(entry.dual_scenarios || {}).filter(s=>s?.mt).map(s=>`${s.mt}\n${s.en} (${s.source_type}, ${s.review_status || entry.dual_scenarios.review_status})`),
    '06 · Inflection',multiple ? 'See each lexeme analysis above' : `Perfect: ${f.perfett_3sg_m || 'not recorded'}; imperfect: ${f.imperfett_3sg_m || 'not recorded'}; imperative: ${f.imperattiv_2sg || 'not recorded'}; plural: ${(f.plural || []).join(', ')}`,
    '07 · Pragmatics',`Register: ${(p?.register || []).join(', ')}; synonyms: ${(p?.synonyms || []).join(', ')}; antonyms: ${(p?.antonyms || []).join(', ')}`,
    '08 · Etymology',multiple ? 'See each lexeme analysis above' : e.etymology_text_en || 'not recorded',`Discovery stratum: ${e.stratum}`,`Learner mnemonic: ${e.cognitive_memory_aid || 'not recorded'} (${e.cognitive_memory_aid_provenance?.source_type || 'not recorded'})`];
  return lines.join('\n\n');
}
async function copyExport(anki) {
  if (!state.current) return;
  try { await navigator.clipboard.writeText(exportText(state.current,anki)); toast(anki ? '已复制 Anki TSV（9 列）' : '已复制 Markdown'); }
  catch { toast('浏览器未允许剪贴板访问。请在本机 localhost 页面重试。'); }
}
function readStorage(key,fallback) {
  try {return JSON.parse(localStorage.getItem(key)) ?? fallback;} catch {return fallback;}
}
function writeStorage(key,value) {
  try {localStorage.setItem(key,JSON.stringify(value));} catch { /* private mode */ }
}
function preferences() {
  const defaults={theme:'white',scale:1,language:'trilingual',font:'sans',density:'normal'};
  const saved=readStorage('open-malti-preferences',{});
  let prefs={...defaults,...saved,language:saved.language || (saved.english ? 'en' : 'trilingual')};
  function apply(patch={}) {
    prefs={...prefs,...patch};
    for (const [key,options] of Object.entries({theme:['white','sepia','grey','night'],language:['trilingual','bilingual','en'],font:['sans','serif','mono','legible'],density:['compact','normal','spacious']})) {
      if (!options.includes(prefs[key])) prefs[key]=defaults[key];
    }
    prefs.scale=Number.isFinite(Number(prefs.scale)) ? Math.max(.85,Math.min(1.3,Number(prefs.scale))) : 1;
    state.scale=prefs.scale; state.english=prefs.language==='en';
    document.body.dataset.theme=prefs.theme;
    document.body.dataset.language=prefs.language;
    document.body.classList.toggle('english-mode',state.english);
    const root=document.documentElement;
    root.dataset.readingPaper=prefs.theme; root.dataset.readingFont=prefs.font; root.dataset.readingDensity=prefs.density;
    root.style.setProperty('--scale',prefs.scale); root.style.setProperty('--font-scale',prefs.scale);
    $('theme').value=prefs.theme;
    $('font-size-value').textContent=`${Math.round(prefs.scale*100)}%`;
    $('language-mode').textContent=state.english ? 'English–Maltese' : prefs.language==='bilingual' ? '中英双语' : '马–中–英';
    $('language-mode').setAttribute('aria-pressed',String(state.english));
    $('theme-toggle').setAttribute('aria-pressed',String(prefs.theme==='night'));
    for (const mode of ['trilingual','bilingual','en']) $('lang-'+mode).setAttribute('aria-pressed',String(mode===prefs.language));
    for (const [attr,key] of [['font-family','font'],['density','density'],['paper','theme']]) {
      document.querySelectorAll(`[data-${attr}]`).forEach(b=>b.setAttribute('aria-pressed',String(b.getAttribute('data-'+attr)===prefs[key])));
    }
    writeStorage('open-malti-preferences',{...prefs,english:state.english});
    if (state.manifest) renderList();
  }
  $('theme').onchange=()=>apply({theme:$('theme').value});
  for (const id of ['font-down','font-decrease']) $(id).onclick=()=>apply({scale:prefs.scale-.05});
  for (const id of ['font-up','font-increase']) $(id).onclick=()=>apply({scale:prefs.scale+.05});
  $('language-mode').onclick=()=>apply({language:state.english ? 'trilingual' : 'en'});
  for (const mode of ['trilingual','bilingual','en']) $('lang-'+mode).onclick=()=>apply({language:mode});
  for (const [attr,key] of [['font-family','font'],['density','density'],['paper','theme']]) {
    document.querySelectorAll(`[data-${attr}]`).forEach(b=>b.onclick=()=>apply({[key]:b.getAttribute('data-'+attr)}));
  }
  $('typo-reset').onclick=()=>apply(defaults);
  $('theme-toggle').onclick=()=>apply({theme:prefs.theme==='night' ? 'white' : 'night'});
  $('typography-btn').onclick=()=>{
    if ($('typography-panel').open) $('typography-panel').close();
    else { $('typography-panel').showModal(); $('typography-btn').setAttribute('aria-expanded','true'); }
  };
  $('typography-close').onclick=()=>$('typography-panel').close();
  $('typography-panel').addEventListener('close',()=>{$('typography-btn').setAttribute('aria-expanded','false');$('typography-btn').focus({preventScroll:true});});
  apply();
}
function updateBookmarkControls() {
  $('bookmark-count').textContent=state.bookmarks.length;
  $('bookmarks').setAttribute('aria-pressed',String(state.bookmarksOnly));
  $('save').disabled=!state.current;
  $('copy-markdown').disabled=$('copy-anki').disabled=!state.current;
  const saved=!!state.current && state.bookmarks.includes(state.current.id);
  $('save').setAttribute('aria-pressed',String(saved)); $('save').textContent=saved ? '★' : '☆';
}
function updatePinnedWord() {
  const title=document.querySelector('#entry-card h1.word-title'), toolbar=document.querySelector('.content-toolbar');
  const pinned=$('toolbar-pinned-word');
  pinned.hidden=!title || title.getBoundingClientRect().bottom>toolbar.getBoundingClientRect().bottom;
  $('breadcrumb').hidden=!pinned.hidden;
  if (title && pinned.dataset.word!==state.current?.id) {
    pinned.dataset.word=state.current?.id || '';
    pinned.innerHTML=`<strong lang="mt">${esc(title.textContent)}</strong><button class="audio-pill" aria-label="朗读当前词">◖♪<span class="wave" aria-hidden="true"><span></span><span></span><span></span></span></button>`;
    pinned.querySelector('button').onclick=()=>{if(state.current)playAudio(pinned.querySelector('button'),state.current.headword.word,state.current.headword.audio_url);};
  }
}
function workspace() {
  const bookmarks=readStorage('open-malti-bookmarks',[]);
  state.bookmarks=Array.isArray(bookmarks) ? [...new Set(bookmarks.filter(id=>typeof id==='string'))] : [];
  $('save').onclick=()=>{
    if (!state.current) return;
    const id=state.current.id;
    state.bookmarks=state.bookmarks.includes(id) ? state.bookmarks.filter(b=>b!==id) : [...state.bookmarks,id];
    writeStorage('open-malti-bookmarks',state.bookmarks); updateBookmarkControls();
    if (state.bookmarksOnly) requestSearch();
  };
  $('bookmarks').onclick=()=>{state.bookmarksOnly=!state.bookmarksOnly;updateBookmarkControls();requestSearch();};
  $('sort-order').onchange=()=>{state.sort=$('sort-order').value;requestSearch();};
  $('copy-markdown').onclick=()=>copyExport(false); $('copy-anki').onclick=()=>copyExport(true);
  $('clear').onclick=()=>{$('search').value='';requestSearch();$('search').focus();};
  $('page-go').onclick=()=>{const n=Number($('page-input').value);if(Number.isFinite(n)){state.offset=(Math.max(1,Math.min(Math.ceil(state.total/60),Math.floor(n)))-1)*60;requestSearch(false);}};
  $('page-input').onkeydown=e=>{if(e.key==='Enter') $('page-go').click();};
  $('headword-list').addEventListener('scroll',()=>{
    const list=$('headword-list');
    if (!state.loading && state.offset+60<state.total && list.scrollTop>0 && list.scrollTop+list.clientHeight>=list.scrollHeight-80) {
      state.offset+=60;requestSearch(false,true);
    }
  });
  $('content').addEventListener('scroll',updatePinnedWord,{passive:true});
  window.addEventListener('resize',updatePinnedWord);
  $('back').onclick=()=>{document.body.classList.remove('reading','focus-mode');$('focus').setAttribute('aria-pressed','false');$('search').focus();};
  $('focus').onclick=()=>{
    const active=document.body.classList.toggle('focus-mode');$('focus').setAttribute('aria-pressed',String(active));updatePinnedWord();
  };
  const resizer=$('resizer');let width=360,grab;
  function setWidth(value,persist=false) {
    width=Math.max(280,Math.min(640,Number(value)||360));
    document.documentElement.style.setProperty('--sidebar-width',width+'px');
    resizer.setAttribute('aria-valuenow',width);resizer.setAttribute('aria-valuetext',`${width} 像素`);
    if(persist) writeStorage('open-malti-sidebar-width',width);
  }
  setWidth(readStorage('open-malti-sidebar-width',360));
  resizer.onpointerdown=e=>{
    if(e.button!==0 || window.innerWidth<=760) return;
    e.preventDefault();grab={id:e.pointerId,x:e.clientX,width};resizer.setPointerCapture(e.pointerId);document.body.classList.add('resizing');
  };
  resizer.onpointermove=e=>{if(grab?.id===e.pointerId)setWidth(grab.width+e.clientX-grab.x);};
  const finish=e=>{
    if(grab?.id!==e.pointerId)return;
    grab=null;document.body.classList.remove('resizing');setWidth(width,true);
    if(resizer.hasPointerCapture(e.pointerId))resizer.releasePointerCapture(e.pointerId);
    updatePinnedWord();
  };
  for(const name of ['pointerup','pointercancel','lostpointercapture'])resizer.addEventListener(name,finish);
  resizer.ondblclick=()=>setWidth(360,true);
  resizer.onkeydown=e=>{
    const value={ArrowLeft:width-(e.shiftKey?40:10),ArrowRight:width+(e.shiftKey?40:10),Home:280,End:640,Enter:360}[e.key];
    if(value===undefined)return;e.preventDefault();e.stopPropagation();setWidth(value,true);
  };
  let preparing=false,paused=false;
  $('offline').onclick=async()=>{
    if(preparing){paused=true;$('offline').textContent='正在暂停…';return;}
    preparing=true;paused=false;
    try {
      const result=await prepareOffline(state.manifest,{onProgress:({completed,total})=>{$('offline').textContent=`${completed}/${total} · 暂停`;},shouldPause:()=>paused});
      $('offline').textContent=result.paused ? '继续离线准备' : '离线词库已就绪 · 32/32';
      toast(result.paused ? '已暂停，下次会继续使用已保存的资产' : '32 项词库资产已校验并持久保存；录音仍需网络。');
    } catch(error){$('offline').textContent='重试离线准备';toast(error.message);}
    finally{preparing=false;}
  };
  updateBookmarkControls();
}
function study() {
  let queue=[],position=0,ticket=0,current,grab;
  const dialog=$('study'),card=$('flashcard');
  const savedKnown=readStorage('open-malti-study-known',[]);
  const known=new Set(Array.isArray(savedKnown)?savedKnown:[]);
  function flip(value=!card.classList.contains('flipped')) {
    card.classList.toggle('flipped',value);card.setAttribute('aria-pressed',String(value));
    card.querySelector('.flashcard-front').setAttribute('aria-hidden',String(value));
    card.querySelector('.flashcard-back').setAttribute('aria-hidden',String(!value));
  }
  async function show() {
    const task=++ticket;current=null;flip(false);
    $('study-known').disabled=$('study-again').disabled=$('study-open').disabled=true;
    $('card-word').textContent='…';$('card-phonetic').textContent='';$('card-meaning').textContent='';
    $('study-progress').textContent=`${position+1} / ${queue.length} · 本机已记住 ${known.size} 词`;
    try {
      const entry=await loadEntry(queue[position],state.manifest);
      if(task!==ticket || !dialog.open)return;
      current=entry;$('card-word').textContent=entry.headword.word;$('card-phonetic').textContent=entry.headword.ipa || '';
      $('card-meaning').innerHTML=entry.senses.slice(0,3).map(s=>`<p>${esc(s.zh_definition || s.en_definition)}</p>`).join('')+`<p class="source">${esc(entry.morphology.root_consonants || entry.morphology.pattern_type || '构词暂无实证')}</p>`;
      $('study-known').disabled=$('study-again').disabled=$('study-open').disabled=false;
    } catch(error){if(task===ticket){$('card-word').textContent='暂未载入';$('card-meaning').textContent=error.message;}}
  }
  function open(daily=false) {
    if(!state.results.length)return toast('先搜索或选择一个词。');
    queue=[...state.results];position=daily ? Math.floor(Date.now()/86400000)%queue.length : 0;
    $('study-title').textContent=daily ? '每日一词' : '抽认卡片';
    dialog.showModal();show();
  }
  $('daily').onclick=()=>open(true);$('practice').onclick=()=>open();
  $('close-study').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{ticket++;current=null;dialog.style.transform='';});
  card.onclick=()=>{if(current)flip();};
  card.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();if(current)flip();}};
  $('study-again').onclick=()=>{position=(position+1)%queue.length;show();};
  $('study-known').onclick=()=>{if(!current)return;known.add(current.id);writeStorage('open-malti-study-known',[...known]);position=(position+1)%queue.length;show();};
  $('study-open').onclick=()=>{if(!current)return;const word=current.headword.word;dialog.close();searchDirect(word);};
  const handle=$('study-grabber');
  handle.onpointerdown=e=>{if(e.button!==0)return;grab={id:e.pointerId,y:e.clientY,lastY:e.clientY,time:e.timeStamp,velocity:0,dy:0};handle.setPointerCapture(e.pointerId);dialog.style.transition='none';};
  handle.onpointermove=e=>{
    if(grab?.id!==e.pointerId)return;
    grab.velocity=(e.clientY-grab.lastY)/Math.max(1,e.timeStamp-grab.time);grab.lastY=e.clientY;grab.time=e.timeStamp;grab.dy=Math.max(0,e.clientY-grab.y);
    if(!matchMedia('(prefers-reduced-motion: reduce)').matches)dialog.style.transform=`translateY(${grab.dy}px)`;
  };
  const finish=e=>{
    if(grab?.id!==e.pointerId)return;
    const close=e.type!=='pointercancel' && grab.dy>10 && grab.dy+grab.velocity*180>100;
    grab=null;dialog.style.transition='transform 250ms var(--ease)';dialog.style.transform='';
    if(handle.hasPointerCapture(e.pointerId))handle.releasePointerCapture(e.pointerId);
    if(close)dialog.close();
  };
  for(const name of ['pointerup','pointercancel','lostpointercapture'])handle.addEventListener(name,finish);
}
async function start() {
  preferences();workspace();study();
  $('close-pronunciation').onclick=()=>$('pronunciation-guide-popover').close();
  $('search').addEventListener('input',()=>{state.selection++; state.request++; clearTimeout(debounce); debounce=setTimeout(()=>requestSearch(),100);});
  $('previous-page').onclick=()=>{state.offset-=60;requestSearch(false);};
  $('next-page').onclick=()=>{state.offset+=60;requestSearch(false);};
  document.addEventListener('keydown',event=>{
    if (document.querySelector('dialog[open]')) return;
    const typing=event.target.matches('input,textarea,select') || event.target.isContentEditable;
    if (event.key === '/' && !typing) {event.preventDefault();document.body.classList.remove('reading','focus-mode');$('focus').setAttribute('aria-pressed','false');$('search').focus();}
    if (event.key === 'Escape') {document.body.classList.remove('focus-mode');$('focus').setAttribute('aria-pressed','false');$('search').blur();}
    if (['ArrowDown','ArrowUp'].includes(event.key) && !event.altKey && !event.ctrlKey && !$('pronunciation-guide-popover').open && (!typing || event.target === $('search'))) {
      event.preventDefault(); const next=state.selected+(event.key === 'ArrowDown' ? 1 : -1);
      if (next>=0 && next<state.results.length) selectEntry(next,true);
      else if (event.key === 'ArrowDown' && state.offset+60<state.total) {state.offset+=60;requestSearch(false);}
      else if (event.key === 'ArrowUp' && state.offset>0) {state.offset-=60;requestSearch(false);}
    }
  });
  try {
    state.manifest=await loadManifest(); navigation();
    $('offline').disabled=false;
    $('inventory-note').textContent=`${state.manifest.total_lemmas.toLocaleString()} 个词头 · ${state.manifest.wordform_surface_count.toLocaleString()} 个反查表面形 · Ġabra MDX CC BY 3.0 / Wiktionary CC BY-SA 4.0`;
    worker=new Worker('./worker.js',{type:'module'});
    worker.onerror=()=>{$('result-count').textContent='检索器加载失败，请刷新页面。';};
    worker.onmessage=({data})=>{
      if (data.type === 'ready') {$('search').disabled=false;$('wordforms-status').textContent='基础检索已就绪 · 反查表后台载入中…';requestSearch();}
      if (data.type === 'wordforms-ready') $('wordforms-status').textContent='词头与词形反查均已就绪';
      if (data.type === 'wordforms-error') $('wordforms-status').textContent='基础检索可用 · 反查表暂不可用：'+data.message;
      if (currentWorkerError(data,state.request)) {state.loading=false;toast(data.message);$('result-count').textContent=data.message;}
      if (data.type !== 'results' || data.requestId !== state.request) return;
      const selectedId=state.results[state.selected]?.id || state.current?.id, previousOffset=state.offset;
      const previousTrace=state.results[state.selected]?.trace;
      state.loading=false;
      const firstPage=!state.pages.size;
      state.results=mergeResultPage(state.pages,data); state.total=data.total; state.offset=data.offset;
      state.selected=firstPage ? -1 : state.results.findIndex(e=>e.id===selectedId);
      $('search-time').textContent=`${data.elapsed.toFixed(1)} ms`; renderList();
      if(firstPage || previousOffset!==data.offset) $('headword-list').scrollTop=0;
      if (state.results.length) {
        if(state.selected<0) selectEntry(0);
        else if(state.current && JSON.stringify(previousTrace)!==JSON.stringify(state.results[state.selected].trace)) {renderEntry(state.current,state.results[state.selected].trace);updatePinnedWord();}
      } else {state.current=null; pronunciation.stop();$('entry-card').removeAttribute('aria-busy');$('entry-card').innerHTML='<p class="empty">请尝试其他词形，或清除字母、层级与语源筛选。</p>';updateBookmarkControls();updatePinnedWord();}
    };
    worker.postMessage({type:'init',manifest:state.manifest});
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(()=>{});
  } catch(error) { $('result-count').textContent=error.message; $('entry-card').textContent=error.message; }
}
if (typeof document !== 'undefined') start();
