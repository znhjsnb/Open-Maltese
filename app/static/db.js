/* All generated assets are bound to manifest version + SHA-256. */
const memory = new Map(), inflight = new Map();
let database;
function openDatabase() {
  if (!globalThis.indexedDB) return Promise.resolve(null);
  if (!database) database = new Promise((resolve,reject) => {
    let blocked=false;
    const request = indexedDB.open('open-malti-data',2);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains('files')) request.result.createObjectStore('files');
    };
    request.onsuccess = () => {
      if (blocked) {request.result.close();return;}
      request.result.onversionchange=()=>{request.result.close();database=undefined;};
      resolve(request.result);
    };
    request.onerror = () => reject(request.error);
    request.onblocked = () => {blocked=true;resolve(null);};
  }).catch(() => null).then(db=>{if (!db) database=undefined;return db;});
  return database;
}
async function persisted(key, value) {
  const db = await openDatabase();
  if (!db) return undefined;
  return new Promise(resolve => {
    const tx = db.transaction('files',value === undefined ? 'readonly' : 'readwrite');
    const store = tx.objectStore('files');
    const request = value === undefined ? store.get(key) : store.put(value,key);
    let result;
    request.onsuccess = () => {result=request.result;};
    tx.oncomplete = () => resolve(result);
    tx.onerror = tx.onabort = () => resolve(undefined);
  }).catch(() => undefined);
}
async function readRecord(key) {
  const saved = await persisted(key);
  if (saved !== undefined) return saved;
  // Preserve version-1 caches during the object-store migration.
  const db = await openDatabase();
  if (!db?.objectStoreNames.contains('assets')) return undefined;
  return new Promise(resolve => {
    const tx=db.transaction('assets','readonly'), request=tx.objectStore('assets').get(key);
    let value;
    request.onsuccess=()=>{value=request.result;};
    tx.oncomplete=()=>resolve(value);
    tx.onerror=tx.onabort=()=>resolve(undefined);
  }).catch(()=>undefined);
}
async function verifyPayload(payload, meta, required=false) {
  if (!globalThis.crypto?.subtle) {
    if (required) throw new Error('离线准备需要 SHA-256 校验，请使用 localhost 或 HTTPS。');
    return;
  }
  const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',payload))].map(b=>b.toString(16).padStart(2,'0')).join('');
  if (digest !== meta.sha256) throw new Error('词库正在更新或缓存已损坏，请刷新后重试。');
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
    const saved = await readRecord('manifest');
    if (saved) return saved;
    throw error;
  }
}
export async function loadDataset(meta, version) {
  const key = `${version}:${meta.sha256}`;
  let payload = await readRecord(key);
  const url = `./data/${meta.file}?sha=${meta.sha256}&version=${encodeURIComponent(version)}`;
  let cache, response;
  try {cache=await caches.open('open-malti-shards-v2');} catch { /* private mode */ }
  if (!payload) {
    try {response=await cache?.match(url);} catch { /* cache unavailable */ }
    if (!response) response=await fetch(url,{cache:'no-cache'});
    if (!response.ok) throw new Error(`词库加载失败 (${response.status})，请重试。`);
    payload=await response.clone().arrayBuffer();
  }
  try { await verifyPayload(payload,meta); }
  catch (error) {
      await persisted(key,null);
      try {await cache?.delete(url);} catch { /* private mode */ }
      throw error;
  }
  const data=JSON.parse(new TextDecoder().decode(payload));
  await persisted(key,payload);
  if (response && cache) {try {await cache.put(url,response);} catch { /* quota */ }}
  return data;
}
export const loadJson = loadDataset;

export async function prepareOffline(manifest, {onProgress, shouldPause} = {}) {
  const pinned=structuredClone(manifest), version=pinned.version;
  const assets=[pinned.index_lite,pinned.wordforms_lookup,...pinned.shards];
  if (!version || assets.length !== 32 || assets.some(m=>!m?.file || !m.sha256)) throw new Error('离线清单必须包含索引、反查表与 30 个分片。');
  if (!await openDatabase()) throw new Error('IndexedDB 不可用，无法持久保存离线词库。');
  if (!globalThis.crypto?.subtle) throw new Error('离线准备需要 SHA-256 校验，请使用 localhost 或 HTTPS。');
  let completed=0;
  for (const meta of assets) {
    if (shouldPause?.()) return {version,completed,total:assets.length,paused:true};
    const key=`${version}:${meta.sha256}`;
    // A previous partial run can resume only from verified persistent bytes.
    let payload=await readRecord(key);
    if (payload) {
      try {await verifyPayload(payload,meta,true);} catch {payload=null;await persisted(key,null);}
    }
    if (!payload) {
      await loadDataset(meta,version);
      payload=await readRecord(key);
    }
    if (!payload) throw new Error(`IndexedDB 回读失败：${meta.file}，离线词库尚未就绪。`);
    await verifyPayload(payload,meta,true);
    // Migrate legacy assets too, then independently read the destination store.
    await persisted(key,payload);
    const saved=await persisted(key);
    if (!saved) throw new Error(`IndexedDB 写入或回读失败：${meta.file}。`);
    await verifyPayload(saved,meta,true);
    onProgress?.({version,completed:++completed,total:assets.length,file:meta.file});
  }
  await persisted('manifest',pinned);
  if ((await persisted('manifest'))?.version !== version) throw new Error('IndexedDB 离线清单回读失败。');
  return {version,completed,total:assets.length,paused:false};
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
