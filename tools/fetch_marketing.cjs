'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const firebaseDir = path.join(process.env.APPDATA, 'npm', 'node_modules', 'firebase-tools', 'lib');
const auth = require(path.join(firebaseDir, 'auth.js'));

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
  const account = auth.getGlobalDefaultAccount();
  if (!account?.user?.email?.endsWith('@chaakan.co.kr')) throw new Error('Company Firebase CLI account required');
  const token = await auth.getAccessToken(account.tokens.refresh_token, []);
  const home = await (await get('https://chaakan-creator-hub.web.app/')).text();
  const script = home.match(/modulepreload[^>]+href="([^"]+)"/);
  if (!script) throw new Error('Marketing app module not found');
  const js = await (await get(new URL(script[1], 'https://chaakan-creator-hub.web.app/'))).text();
  const config = js.match(/apiKey:[`"]([^`"]+)[`"],authDomain:[`"]chaakan-creator-hub\.firebaseapp\.com/);
  if (!config) throw new Error('Marketing Firebase public config not found');
  const response = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${encodeURIComponent(config[1])}`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, signal: AbortSignal.timeout(30000),
    body: JSON.stringify({requestUri: 'https://chaakan-creator-hub.web.app/', postBody: new URLSearchParams({access_token: token.access_token, providerId: 'google.com'}).toString(), returnSecureToken: true})
  });
  const login = await response.json();
  if (!response.ok || !login.idToken) throw new Error(`Marketing sign-in failed: ${(login.error?.message || String(response.status)).replaceAll(token.access_token, '[token]').replace(/[A-Za-z0-9_-]{40,}/g, '[redacted]')}`);
  const output = {fetchedAt: new Date().toISOString()};
  for (const collection of ['creators', 'contents', 'reels', 'adCreatives']) {
    let next = '', records = [];
    do {
      const url = new URL(`https://firestore.googleapis.com/v1/projects/chaakan-creator-hub/databases/(default)/documents/${collection}`);
      url.searchParams.set('pageSize', '300');
      if (next) url.searchParams.set('pageToken', next);
      const data = await (await get(url, {headers: {Authorization: `Bearer ${login.idToken}`}})).json();
      records.push(...(data.documents || []).map(doc => ({id: doc.name.split('/').at(-1), ...Object.fromEntries(Object.entries(doc.fields || {}).map(([k, v]) => [k, decode(v)]))})));
      next = data.nextPageToken || '';
    } while (next);
    output[collection] = records;
  }
  // Auth credentials stay in process memory; the private cache is excluded from git.
  fs.mkdirSync(path.join(root, 'runtime'), {recursive: true});
  fs.writeFileSync(path.join(root, 'runtime', 'marketing-source.json'), JSON.stringify(output));
  console.log(JSON.stringify({ok: true, counts: Object.fromEntries(Object.entries(output).filter(([,v]) => Array.isArray(v)).map(([k,v])=>[k,v.length]))}));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
