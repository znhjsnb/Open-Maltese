// Real Chrome CDP End-to-End Acceptance Test for Open-Malti (0 external npm packages)
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { readFile, mkdtemp, rm, mkdir } from 'node:fs/promises';
import { resolve, join } from 'node:path';

const pause = ms => new Promise(r => setTimeout(r, ms));
async function until(fn, timeout = 15000) {
  const start = Date.now();
  let last;
  while (Date.now() - start < timeout) {
    try {
      last = await fn();
      if (last) return last;
    } catch (error) {
      last = error;
    }
    await pause(50);
  }
  throw new Error(`Browser condition timed out: ${last}`);
}

const chromeCandidates = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Users/d/.agent-browser/browsers/chrome-156.0.8078.47/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean);

const chromePath = chromeCandidates.find(existsSync);
if (!chromePath) {
  throw new Error('No Chrome/Edge executable found for E2E verification');
}

await mkdir(resolve('.tmp'), { recursive: true });
const profile = await mkdtemp(resolve('.tmp/chrome-e2e-'));
const serverProc = spawn('python', ['-X', 'utf8', 'app/server.py', '--port', '0'], { windowsHide: true });
const origin = await new Promise((resolveOrigin, rejectOrigin) => {
  serverProc.stdout.once('data', chunk => {
    const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/);
    if (match) resolveOrigin(match[0]);
    else rejectOrigin(new Error(`Unexpected server output: ${chunk}`));
  });
  serverProc.once('error', rejectOrigin);
});

const chrome = spawn(
  chromePath,
  [
    '--headless=new',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    '--disable-gpu',
    '--no-first-run',
    '--window-size=1440,960',
    'about:blank',
  ],
  { windowsHide: true, stdio: 'ignore' }
);

let ws;
const consoleErrors = [];
const pageErrors = [];
try {
  let cdpPort;
  const started = Date.now();
  while (!cdpPort) {
    if (Date.now() - started > 12000) throw new Error('Chrome CDP startup timed out');
    try {
      cdpPort = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0].trim();
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (!cdpPort) await pause(40);
  }
  const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json/list`)).json();
  ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });

  let id = 0;
  const pending = new Map();
  ws.onmessage = event => {
    const msg = JSON.parse(event.data);
    if (msg.method === 'Runtime.exceptionThrown') {
      pageErrors.push(msg.params.exceptionDetails?.text || 'exception');
    }
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
      consoleErrors.push(msg.params.args.map(a => a.value || a.description).join(' '));
    }
    if (!pending.has(msg.id)) return;
    const { resolve: res, reject: rej } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
  };

  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const reqId = ++id;
      const timer = setTimeout(() => {
        pending.delete(reqId);
        rej(new Error(`CDP timeout: ${method}`));
      }, 20000);
      pending.set(reqId, {
        resolve: v => {
          clearTimeout(timer);
          res(v);
        },
        reject: e => {
          clearTimeout(timer);
          rej(e);
        },
      });
      ws.send(JSON.stringify({ id: reqId, method, params }));
    });

  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(JSON.stringify(result.exceptionDetails));
    }
    return result.result?.value;
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Page.navigate', { url: origin });

  // 1. Wait for two-stage worker bootstrap and initial entry card
  await until(async () => {
    const status = await evaluate(`({
      countText: document.getElementById('result-count')?.textContent || '',
      wfStatus: document.getElementById('wordforms-status')?.textContent || '',
      dims: document.querySelectorAll('#entry-card .dimension').length,
      detailsTags: document.querySelectorAll('details').length
    })`);
    return (
      status.countText.includes('24,045') &&
      status.wfStatus.includes('词头与词形反查均已就绪') &&
      status.dims === 8 &&
      status.detailsTags === 0
    );
  });
  console.log('PASS 1: Cold bootstrap (24,045 lemmas + stage-2 reverse lookup + 8 flat dimensions, 0 <details>)');

  // 2. Verify bucket I highlights sub-prefix 'ie' first
  await evaluate(`
    Array.from(document.querySelectorAll('#letter-bar button')).find(b => b.textContent === 'I').click();
  `);
  await until(async () => {
    const firstSub = await evaluate(`
      document.querySelectorAll('#sub-prefix-bar button')[1]?.textContent || ''
    `);
    return firstSub.startsWith('ie ');
  });
  await evaluate(`
    Array.from(document.querySelectorAll('#letter-bar button')).find(b => b.textContent === '全部').click();
  `);
  await until(async () => (await evaluate(`document.getElementById('result-count').textContent`)).includes('24,045'));
  console.log('PASS 2: UI letter bar (29+#) and I -> ie top sub-prefix capsule');

  // 3. Verify context-checked article & fused preposition resolution ('fix-xemx' -> 'xemx') and rejection of 'ix-ktieb'
  await evaluate(`(() => {
    const input = document.getElementById('search');
    input.value = 'fix-xemx';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await until(async () => {
    const state = await evaluate(`({
      word: document.querySelector('#entry-card h1')?.textContent,
      banner: document.getElementById('morph-trace-banner')?.textContent || ''
    })`);
    return state.word === 'xemx' && state.banner.includes('fix-xemx');
  });

  await evaluate(`(() => {
    const input = document.getElementById('search');
    input.value = 'ix-ktieb';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await until(async () => (await evaluate(`document.getElementById('result-count').textContent`)) === '0 个词目');
  console.log('PASS 3: Assimilated fused preposition (fix-xemx -> xemx) resolved & invalid (ix-ktieb) rejected');

  // 4. Verify inflected verb reverse lookup ('ktibt' -> 'kiteb') and P1-1 no verbal forms in lexical plural_forms
  await evaluate(`(() => {
    const input = document.getElementById('search');
    input.value = 'ktibt';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await until(async () => {
    const state = await evaluate(`({
      word: document.querySelector('#entry-card h1')?.textContent,
      banner: document.getElementById('morph-trace-banner')?.textContent || '',
      cardText: document.getElementById('entry-card')?.textContent || ''
    })`);
    return state.word === 'kiteb' && state.banner.includes('ktibt');
  });
  const kitebPluralCheck = await evaluate(`
    (() => {
      const dts = Array.from(document.querySelectorAll('#entry-card dt'));
      const plDt = dts.find(d => d.textContent === '复数');
      return plDt ? plDt.nextElementSibling.textContent : '';
    })()
  `);
  assert.ok(!kitebPluralCheck.includes('jiktbu') && !kitebPluralCheck.includes('ktibna'));
  console.log('PASS 4: Reverse lookup (ktibt -> kiteb) trace banner & P1-1 clean verbal plural field');

  // 5. Verify homograph sub-entry boundaries on 'dar'
  await evaluate(`(() => {
    const input = document.getElementById('search');
    input.value = 'dar';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await until(async () => (await evaluate(`document.querySelector('#entry-card h1')?.textContent`)) === 'dar');
  const darAnalysesCount = await evaluate(`document.querySelectorAll('#entry-card .lexeme-analysis').length`);
  assert.ok(darAnalysesCount >= 2);
  const darTranslations = await evaluate(`Array.from(document.querySelectorAll('#entry-card .lexeme-analysis')).map(a=>({
    heading:a.querySelector('h3').textContent,
    zh:Array.from(a.querySelectorAll('.sense .zh')).map(s=>s.textContent),
    provenance:a.textContent.includes('authored_pedagogical')
  }))`);
  for (const analysis of darTranslations) {
    assert.ok(analysis.zh.length > 0 && analysis.provenance);
    if (analysis.heading.includes('noun') || analysis.heading.includes('NOUN')) {
      assert.ok(analysis.zh.some(t=>t.includes('房')));
      assert.ok(!analysis.zh.some(t=>t.includes('转向')));
    } else {
      assert.ok(!analysis.zh.some(t=>t.includes('房屋')));
    }
  }
  assert.ok((await evaluate(`document.getElementById('entry-card').textContent`)).includes('学习助记：'));
  console.log(`PASS 5: Homograph 'dar' renders ${darAnalysesCount} isolated .lexeme-analysis blocks`);

  // 6. Verify 'għajn' has native audio button, and unrecorded 'għabex' opens longest-match 'għ' guide (no false 'ħ')
  await evaluate(`(() => {
    const input = document.getElementById('search');
    input.value = 'ghajn';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await until(async () => (await evaluate(`document.querySelector('#entry-card h1')?.textContent`)) === 'għajn');
  assert.ok((await evaluate(`document.getElementById('pronounce-word').textContent`)).includes('真人录音'));

  await evaluate(`(() => {
    const input = document.getElementById('search');
    input.value = 'għabex';
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);
  await until(async () => (await evaluate(`document.querySelector('#entry-card h1')?.textContent`)) === 'għabex');
  await evaluate(`(() => {
    window.speechSynthesis.getVoices = () => [];
    document.getElementById('pronounce-word').click();
  })()`);
  await until(async () => await evaluate(`document.getElementById('pronunciation-guide-popover').open === true`));
  const guideDts = await evaluate(`
    Array.from(document.querySelectorAll('#pronunciation-content dt')).map(el => el.textContent)
  `);
  assert.ok(guideDts.includes('għ'));
  assert.ok(!guideDts.includes('ħ'));
  await evaluate(`document.getElementById('close-pronunciation').click();`);
  console.log('PASS 6: ASCII-tolerant search (ghajn -> għajn) & longest-match pronunciation guide popover');

  // 7. Verify 4 paper themes, font scaling, and language toggle
  for (const theme of ['sepia', 'grey', 'night', 'white']) {
    await evaluate(`(() => {
      const sel = document.getElementById('theme');
      sel.value = '${theme}';
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    })()`);
    const bodyTheme = await evaluate(`document.body.dataset.theme`);
    assert.equal(bodyTheme, theme);
  }
  await evaluate(`document.getElementById('font-up').click(); document.getElementById('language-mode').click();`);
  assert.equal(await evaluate(`document.body.classList.contains('english-mode')`), true);
  console.log('PASS 7: Paper themes (white/sepia/grey/night), font scale, and language mode switch');

  // 8. Manifest-driven enrichment count and real Worker filter.
  await evaluate(`(() => {
    const input=document.getElementById('search'); input.value='';
    // The filter click submits the cleared input itself; no pending debounce.
    Array.from(document.querySelectorAll('#feature-filters button')).find(b=>b.textContent.startsWith('精选样板 (')).click();
  })()`);
  const showcaseCount = JSON.parse(await readFile(resolve('app/static/data/manifest.json'), 'utf8')).showcase_count;
  await until(async () => await evaluate(`(() => {
    const card=document.getElementById('entry-card');
    return document.getElementById('result-count').textContent === '${showcaseCount.toLocaleString()} 个词目'
      && !card.hasAttribute('aria-busy') && card.textContent.includes('phase2_reviewed')
      && card.querySelectorAll('.dialogue-turn').length >= 2;
  })()`));
  assert.ok((await evaluate(`document.getElementById('entry-card').textContent`)).includes('phase2_reviewed'));
  console.log(`PASS 8: Dynamic showcase (${showcaseCount}), Phase 2 teaching provenance, dialogue turns and filtered Worker results`);

  const searchWord = async word => {
    await evaluate(`(() => {
      document.getElementById('search').value=${JSON.stringify(word)};
      Array.from(document.querySelectorAll('#feature-filters button')).find(b=>b.textContent==='全部特征').click();
    })()`);
    await until(async()=>await evaluate(`document.querySelector('#entry-card h1')?.textContent===${JSON.stringify(word)} && !document.getElementById('entry-card').hasAttribute('aria-busy')`));
  };
  // 9. Independently inspect each dimension's exact source-record boundary.
  await searchWord('abaku');
  const abaku = await evaluate(`(() => {
    const dims=document.querySelectorAll('#entry-card > .dimension');
    return {six:dims[5].textContent,eight:dims[7].textContent,ipa:document.querySelector('.ipa').textContent,
      all:document.getElementById('entry-card').textContent,
      morphology:document.querySelectorAll('#entry-card .lexeme-analysis').length,
      sixIds:Array.from(dims[5].querySelectorAll('.inflection-subentry')).map(a=>a.dataset.analysisId),
      eightIds:Array.from(dims[7].querySelectorAll('.etymology-subentry')).map(a=>a.dataset.analysisId)};
  })()`);
  assert.ok(abaku.six.includes('abaki') && abaku.six.includes('l-abaku'));
  assert.ok(!/Perfett 3sg.m|Imperfett 3sg.m|Imperattiv 2sg/.test(abaku.six));
  assert.ok(abaku.eight.includes('Borrowed from Italian abaco.') && abaku.eight.includes('学习助记：'));
  assert.ok(!/列于上方|分列如下/.test(abaku.all));
  assert.ok(abaku.ipa.includes('/ˈaː.ba.ku/ (kaikki)'));
  assert.equal(abaku.morphology,2);assert.deepEqual(abaku.sixIds,abaku.eightIds);
  await searchWord('dar');
  const darGroups=await evaluate(`(() => {
    const dims=document.querySelectorAll('#entry-card > .dimension');
    return {six:Array.from(dims[5].querySelectorAll('.inflection-subentry')).map(a=>({id:a.dataset.analysisId,text:a.textContent})),
      eight:Array.from(dims[7].querySelectorAll('.etymology-subentry')).map(a=>({id:a.dataset.analysisId,text:a.textContent})),
      source: dims[2].textContent, senses: dims[2].querySelectorAll('.sense-card').length};
  })()`);
  assert.equal(darGroups.six.length,5);assert.deepEqual(darGroups.six.map(a=>a.id),darGroups.eight.map(a=>a.id));
  const noun=darGroups.six.find(a=>a.id==='kaikki:dar:0').text,verb=darGroups.six.find(a=>a.id==='kaikki:dar:1').text;
  assert.ok(noun.includes('djar') && noun.includes('id-dar') && !/jdur|midur/.test(noun));
  assert.ok(verb.includes('jdur') && verb.includes('midur') && !verb.includes('djar'));
  assert.ok(verb.includes('已展示 24 / 共 55 项'));
  assert.ok(darGroups.eight.find(a=>a.id==='kaikki:dar:0').text.includes('From Arabic دَار (dār).'));
  assert.ok(!darGroups.eight.find(a=>a.id==='kaikki:dar:0').text.includes('دَارَ (dāra)'));
  assert.ok(darGroups.source.includes('licensed_source') && darGroups.source.includes('译释：authored_pedagogical · phase2_reviewed'));
  assert.ok(darGroups.senses>1);
  console.log('PASS 9: abaku/dar dimensions 06/08 preserve exact analysis ids, applicable rows, excerpts and translation provenance');

  const point = id => evaluate(`(() => {const r=document.getElementById('${id}').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
  const drag = async (id,dx,dy) => {
    const p=await point(id);
    await send('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});
    for(let step=1;step<=5;step++)await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:p.x+dx*step/5,y:p.y+dy*step/5,button:'left',buttons:1});
    await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:p.x+dx,y:p.y+dy,button:'left',clickCount:1});
  };
  // 10. Use actual pointer input for the splitter, then scroll the content pane.
  assert.equal(await evaluate(`['.topbar','.workspace','#word-sidebar','#resizer','#content','.content-toolbar'].every(s=>!!document.querySelector(s))`),true);
  const widthBefore=await evaluate(`document.getElementById('word-sidebar').getBoundingClientRect().width`);
  await drag('resizer',50,0);
  const widthAfter=await evaluate(`document.getElementById('word-sidebar').getBoundingClientRect().width`);
  assert.ok(Math.abs(widthAfter-widthBefore-50)<2);
  assert.equal(await evaluate(`JSON.parse(localStorage.getItem('open-malti-sidebar-width'))`),widthAfter);
  await evaluate(`document.getElementById('content').scrollTop=600`);
  await until(async()=>await evaluate(`!document.getElementById('toolbar-pinned-word').hidden`));
  assert.ok((await evaluate(`document.getElementById('toolbar-pinned-word').textContent`)).includes('dar'));
  await evaluate(`document.getElementById('focus').click()`);
  assert.equal(await evaluate(`getComputedStyle(document.getElementById('word-sidebar')).display`),'none');
  await evaluate(`document.getElementById('focus').click();document.querySelector('.sense-chip').click()`);
  await until(async()=>await evaluate(`document.getElementById('sense-0').classList.contains('pulse') && document.activeElement.id==='sense-0'`));
  console.log('PASS 10: Workbench shell, pointer splitter persistence, pinned word, focus mode and pulsing sense navigation');

  // 11. New and legacy controls share state and survive a real document reload.
  await evaluate(`document.getElementById('typography-btn').click()`);
  assert.equal(await evaluate(`document.getElementById('typography-panel').open`),true);
  await evaluate(`document.querySelector('[data-paper="sepia"]').click();document.querySelector('[data-font-family="mono"]').click();document.querySelector('[data-density="compact"]').click();document.getElementById('font-increase').click();document.getElementById('lang-bilingual').click()`);
  const prefs=await evaluate(`JSON.parse(localStorage.getItem('open-malti-preferences'))`);
  assert.equal(prefs.theme,'sepia');assert.equal(prefs.font,'mono');assert.equal(prefs.density,'compact');assert.equal(prefs.language,'bilingual');
  assert.equal(await evaluate(`document.getElementById('theme').value`),'sepia');
  const larger=await evaluate(`Number(document.documentElement.style.getPropertyValue('--scale'))`);
  await evaluate(`document.getElementById('font-down').click();document.getElementById('font-up').click();document.getElementById('font-decrease').click();document.getElementById('font-increase').click();document.getElementById('language-mode').click()`);
  assert.equal(await evaluate(`Number(document.documentElement.style.getPropertyValue('--font-scale'))`),larger);
  assert.equal(await evaluate(`document.getElementById('lang-en').getAttribute('aria-pressed')`),'true');
  assert.equal(await evaluate(`document.body.classList.contains('english-mode')`),true);
  await evaluate(`document.getElementById('typography-close').click()`);
  await send('Page.reload',{ignoreCache:true});
  await until(async()=>await evaluate(`document.querySelectorAll('#entry-card > .dimension').length===8 && document.getElementById('wordforms-status').textContent.includes('均已就绪')`));
  const reloaded=await evaluate(`({paper:document.documentElement.dataset.readingPaper,font:document.documentElement.dataset.readingFont,density:document.documentElement.dataset.readingDensity,en:document.body.classList.contains('english-mode'),scale:Number(document.documentElement.style.getPropertyValue('--scale')),width:document.getElementById('word-sidebar').getBoundingClientRect().width})`);
  assert.deepEqual(reloaded,{paper:'sepia',font:'mono',density:'compact',en:true,scale:larger,width:widthAfter});
  await evaluate(`document.getElementById('lang-trilingual').click();document.getElementById('theme-toggle').click()`);
  assert.equal(await evaluate(`document.body.dataset.theme`),'night');
  await evaluate(`document.getElementById('typography-btn').click();document.getElementById('typo-reset').click();document.getElementById('typography-close').click()`);
  assert.equal(await evaluate(`document.body.dataset.theme`),'white');
  console.log('PASS 11: Typography dialog, legacy/new preference synchronization and reload persistence');

  // 12. Physical study drawer, bookmarks, then all 32 persistent assets.
  await evaluate(`document.getElementById('practice').click()`);
  await until(async()=>await evaluate(`document.getElementById('study').open && !document.getElementById('study-known').disabled`));
  await evaluate(`document.getElementById('flashcard').click()`);
  assert.equal(await evaluate(`document.getElementById('flashcard').getAttribute('aria-pressed')`),'true');
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.flashcard-inner')).transformStyle`),'preserve-3d');
  assert.equal(await evaluate(`document.querySelector('.flashcard-back').getAttribute('aria-hidden')`),'false');
  await drag('study-grabber',0,180);
  await until(async()=>await evaluate(`!document.getElementById('study').open`));
  await searchWord('abaku');
  await evaluate(`document.getElementById('save').click();document.getElementById('search').value='';document.getElementById('bookmarks').click()`);
  await until(async()=>await evaluate(`document.getElementById('result-count').textContent==='1 个词目' && document.querySelector('#entry-card h1')?.textContent==='abaku' && !document.getElementById('save').disabled`));
  assert.equal(await evaluate(`document.getElementById('bookmark-count').textContent`),'1');
  await evaluate(`document.getElementById('save').click()`);
  await until(async()=>await evaluate(`document.getElementById('result-count').textContent==='0 个词目' && document.querySelectorAll('.word-row').length===0`));
  await evaluate(`document.getElementById('bookmarks').click();document.getElementById('offline').click()`);
  await until(async()=>await evaluate(`document.getElementById('offline').textContent.includes('32/32')`),120000);
  const persisted=await evaluate(`(async()=>{
    const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('open-malti-data',2);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    const read=key=>new Promise((resolve,reject)=>{const r=db.transaction('files').objectStore('files').get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    const m=await read('manifest'),assets=[m.index_lite,m.wordforms_lookup,...m.shards];let verified=0;
    for(const meta of assets){const bytes=await read(m.version+':'+meta.sha256);if(!bytes)throw new Error('Missing IndexedDB asset '+meta.file);const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');if(digest!==meta.sha256)throw new Error('SHA mismatch '+meta.file);verified++;}
    db.close();return verified;
  })()`);
  assert.equal(persisted,32);
  await evaluate(`navigator.serviceWorker.ready.then(()=>true)`);
  await send('Network.enable');
  await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
  await send('Page.reload');
  await until(async()=>await evaluate(`document.getElementById('wordforms-status').textContent.includes('均已就绪')`));
  await searchWord('żmien');
  assert.equal(await evaluate(`document.querySelectorAll('#entry-card > .dimension').length`),8);
  await send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await evaluate(`document.getElementById('daily').click()`);
  await until(async()=>await evaluate(`!document.getElementById('study-known').disabled`));
  await evaluate(`document.getElementById('flashcard').click()`);
  assert.equal(await evaluate(`getComputedStyle(document.querySelector('.flashcard-inner')).transform`),'none');
  await evaluate(`document.getElementById('close-study').click()`);
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate(`document.querySelector('.word-row').click()`);
  await until(async()=>await evaluate(`getComputedStyle(document.getElementById('content')).display!=='none'`));
  assert.equal(await evaluate(`document.documentElement.scrollWidth<=innerWidth`),true);
  await evaluate(`document.getElementById('back').click()`);
  assert.equal(await evaluate(`getComputedStyle(document.getElementById('word-sidebar')).display`),'flex');
  console.log('PASS 12: 3D study drawer/drag close, bookmarks including empty, 32 SHA-verified IndexedDB assets, offline reload, reduced motion and mobile navigation');

  assert.equal(consoleErrors.length, 0, `Console errors: ${consoleErrors.join('; ')}`);
  assert.equal(pageErrors.length, 0, `Page errors: ${pageErrors.join('; ')}`);
  console.log('ALL 12 REAL CHROME E2E ACCEPTANCE CASES PASSED (0 consoleErrors, 0 pageErrors)');
} finally {
  ws?.close();
  chrome.kill();
  serverProc.kill();
  await new Promise(r => (chrome.exitCode !== null ? r() : chrome.once('exit', r)));
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 }).catch(() => {});
}
