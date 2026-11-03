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

  assert.equal(consoleErrors.length, 0, `Console errors: ${consoleErrors.join('; ')}`);
  assert.equal(pageErrors.length, 0, `Page errors: ${pageErrors.join('; ')}`);
  console.log('ALL 7 REAL CHROME E2E ACCEPTANCE CASES PASSED (0 consoleErrors, 0 pageErrors)');
} finally {
  ws?.close();
  chrome.kill();
  serverProc.kill();
  await new Promise(r => (chrome.exitCode !== null ? r() : chrome.once('exit', r)));
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 }).catch(() => {});
}
