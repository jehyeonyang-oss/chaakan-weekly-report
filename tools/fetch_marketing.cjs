'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const authFile = path.join(root, 'runtime', 'marketing-auth.json');

async function get(url, options = {}) {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`Source request failed: HTTP ${response.status}`);
  return response;
}
function decode(field) {
  if ('stringValue' in field) return field.stringValue;
  if ('integerValue' in field) return Number(field.integerValue);
  if ('doubleValue' in field) return field.doubleValue;
  if ('booleanValue' in field) return field.booleanValue;
  if ('timestampValue' in field) return field.timestampValue;
  if ('arrayValue' in field) return (field.arrayValue.values || []).map(decode);
  if ('mapValue' in field) return Object.fromEntries(Object.entries(field.mapValue.fields || {}).map(([k, v]) => [k, decode(v)]));
  return null;
}
async function main() {
  if (!fs.existsSync(authFile)) throw new Error('MARKETING_LOGIN_REQUIRED');
  const auth = JSON.parse(fs.readFileSync(authFile, 'utf8'));
  if (auth.projectId !== 'chaakan-creator-hub' || !/@(?:chaakan\.co\.kr|seoul-link\.com)$/.test(auth.email || '')) throw new Error('MARKETING_LOGIN_REQUIRED');
  const response = await fetch(`https://securetoken.googleapis.com/v1/token?key=${encodeURIComponent(auth.apiKey)}`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, signal: AbortSignal.timeout(30000),
    body: JSON.stringify({grant_type: 'refresh_token', refresh_token: auth.refreshToken})
  });
  const login = await response.json();
  if (!response.ok || !login.id_token) throw new Error('MARKETING_LOGIN_REQUIRED');
  if (login.refresh_token && login.refresh_token !== auth.refreshToken) {
    fs.writeFileSync(authFile + '.tmp', JSON.stringify({...auth, refreshToken: login.refresh_token}));
    fs.renameSync(authFile + '.tmp', authFile);
  }
  const output = {fetchedAt: new Date().toISOString()};
  for (const collection of ['reels', 'people', 'brandazineLooks', 'adCreatives']) {
    let next = '', records = [];
    do {
      const url = new URL(`https://firestore.googleapis.com/v1/projects/chaakan-creator-hub/databases/(default)/documents/${collection}`);
      url.searchParams.set('pageSize', '300');
      if (next) url.searchParams.set('pageToken', next);
      const data = await (await get(url, {headers: {Authorization: `Bearer ${login.id_token}`}})).json();
      records.push(...(data.documents || []).map(doc => ({id: doc.name.split('/').at(-1), ...Object.fromEntries(Object.entries(doc.fields || {}).map(([k, v]) => [k, decode(v)]))})));
      next = data.nextPageToken || '';
    } while (next);
    output[collection] = records;
  }
  // Auth credentials and the raw source stay in gitignored runtime, never docs/.
  fs.mkdirSync(path.join(root, 'runtime'), {recursive: true});
  const target = path.join(root, 'runtime', 'marketing-source.json');
  fs.writeFileSync(target + '.tmp', JSON.stringify(output));
  fs.renameSync(target + '.tmp', target);
  console.log(JSON.stringify({ok: true, counts: Object.fromEntries(Object.entries(output).filter(([,v]) => Array.isArray(v)).map(([k,v])=>[k,v.length]))}));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
