import {loadEntry,loadManifest} from './db.js';
import {createPronouncer} from './audio.js';

const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nullable = value => value == null || value === '' ? '<span class="muted">暂无实证 / not recorded</span>' : esc(value);
const values = value => Array.isArray(value) ? value.join(' · ') : value;
const strata = {semitic:'闪米特语源',romance_sicilian_italian:'西西里 / 意大利语源',english:'英语借词',other_or_hybrid:'其他 / 混合',unspecified:'词源待核'};
const state = {manifest:null, bucket:'', prefix:'', tier:'', feature:'', stratum:'', query:'', offset:0,
  results:[], total:0, current:null, selected:-1, request:0, selection:0, english:false, scale:1};
let worker, debounce, toastTimer;
const pronunciation = createPronouncer({guide:showGuide,status:toast});

function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 3000); }
function button(label, pressed, onClick, className='') {
  const b = document.createElement('button'); b.textContent = label; b.className = className;
  b.setAttribute('aria-pressed',String(pressed)); b.onclick = onClick; return b;
}
function requestSearch(reset=true) {
  if (!worker) return;
  if (reset) state.offset = 0;
  state.query = $('search').value;
  // Invalidates any pending shard response before the next worker reply.
  state.selection++;
  worker.postMessage({type:'search', requestId:++state.request, query:state.query,
    bucket:state.bucket,prefix:state.prefix,tier:state.tier,feature:state.feature,stratum:state.stratum,offset:state.offset});
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
    const row = document.createElement('button'); row.className='word-row'; row.dataset.id=entry.id;
    row.setAttribute('aria-current',String(i === state.selected));
    row.innerHTML = `<span class="word"><span lang="mt">${esc(entry.word)}</span><span class="tier">T${entry.tier}</span></span><small>${esc(entry.pos_list.join(' / '))}　${esc(state.english ? entry.gloss_en[0] : entry.gloss_zh || entry.gloss_en[0])}</small>${entry.trace ? `<span class="trace-badge">${esc(entry.trace.surface)} → ${esc(entry.word)} · 词形还原</span>` : ''}`;
    row.onclick = () => selectEntry(i); return row;
  }));
  if (!state.results.length) $('headword-list').innerHTML='<p class="empty">没有匹配词目。请尝试其他拼写或清除筛选。</p>';
  $('previous-page').disabled = state.offset === 0;
  $('next-page').disabled = state.offset + 60 >= state.total;
  $('page-number').textContent = state.total ? `${Math.floor(state.offset/60)+1} / ${Math.ceil(state.total/60)}` : '0 / 0';
}
async function selectEntry(i) {
  const index = state.results[i]; if (!index) return;
  state.selected=i; const ticket=++state.selection; pronunciation.stop(); renderList();
  document.querySelector('.word-row[aria-current="true"]')?.scrollIntoView({block:'nearest'});
  $('entry-card').setAttribute('aria-busy','true');
  try {
    const entry = await loadEntry(index,state.manifest);
    if (ticket !== state.selection) return;
    state.current=entry; renderEntry(entry,index.trace);
  } catch (error) {
    if (ticket !== state.selection) return;
    state.current=null; $('entry-card').innerHTML=`<p class="empty">${esc(error.message)}</p><button id="retry-entry">重试</button>`;
    $('retry-entry').onclick=() => selectEntry(i);
  } finally { if (ticket === state.selection) $('entry-card').removeAttribute('aria-busy'); }
}
function section(title,content) { return `<section class="dimension"><h2>${title}</h2>${content}</section>`; }
function dl(pairs) { return `<dl>${pairs.map(([label,value]) => `<dt>${label}</dt><dd>${nullable(values(value))}</dd>`).join('')}</dl>`; }
function compactDl(pairs) {
  const active = pairs.filter(([,v]) => v != null && v !== '' && (!Array.isArray(v) || v.length > 0));
  return active.length ? dl(active) : '';
}
function family(words) { return (words || []).map(w => `<button data-word="${esc(w)}" lang="mt">${esc(w)}</button>`).join(''); }
function sourceChain(chain) {
  if (!chain?.length) return '';
  return `<ul class="source-chain">${chain.map(c => `<li>${esc(c.template)}: ${esc(Object.entries(c.args).map(([k,v])=>`${k}=${v}`).join(' · '))}</li>`).join('')}</ul>`;
}
export function renderAnalyses(analyses) {
  return analyses.map((a,i)=>{
    const isVerb = /verb|^v\.?$/i.test(a.pos || '');
    const morphPairs = [
      ['性别 / 集合', [a.gender,a.collectivity].filter(Boolean)],
      ['IPA', a.ipa],
      ['共时词根', a.roots],
      ['构词类型', a.pattern_type !== 'unspecified' ? a.pattern_type : null],
      ...(isVerb ? [['动词派生型', a.verb_forms_attested]] : [['词汇复数', a.plural_forms]]),
      ['集合形式', a.collective_forms],
      ['个体形式', a.singulative_forms],
      ['历史词源', a.stratum && a.stratum !== 'unspecified' ? strata[a.stratum] : null],
    ];
    return `<section class="lexeme-analysis"><h3>子词位 ${i+1} · ${esc(a.pos || '词性未标')} · ${esc(a.source)}${a.etymology_number != null ? ` · 词源 ${esc(a.etymology_number)}` : ''}</h3>
    ${compactDl(morphPairs) || dl([['词源状态', strata[a.stratum] || '来源已收录']])}
    ${(a.roots || []).map(r=>`<button data-root="${esc(r)}">#root:${esc(r)}</button>`).join('')}
    ${a.verb_paradigm ? compactDl(Object.entries(a.verb_paradigm)) : ''}
    ${a.senses.map(s=>`<div class="sense"><p>${esc(s.en_definition)}</p>${s.zh_definition ? `<p class="zh">${esc(s.zh_definition)}</p>` : ''}${s.mt_definition ? `<p lang="mt">${esc(s.mt_definition)}</p>` : ''}<span class="source">${esc(s.source)} · ${esc(s.review_status)}${s.translation_provenance ? ` · 译释：${esc(s.translation_provenance.definition_origin)} · ${esc(s.translation_provenance.review_status)}` : ''}</span></div>`).join('')}
    <div class="family">${family(a.word_family)}</div>
    ${a.definite_article ? compactDl([['定冠词',a.definite_article.form],['冠词来源',a.definite_article.source_type]]) : ''}
    ${a.attested_forms?.length ? `<p class="source">来源屈折表节选 · 完整词形可通过搜索反查</p>${formsTable(a.attested_forms)}` : ''}${a.pronomi_mehmuzin?.length ? `<h3>Pronomi Mehmużin</h3>${formsTable(a.pronomi_mehmuzin)}` : ''}
    ${a.etymology_text ? `<p>${esc(a.etymology_text)}</p>` : ''}<p class="source">${esc(a.source_record_id)} · source_attested</p></section>`;
  }).join('');
}
function renderEntry(entry,trace) {
  const h=entry.headword,m=entry.morphology,f=entry.inflection_and_clitics,p=entry.pragmatics_and_cognates,e=entry.etymology;
  const analyses=entry.lexeme_analyses || [];
  const multiple=analyses.length>1;
  const posSet=[...new Set(analyses.map(a=>(a.pos||'').toLowerCase()).filter(Boolean))];
  const isVerbOnly=posSet.length>0 && posSet.every(pos=>/verb|^v\.?$/.test(pos));
  const distinctIpas=[...new Set([h.ipa,...analyses.map(a=>a.ipa)].filter(Boolean))];
  const distinctGenders=[...new Set([h.gender,...analyses.map(a=>a.gender)].filter(Boolean))];
  const distinctStrata=[...new Set([e.stratum,...analyses.map(a=>a.stratum)].filter(s=>s && s!=='unspecified'))];
  const headerIpa=distinctIpas.length ? distinctIpas.join(' · ') : '音标暂缺 / IPA not recorded';
  const headerGender=distinctGenders.length ? distinctGenders.join(' / ') : (posSet.length ? posSet.join(' / ').toUpperCase() : '性别未标注');
  const headerStratum=distinctStrata.length ? distinctStrata.map(s=>strata[s]).join(' · ') : strata[e.stratum || 'unspecified'];
  const sources=h.source_presence.map(s => `<a href="${esc(state.manifest.sources[s]?.url || '#')}" target="_blank" rel="noreferrer">${esc(s)}</a>`).join(' / ');
  const senses=entry.senses.map(s => `<div class="sense">${s.zh_definition ? `<p class="zh">${esc(s.zh_definition)}</p>` : ''}<p>${esc(s.en_definition)}</p>${s.mt_definition ? `<p lang="mt">${esc(s.mt_definition)}</p>` : ''}<span class="source">${esc(s.pos || '')} · ${esc(s.source)} · ${s.definition_origin === 'authored_pedagogical' ? `教学编写 · ${esc(s.definition_origin)}` : '来源释义'} · ${esc(s.review_status || 'source_attested')}</span></div>`).join('');
  const collocations=entry.senses.flatMap(s => s.collocations || []);
  const collocationHtml=collocations.length ? collocations.map(c=>`<p lang="mt">${esc(c.mt)}</p><p>${esc(c.en)}</p><p class="zh">${esc(c.zh)}</p><span class="source">${esc(c.source_type)}</span>`).join('') : '<p class="muted">搭配待补充 / no collocations recorded</p>';
  const scenarios = entry.dual_scenarios ? ['formal','colloquial'].map(key => {
    const s=entry.dual_scenarios[key]; if (!s) return '';
    const turns=key === 'colloquial' && Array.isArray(s.messages) && s.messages.length ? s.messages.map(turn=>`<div class="dialogue-turn"><h4>${esc(turn.speaker)}</h4><p lang="mt">${esc(turn.mt_spoken)}</p><button class="pronunciation" data-speak="${esc(turn.mt_spoken)}">◖♪ 朗读对话</button><p lang="mt">标准表达：${esc(turn.mt_standard)}</p><p>${esc(turn.en)}</p><p class="zh">${esc(turn.zh)}</p></div>`).join('') : `<p lang="mt">${esc(s.mt)}</p><button class="pronunciation" data-speak="${esc(s.mt)}">◖♪ 朗读例句</button><p>${esc(s.en)}</p>${s.zh ? `<p class="zh">${esc(s.zh)}</p>`:''}`;
    return `<div class="scenario"><h3>${key === 'formal' ? '书面表达 / written context' : '日常对话 / conversation'}</h3>${turns}${s.grammar_note ? `<p class="zh">${esc(s.grammar_note)}</p>` : ''}<span class="source">${esc(s.source_type)} · 教学编写 · ${esc(s.review_status || 'source_attested')} · ${esc(entry.dual_scenarios.review_status)}</span></div>`;
  }).join('') : '<p class="muted">暂无已编写语境 / examples not yet enriched</p>';
  const morphFields = [
    ['构词类型', m.pattern_type !== 'unspecified' ? m.pattern_type : null],
    ['词根辅音', m.root_radicals],
    ...(isVerbOnly ? [['动词派生型', m.verb_form],['未完成体', m.imperfect],['过去分词', m.past_participle],['动名词', m.verbal_noun]] : [
      ...(m.verb_form ? [['动词派生型', m.verb_form]] : []),
      ...(m.imperfect ? [['未完成体', m.imperfect]] : []),
      ...(m.past_participle ? [['过去分词', m.past_participle]] : []),
      ...(m.verbal_noun ? [['动名词', m.verbal_noun]] : []),
      ['复数', m.plural_forms],
    ]),
    ['集合形式', m.collective_form],
    ['个体形式', m.singulative_form],
  ];
  const morphSummary = `${m.root_consonants ? `<button class="root-chip" data-root="${esc(m.root_consonants)}">#root:${esc(m.root_consonants)}</button>` : '<p class="muted">词根暂无实证 / no attested root</p>'}${compactDl(morphFields) || dl([['构词类型', m.pattern_type]])}<div class="family">${family(m.word_family)}</div>${m.root_evidence.length>1 ? `<div class="family">${m.root_evidence.slice(1).map(r=>`<button data-root="${esc(r.root)}">#root:${esc(r.root)}</button>`).join('')}</div>`:''}`;
  const inflectPairs = [
    ...(isVerbOnly || f.perfett_3sg_m || f.imperfett_3sg_m || f.imperattiv_2sg ? [
      ['Perfett 3sg.m', f.perfett_3sg_m],
      ['Imperfett 3sg.m', f.imperfett_3sg_m],
      ['Imperattiv 2sg', f.imperattiv_2sg],
    ] : []),
    ...(!isVerbOnly || f.plural?.length ? [['复数 / plural', f.plural]] : []),
    ...(f.definite_article?.form ? [['定冠词', f.definite_article.form]] : []),
  ];
  const allAttestedForms = f.attested_forms?.length ? f.attested_forms : analyses.flatMap(a => a.attested_forms || []);
  const allPronomi = f.pronomi_mehmuzin?.length ? f.pronomi_mehmuzin : analyses.flatMap(a => a.pronomi_mehmuzin || []);
  const inflectionHtml = `${compactDl(inflectPairs) || dl([['复数 / plural', f.plural],['定冠词', f.definite_article?.form]])}${f.definite_article ? `<p class="source">${esc(f.definite_article.note)} · grammar_reference</p>`:''}${formsTable(allAttestedForms)}${allPronomi.length ? `<h3>Pronomi Mehmużin · 附着代词</h3>${formsTable(allPronomi)}` : ''}`;
  const distinctEtymTexts = [...new Set([e.etymology_text_en, ...analyses.map(a => a.etymology_text)].filter(Boolean))];
  const etymologyHtml = `<p><strong>语源层级：</strong>${esc(headerStratum)}</p>${distinctEtymTexts.length ? distinctEtymTexts.map(t => `<p>${esc(t)}</p>`).join('') : `<p>${nullable(null)}</p>`}${sourceChain(e.source_chain)}<p class="source">Kaikki / Wiktionary 词源</p><p class="zh">学习助记：${esc(e.cognitive_memory_aid || '待补充 / not recorded')}</p>${e.cognitive_memory_aid_provenance ? `<p class="source">${esc(e.cognitive_memory_aid_provenance.source_type)} · ${esc(e.cognitive_memory_aid_provenance.review_status)}</p>` : ''}`;
  $('entry-card').innerHTML = `${trace ? `<div id="morph-trace-banner" role="status">词形还原 / morphological trace<br>${esc(traceText(trace))}</div>` : ''}
    <div class="entry-top"><div><h1 lang="mt">${esc(h.word)}</h1><p class="ipa">${esc(headerIpa)}</p></div><button id="pronounce-word" class="pronunciation">◖♪ ${h.audio_url ? '真人录音' : '发音 / 指南'}</button></div>
    <div class="entry-meta"><span class="chip">Tier ${h.tier}</span><span class="chip">${esc(headerGender)}</span><span class="chip">${esc(headerStratum)}</span></div>
    <div class="tools"><button id="copy-markdown">复制 Markdown</button><button id="copy-anki">复制 Anki TSV</button></div>
    ${section('01 · 词头与发音 / headword',`<p class="source">${sources} · 来源已收录（source_attested）</p>${h.audio_commons_url ? `<p><a href="${esc(h.audio_commons_url)}" target="_blank" rel="noreferrer">Wikimedia Commons · 作者与录音许可</a></p>` : ''}${compactDl([['音标来源',h.ipa_source],['集合 / 个体',h.collectivity],['录音说明',h.audio_note ? `${h.audio_note.note || ''} ${h.audio_note.file || ''} · 许可见 Commons 文件页` : null]])}`)}
    ${section('02 · 构词与词族 / morphology',multiple ? `${morphSummary}${renderAnalyses(analyses)}` : morphSummary)}
    ${section('03 · 三语释义 / senses',senses || '<p class="muted">释义暂无实证 / not recorded</p>')}
    ${section('04 · 实用搭配 / collocations',collocationHtml)}
    ${section('05 · 双境表达 / two contexts',scenarios)}
    ${section('06 · 屈折与附着代词 / inflection & clitics',inflectionHtml)}
    ${section('07 · 语用与同源词 / pragmatics & cognates',p && (p.register?.length || p.synonyms?.length || p.antonyms?.length || p.cognates_and_false_friends?.length) ? `${compactDl([['语域',p.register],['同义词',p.synonyms],['反义词',p.antonyms]])}${sourceChain(p.cognates_and_false_friends)}` : '<p class="muted">暂无已记录语用资料 / not recorded</p>')}
    ${section('08 · 历史词源 / etymology',etymologyHtml)}`;
  $('pronounce-word').onclick=() => pronunciation.play(h.word,h.audio_url);
  $('entry-card').querySelectorAll('[data-speak]').forEach(b => b.onclick=()=>pronunciation.play(b.dataset.speak));
  $('entry-card').querySelectorAll('[data-word]').forEach(b => b.onclick=()=>searchDirect(b.dataset.word));
  $('entry-card').querySelectorAll('[data-root]').forEach(b => b.onclick=()=>searchDirect(`#root:${b.dataset.root}`));
  $('copy-markdown').onclick=()=>copyExport(false);
  $('copy-anki').onclick=()=>copyExport(true);
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
  const lines=[`# ${h.word}`,`Sources: ${sources}`,`Review: ${review}`,`Audio attribution: ${h.audio_commons_url || 'not recorded'}`,`Lexeme analyses:\n${analyses}`,`01 · ${h.ipa || 'IPA not recorded'} · Tier ${h.tier} · ${h.source_presence.join(', ')}`,
    `02 · Root: ${m.root_consonants || 'not recorded'} · ${m.pattern_type}`, `Family: ${(m.word_family || []).join(', ')}`,
    '03 · Senses',...entry.senses.map(s=>`- ${s.en_definition}${s.zh_definition ? ' / '+s.zh_definition : ''} (${s.pos || 'teaching'}, ${s.source}, ${s.definition_origin}, ${s.review_status || h.editorial_status})`),
    '04 · Collocations',...entry.senses.flatMap(s=>(s.collocations || []).map(c=>`${c.mt} / ${c.en} / ${c.zh} (${c.source_type}, ${c.review_status || 'pending_linguistic_review'})`)),
    '05 · Contexts',...Object.values(entry.dual_scenarios || {}).filter(s=>s?.mt).map(s=>`${s.mt}\n${s.en} (${s.source_type}, ${s.review_status || entry.dual_scenarios.review_status})`),
    '06 · Inflection',`Perfect: ${f.perfett_3sg_m || 'not recorded'}; imperfect: ${f.imperfett_3sg_m || 'not recorded'}; imperative: ${f.imperattiv_2sg || 'not recorded'}; plural: ${(f.plural || []).join(', ')}`,
    '07 · Pragmatics',`Register: ${(p?.register || []).join(', ')}; synonyms: ${(p?.synonyms || []).join(', ')}; antonyms: ${(p?.antonyms || []).join(', ')}`,
    '08 · Etymology',e.etymology_text_en || 'not recorded',`Discovery stratum: ${e.stratum}`,`Learner mnemonic: ${e.cognitive_memory_aid || 'not recorded'} (${e.cognitive_memory_aid_provenance?.source_type || 'not recorded'})`];
  return lines.join('\n\n');
}
async function copyExport(anki) {
  if (!state.current) return;
  try { await navigator.clipboard.writeText(exportText(state.current,anki)); toast(anki ? '已复制 Anki TSV（9 列）' : '已复制 Markdown'); }
  catch { toast('浏览器未允许剪贴板访问。请在本机 localhost 页面重试。'); }
}
function preferences() {
  try {
    const saved=JSON.parse(localStorage.getItem('open-malti-preferences') || '{}');
    if (['white','sepia','grey','night'].includes(saved.theme)) $('theme').value=saved.theme;
    state.scale=Math.max(.85,Math.min(1.3,Number(saved.scale) || 1)); state.english=!!saved.english;
  } catch { /* memory-only preferences */ }
  function apply() {
    document.body.dataset.theme=$('theme').value; document.documentElement.style.setProperty('--scale',state.scale);
    document.body.classList.toggle('english-mode',state.english);
    $('language-mode').textContent=state.english ? 'English–Maltese' : '马–中–英';
    $('language-mode').setAttribute('aria-pressed',String(state.english));
    try { localStorage.setItem('open-malti-preferences',JSON.stringify({theme:$('theme').value,scale:state.scale,english:state.english})); } catch { /* private mode */ }
  }
  $('theme').onchange=apply;
  $('font-down').onclick=()=>{state.scale=Math.max(.85,state.scale-.05);apply();};
  $('font-up').onclick=()=>{state.scale=Math.min(1.3,state.scale+.05);apply();};
  $('language-mode').onclick=()=>{state.english=!state.english;apply();renderList();}; apply();
}
async function start() {
  preferences();
  $('close-pronunciation').onclick=()=>$('pronunciation-guide-popover').close();
  $('search').addEventListener('input',()=>{state.selection++; state.request++; clearTimeout(debounce); debounce=setTimeout(()=>requestSearch(),100);});
  $('previous-page').onclick=()=>{state.offset-=60;requestSearch(false);};
  $('next-page').onclick=()=>{state.offset+=60;requestSearch(false);};
  document.addEventListener('keydown',event=>{
    const typing=event.target.matches('input,textarea,select') || event.target.isContentEditable;
    if (event.key === '/' && !typing) {event.preventDefault();$('search').focus();}
    if (event.key === 'Escape') {$('pronunciation-guide-popover').close();$('search').blur();}
    if (['ArrowDown','ArrowUp'].includes(event.key) && !event.altKey && !event.ctrlKey && !$('pronunciation-guide-popover').open && (!typing || event.target === $('search'))) {
      event.preventDefault(); const next=state.selected+(event.key === 'ArrowDown' ? 1 : -1);
      if (next>=0 && next<state.results.length) selectEntry(next);
      else if (event.key === 'ArrowDown' && state.offset+60<state.total) {state.offset+=60;requestSearch(false);}
      else if (event.key === 'ArrowUp' && state.offset>0) {state.offset-=60;requestSearch(false);}
    }
  });
  try {
    state.manifest=await loadManifest(); navigation();
    $('inventory-note').textContent=`${state.manifest.total_lemmas.toLocaleString()} 个词头 · ${state.manifest.wordform_surface_count.toLocaleString()} 个反查表面形 · Ġabra MDX CC BY 3.0 / Wiktionary CC BY-SA 4.0`;
    worker=new Worker('./worker.js',{type:'module'});
    worker.onerror=()=>{$('result-count').textContent='检索器加载失败，请刷新页面。';};
    worker.onmessage=({data})=>{
      if (data.type === 'ready') {$('search').disabled=false;$('wordforms-status').textContent='基础检索已就绪 · 反查表后台载入中…';requestSearch();}
      if (data.type === 'wordforms-ready') $('wordforms-status').textContent='词头与词形反查均已就绪';
      if (data.type === 'wordforms-error') $('wordforms-status').textContent='基础检索可用 · 反查表暂不可用：'+data.message;
      if (currentWorkerError(data,state.request)) {toast(data.message);$('result-count').textContent=data.message;}
      if (data.type !== 'results' || data.requestId !== state.request) return;
      state.results=data.results; state.total=data.total; state.offset=data.offset; state.selected=-1;
      $('search-time').textContent=`${data.elapsed.toFixed(1)} ms`; renderList();
      if (state.results.length) selectEntry(0);
      else {state.current=null; pronunciation.stop();$('entry-card').removeAttribute('aria-busy');$('entry-card').innerHTML='<p class="empty">请尝试其他词形，或清除字母、层级与语源筛选。</p>';}
    };
    worker.postMessage({type:'init',manifest:state.manifest});
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(()=>{});
  } catch(error) { $('result-count').textContent=error.message; $('entry-card').textContent=error.message; }
}
if (typeof document !== 'undefined') start();
