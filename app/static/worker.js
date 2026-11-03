/* Search is pure client-side; retain the builder's deterministic DMS order. */
import {loadDataset} from './db.js';
export function exact(text) {
  return String(text).normalize('NFC').replace(/[‘’‛ʼ＇′`´]/g,"'")
    .replace(/[‐‑‒–—−]/g,'-').trim().replace(/\s+/g,' ').toLowerCase();
}
export function ascii(text) {
  const vowels={a:'àáâäãāăå',e:'èéêëēĕ',i:'ìíîïīĭ',o:'òóôöõōŏ',u:'ùúûüūŭ'};
  let folded=exact(text);
  for (const [base,accented] of Object.entries(vowels)) folded=folded.replace(new RegExp(`[${accented}]`,'g'),base);
  return folded.replace(/[ċġħż]/g,c=>({ċ:'c',ġ:'g',ħ:'h',ż:'z'}[c])).replace(/[^\p{L}\p{N}]/gu,'');
}

export function stripArticle(text, known) {
  const q=exact(text), suns='ċdnrstxżz';
  const sunPrefixes=new Map(['i','','fi','bi','ma','ta','għa','li'].flatMap(base=>[...suns].map(c=>[base+c+'-',c])));
  const moons=['il-','fil-','bil-','mal-','tal-','għall-','lil-','lill-'];
  const elided=['l-','fl-'];
  for (const prefix of [...sunPrefixes.keys(),...moons,...elided].sort((a,b)=>b.length-a.length)) {
    if (!q.startsWith(prefix) || q.length<=prefix.length) continue;
    const stem=q.slice(prefix.length);
    if (sunPrefixes.has(prefix) && !stem.startsWith(sunPrefixes.get(prefix))) continue;
    if (moons.includes(prefix) && suns.includes(stem[0])) continue;
    if (known?.has(stem)) return [stem,prefix];
    if (['l-','fl-','bil-','mal-','tal-','għall-'].includes(prefix)
        && /^i[sxżz](?![aeiou]|għ|h)\p{L}/u.test(stem) && stem.slice(1)!=='żmien'
        && known?.has(stem.slice(1))) return [stem.slice(1),prefix+'i'];
    return [stem,prefix];
  }
  return [q,null];
}

export function makeSearchEngine(entries, compact={tags:[],forms:{}}) {
  const lookup=compact.forms || compact;
  const links=key=>Array.isArray(lookup[key]) ? lookup[key].map(link=>Array.isArray(link) ? {lemma:link[0],tag:compact.tags[link[1]]} : link) : [];
  const byId = new Map(entries.map(e => [e.id, e]));
  const reverseAscii = new Map();
  for (const key of Object.keys(lookup)) {
    const folded = ascii(key);
    if (!reverseAscii.has(folded)) reverseAscii.set(folded, []);
    reverseAscii.get(folded).push(key);
  }
  function resolve(query) {
    const q = exact(query), found = new Map();
    function add(key, prefix = '') {
      if (prefix && byId.has(key)) {
        found.set(key, [prefix]);
      }
      for (const link of links(key)) {
        if (!byId.has(link.lemma)) continue;
        const tags = found.get(link.lemma) || [];
        tags.push(prefix + link.tag);
        found.set(link.lemma, [...new Set(tags)]);
      }
    }
    add(q);
    const [stem,prefix]=stripArticle(q,byId);
    if (prefix) add(stem, `grammar_rule: 剥离 ${prefix} / article or fused preposition; `);
    const proclitic = q.match(/^[mxbftl]'/)?.[0];
    if (proclitic) add(q.slice(proclitic.length), `剥离 ${proclitic} / proclitic; `);
    // Exact glyph evidence wins; tolerant candidates only supplement a miss.
    if (!found.size && !byId.has(q)) {
      for (const key of reverseAscii.get(ascii(q)) || []) add(key, 'ASCII 容错 / tolerant match; ');
    }
    return found;
  }
  function search(message) {
    const start = performance.now();
    const q = exact(message.query || '').slice(0, 200), folded = ascii(q);
    const root = q.startsWith('#root:') ? q.slice(6).trim() : null;
    const traces = q && !root ? resolve(q) : new Map();
    const ranked = [[], [], [], [], [], [], []];
    for (const e of entries) {
      if (message.bucket && e.bucket !== message.bucket) continue;
      if (message.prefix && e.sub_prefix !== message.prefix) continue;
      if (message.tier === 'core' && e.tier !== 1) continue;
      if (message.tier === 'rich' && e.tier > 2) continue;
      if (message.feature === 'showcase' && !e.is_showcase) continue;
      if (message.feature === 'root' && !(e.roots || []).length) continue;
      if (message.feature === 'audio' && !e.has_audio) continue;
      if (message.feature === 'loans' && !(e.strata || [e.stratum]).some(s=>['romance_sicilian_italian','english'].includes(s))) continue;
      if (message.stratum && e.stratum !== message.stratum) continue;
      let rank = -1;
      if (root) { if ((e.roots || [e.root]).includes(root)) rank = 0; }
      else if (!q || e.exact_key === q) rank = 0;
      else if (traces.has(e.id)) rank = 1;
      else if (folded && e.ascii_key === folded) rank = 2;
      else if (e.exact_key.startsWith(q)) rank = 3;
      else if (folded && e.ascii_key.startsWith(folded)) rank = 4;
      else if (e.exact_key.includes(q) || (folded && e.ascii_key.includes(folded))) rank = 5;
      else if ([...(e.gloss_en || []), e.gloss_zh || ''].join(' ').toLowerCase().includes(q)) rank = 6;
      if (rank >= 0) ranked[rank].push(e);
    }
    const all = ranked.flat(), pageSize = 60;
    const offset = Math.min(Math.max(0, Math.floor((message.offset || 0) / pageSize) * pageSize),
      Math.max(0, Math.floor((all.length - 1) / pageSize) * pageSize));
    return {type:'results', requestId:message.requestId, total:all.length, offset, pageSize,
      results:all.slice(offset, offset + pageSize).map(e => ({...e,
        trace:e.exact_key !== q && traces.has(e.id) ? {surface:q, lemma:e.word, tags:traces.get(e.id)} : null})),
      elapsed:performance.now() - start};
  }
  return {search, resolve};
}

export function createWorkerHandler(post, load=loadDataset) {
  let engine, loading, generation=0, latestSearch;
  return async ({data}) => {
    try {
      if (data.type === 'init') {
        const ticket=++generation, manifest=data.manifest;
        engine=null; latestSearch=null;
        loading = load(manifest.index_lite,manifest.version).then(entries => {
          if (ticket!==generation) return;
          engine=makeSearchEngine(entries);
          post({type:'ready',stage:'basic',count:entries.length,version:manifest.version});
          // Stage 2 never participates in the basic-search loading promise.
          load(manifest.wordforms_lookup,manifest.version).then(lookup => {
            if (ticket!==generation) return;
            if (lookup.version!==manifest.version) throw new Error('反查表版本不匹配，请刷新。');
            engine=makeSearchEngine(entries,lookup);
            post({type:'wordforms-ready',version:manifest.version});
            if (latestSearch) post(engine.search(latestSearch));
          }).catch(error=>{if (ticket===generation) post({type:'wordforms-error',message:error.message});});
        });
        await loading;
      } else {
        const ticket=generation;
        await loading;
        if (engine && ticket===generation) {latestSearch=data;post(engine.search(data));}
      }
    } catch (error) { post({type:'error', requestId:data.requestId, message:error.message}); }
  };
}
if (typeof WorkerGlobalScope !== 'undefined' && globalThis instanceof WorkerGlobalScope) {
  self.onmessage=createWorkerHandler(message=>self.postMessage(message));
}
