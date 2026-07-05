const SHEET_NAME     = 'Temperatures';
const VISITORS_SHEET = 'Visiteurs';
const SPREADSHEET_ID = '1-bCZDpK7PwrMPeG7KcUEcpXs1LcsND7C4tnJMInwnoo';
const FIREBASE_URL   = 'https://lac-manitou-temperatures-d284a-default-rtdb.firebaseio.com';

// ── Migration one-shot : Sheet Temperatures → Firebase /readings ──────────────
// À lancer manuellement depuis l'éditeur GAS (bouton Run).
//
// Anti-doublon : ne migre QUE les lignes antérieures à la première écriture
// live de HA dans Firebase (détectée automatiquement). Les lectures récentes
// sont déjà dans Firebase via le dual-write, donc on ne les recopie pas.
// Clé Firebase = timestamp ms → idempotent : relançable sans créer de doublon.
function migrateSheetToFirebase() {
  // 1) Détecter la plus ancienne clé live déjà présente dans Firebase
  const firstRes = UrlFetchApp.fetch(
    FIREBASE_URL + '/readings.json?orderBy=' + encodeURIComponent('"$key"') + '&limitToFirst=1',
    { muteHttpExceptions: true }
  );
  let cutoff = Infinity;
  try {
    const obj = JSON.parse(firstRes.getContentText());
    if (obj && typeof obj === 'object') {
      const k = Object.keys(obj)[0];
      if (k) cutoff = Number(k);
    }
  } catch (e) {}
  Logger.log('Point de coupure (1re écriture live Firebase) : %s (%s)',
             cutoff, cutoff === Infinity ? 'aucune' : new Date(cutoff).toISOString());

  // 2) Lire le Sheet et ne garder que ts < cutoff
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);
  const lastRow = sheet ? sheet.getLastRow() : 0;
  if (lastRow < 2) { Logger.log('Aucune donnée à migrer'); return; }

  const rows = sheet.getRange(2, 1, lastRow - 1, 4).getValues(); // Timestamp, Air, Surface, 4pi
  const round2 = v => Math.round(parseFloat(v) * 100) / 100;

  const BATCH = 2000;
  let total = 0, skipped = 0;
  for (let i = 0; i < rows.length; i += BATCH) {
    const chunk = rows.slice(i, i + BATCH);
    const payload = {};
    chunk.forEach(function(r) {
      const ts = new Date(r[0]).getTime();
      if (!ts || isNaN(ts)) return;
      if (ts >= cutoff) { skipped++; return; }   // déjà en live → on saute
      const air = round2(r[1]), surface = round2(r[2]), depth = round2(r[3]);
      if ([air, surface, depth].some(isNaN)) return;
      payload[ts] = { air: air, surface: surface, depth: depth };
    });
    const n = Object.keys(payload).length;
    if (!n) continue;
    const res = UrlFetchApp.fetch(FIREBASE_URL + '/readings.json', {
      method: 'patch',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    total += n;
    Logger.log('Batch → HTTP %s (%s lignes)', res.getResponseCode(), n);
  }
  Logger.log('Migration terminée : %s lignes migrées, %s ignorées (déjà en live)',
             total, skipped);
}

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    const expected = PropertiesService.getScriptProperties().getProperty('POST_TOKEN');
    if (!expected || data.token !== expected) {
      return ContentService
        .createTextOutput(JSON.stringify({ status: 'error', message: 'Unauthorized' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    let sheet = ss.getSheetByName(SHEET_NAME);

    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(['Timestamp', 'Air (°C)', 'Surface (°C)', '4 pieds (°C)']);
      sheet.setFrozenRows(1);
    }

    // Bulk insert (array) ou insertion simple
    const rows = Array.isArray(data) ? data : [data];

    if (rows.length > 1000) {
      return ContentService
        .createTextOutput(JSON.stringify({ status: 'error', message: 'Batch too large' }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const TEMP_MIN = -50, TEMP_MAX = 60;
    const values = rows.map(r => {
      const air     = parseFloat(r.air);
      const surface = parseFloat(r.surface);
      const depth   = parseFloat(r.depth);
      if ([air, surface, depth].some(v => isNaN(v) || v < TEMP_MIN || v > TEMP_MAX)) {
        throw new Error('Temperature out of range');
      }
      return [new Date(r.timestamp || Date.now()), air, surface, depth];
    });

    sheet.getRange(sheet.getLastRow() + 1, 1, values.length, 4).setValues(values);

    // Trier par timestamp après bulk insert
    if (values.length > 1) {
      const lastRow = sheet.getLastRow();
      sheet.getRange(2, 1, lastRow - 1, 4).sort(1);
    }

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'ok', inserted: values.length }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error('doPost error:', err.message);
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: 'Internal error' }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  // ── Redirection vers le nouveau domaine Firebase ──────────────────────────
  // Pour REVENIR à l'ancienne page GAS : commenter ce bloc de redirection
  // et décommenter le bloc « ANCIEN CODE » plus bas.
  var url = 'https://lmt.bcourchesne.com';
  return HtmlService.createHtmlOutput(
    '<!DOCTYPE html><html><head><base target="_top"><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
    '<title>Lac Manitou — Températures</title>' +
    // Tente la vraie redirection top (change l\'URL) là où le navigateur
    // l\'autorise ; sinon l\'utilisateur clique le bouton ci-dessous.
    '<script>try{window.top.location.href=' + JSON.stringify(url) + ';}catch(e){}<\/script>' +
    '</head>' +
    '<body style="font-family:sans-serif;background:#0a1524;color:#e2eaf4;margin:0;' +
    'display:flex;align-items:center;justify-content:center;min-height:100vh;text-align:center">' +
    '<div style="padding:2rem;max-width:420px">' +
    '<h1 style="font-size:1.3rem;font-weight:500;margin:0 0 .5rem">Le site a déménagé</h1>' +
    '<p style="color:#9fb3c8;margin:0 0 1.5rem">Lac Manitou — Températures est maintenant ' +
    'à sa nouvelle adresse.</p>' +
    '<a href="' + url + '" target="_top" style="display:inline-block;background:#38bdf8;' +
    'color:#0a1524;font-weight:600;padding:.75rem 1.5rem;border-radius:10px;text-decoration:none">' +
    'Voir les températures →</a>' +
    '<p style="margin:1.5rem 0 0;font-size:.8rem;color:#5f7891">' + url + '</p>' +
    '</div></body></html>'
  )
    .setTitle('Lac Manitou — Températures')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);

  /* ── ANCIEN CODE (décommenter pour restaurer la page GAS d'origine) ─────────
  const action = e.parameter && e.parameter.action;

  if (action === 'getData') {
    const period = e.parameter.period || '24h';
    const data = getDataJson(period);
    return ContentService
      .createTextOutput(JSON.stringify(data))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'trackVisitor') {
    const vid = e.parameter.vid || '';
    const result = trackVisitor(vid);
    return ContentService
      .createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  }

  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Lac Manitou — Températures')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0')
    .setSandboxMode(HtmlService.SandboxMode.IFRAME);
  ── FIN ANCIEN CODE ──────────────────────────────────────────────────────── */
}

// Appelée via google.script.run depuis le client
function getDataJson(period) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);

  const lastRow = sheet ? sheet.getLastRow() : 0;
  if (!sheet || lastRow < 2) return [];

  const now = new Date();
  let ms;
  switch (period) {
    case '7d':     ms = 7   * 24 * 60 * 60 * 1000; break;
    case '30d':    ms = 30  * 24 * 60 * 60 * 1000; break;
    case 'season': ms = 180 * 24 * 60 * 60 * 1000; break;
    case 'year':   ms = 365 * 24 * 60 * 60 * 1000; break;
    default:       ms =       24 * 60 * 60 * 1000;
  }
  const cutoff = new Date(now - ms);

  // Lire depuis la fin — données triées ASC, + 20% marge
  const maxRows  = Math.ceil(ms / (5 * 60 * 1000) * 1.2);
  const startRow = Math.max(2, lastRow - maxRows + 1);
  const rows     = sheet.getRange(startRow, 1, lastRow - startRow + 1, 4).getValues();

  // Granularité selon la période
  // 24h → brut | 7d/30d → moyenne horaire | saison/année → moyenne journalière
  const bucketMs = (period === 'season' || period === 'year')
    ? 24 * 60 * 60 * 1000
    : (period === '7d' || period === '30d')
      ? 60 * 60 * 1000
      : 0;

  if (bucketMs === 0) {
    const data = [];
    for (let i = 0; i < rows.length; i++) {
      const ts = new Date(rows[i][0]);
      if (ts >= cutoff) data.push({ t: ts.toISOString(), air: rows[i][1], surface: rows[i][2], depth: rows[i][3] });
    }
    return data;
  }

  // Agréger par bucket (heure ou jour)
  const buckets = {};
  for (let i = 0; i < rows.length; i++) {
    const ts = new Date(rows[i][0]);
    if (ts < cutoff) continue;
    const key = Math.floor(ts.getTime() / bucketMs) * bucketMs;
    if (!buckets[key]) buckets[key] = { a: 0, s: 0, d: 0, n: 0 };
    buckets[key].a += rows[i][1];
    buckets[key].s += rows[i][2];
    buckets[key].d += rows[i][3];
    buckets[key].n++;
  }

  const round1 = v => Math.round(v * 10) / 10;
  return Object.keys(buckets).sort((a, b) => a - b).map(key => {
    const b = buckets[key];
    return { t: new Date(+key).toISOString(), air: round1(b.a / b.n), surface: round1(b.s / b.n), depth: round1(b.d / b.n) };
  });
}

// ── Visiteurs uniques ─────────────────────────────────────────────────────────
function trackVisitor(visitorId) {
  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (!visitorId || !UUID_RE.test(visitorId)) {
    return { status: 'invalid' };
  }

  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(VISITORS_SHEET);

  if (!sheet) {
    sheet = ss.insertSheet(VISITORS_SHEET);
    sheet.appendRow(['Visitor ID', 'Première visite', 'Dernière visite', 'Nb visites']);
    sheet.setFrozenRows(1);
  }

  const rows  = sheet.getDataRange().getValues();
  const now   = new Date();

  for (let i = 1; i < rows.length; i++) {
    if (rows[i][0] === visitorId) {
      // Visiteur connu — màj dernière visite + compteur
      sheet.getRange(i + 1, 3).setValue(now);
      sheet.getRange(i + 1, 4).setValue(rows[i][3] + 1);
      return { status: 'returning', visits: rows[i][3] + 1 };
    }
  }

  // Nouveau visiteur
  sheet.appendRow([visitorId, now, now, 1]);
  return { status: 'new', visits: 1 };
}

// ── Google Analytics 4 via Measurement Protocol ──────────────────────────────
function logGa4Event(eventName, params, clientId) {
  try {
    const apiSecret   = PropertiesService.getScriptProperties().getProperty('GA4_API_SECRET');
    const measurementId = 'G-DPZEL02P7N';
    if (!apiSecret) return;

    const url = 'https://www.google-analytics.com/mp/collect'
      + '?measurement_id=' + measurementId
      + '&api_secret=' + apiSecret;

    const payload = {
      client_id: clientId || ('gas.' + Utilities.getUuid()),
      events: [{ name: eventName, params: Object.assign({ engagement_time_msec: '100' }, params || {}) }]
    };

    UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
  } catch(e) {
    console.error('GA4 event error:', e.message);
  }
}

// ── Stats visiteurs (pour usage futur) ───────────────────────────────────────
function getVisitorStats() {
  const ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(VISITORS_SHEET);
  if (!sheet || sheet.getLastRow() < 2) return { total: 0, today: 0 };

  const rows  = sheet.getDataRange().getValues();
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  let todayCount = 0;

  for (let i = 1; i < rows.length; i++) {
    const last = new Date(rows[i][2]);
    if (last >= today) todayCount++;
  }

  return { total: rows.length - 1, today: todayCount };
}
