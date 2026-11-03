/* All generated assets are bound to manifest version + SHA-256. */
const memory = new Map(), inflight = new Map();
let database;
function openDatabase() {
  if (!globalThis.indexedDB) return Promise.resolve(null);
  if (!database) database = new Promise((resolve,reject) => {
    const request = indexedDB.open('open-malti-data',1);
    request.onupgradeneeded = () => request.result.createObjectStore('assets');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => resolve(null);
  }).catch(() => null);
  return database;
}
async function persisted(key, value) {
  const db = await openDatabase();
  if (!db) return undefined;
  return new Promise(resolve => {
    const tx = db.transaction('assets',value === undefined ? 'readonly' : 'readwrite');
    const store = tx.objectStore('assets');
    const request = value === undefined ? store.get(key) : store.put(value,key);
    let result;
    request.onsuccess = () => {result=request.result;};
    tx.oncomplete = () => resolve(result);
    tx.onerror = tx.onabort = () => resolve(undefined);
  }).catch(() => undefined);
}
export async function loadManifest() {
  try {
    const response = await fetch('./data/manifest.json',{cache:'no-cache'});
    if (!response.ok) throw new Error('词库尚未构建。请运行构建脚本后刷新。');
    const manifest = await response.json();
    if (!manifest.version || !manifest.index_lite?.sha256 || !manifest.wordforms_lookup?.sha256) throw new Error('词库清单格式错误。');
    await persisted('manifest',manifest);
    return manifest;
  } catch (error) {
    const saved = await persisted('manifest');
    if (saved) return saved;
    throw error;
  }
}
export async function loadDataset(meta, version) {
  const key = `${version}:${meta.sha256}`;
  let payload = await persisted(key);
  const url = `./data/${meta.file}?sha=${meta.sha256}&version=${encodeURIComponent(version)}`;
  let cache, response;
  try {cache=await caches.open('open-malti-shards-v2');} catch { /* private mode */ }
  if (!payload) {
    try {response=await cache?.match(url);} catch { /* cache unavailable */ }
    if (!response) response=await fetch(url,{cache:'no-cache'});
    if (!response.ok) throw new Error(`词库加载失败 (${response.status})，请重试。`);
    payload=await response.clone().arrayBuffer();
  }
  if (globalThis.crypto?.subtle) {
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',payload))].map(b=>b.toString(16).padStart(2,'0')).join('');
    if (digest !== meta.sha256) {
      await persisted(key,null);
      try {await cache?.delete(url);} catch { /* private mode */ }
      throw new Error('词库正在更新或缓存已损坏，请刷新后重试。');
    }
  }
  const data=JSON.parse(new TextDecoder().decode(payload));
  await persisted(key,payload);
  if (response && cache) {try {await cache.put(url,response);} catch { /* quota */ }}
  return data;
}
export async function loadEntry(index, manifest) {
  const meta = manifest.shards.find(s => s.bucket === index.bucket);
  if (!meta) throw new Error('找不到词条所在分片。');
  const key = `${manifest.version}:${meta.sha256}`;
  if (!memory.has(key)) {
    if (!inflight.has(key)) inflight.set(key, loadShard(meta,manifest.version).finally(() => inflight.delete(key)));
    memory.set(key, await inflight.get(key));
    if (memory.size > 4) memory.delete(memory.keys().next().value);
  }
  const entry = memory.get(key).get(index.id);
  if (!entry) throw new Error('索引与词条不一致，请刷新页面。');
  return entry;
}
async function loadShard(meta, version) {
  const data = await loadDataset(meta,version);
  if (!Array.isArray(data)) throw new Error('词条分片格式错误。');
  return new Map(data.map(e => [e.id, e]));
}
