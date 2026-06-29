const SHEET_NAME     = 'Temperatures';
const VISITORS_SHEET = 'Visiteurs';
const SPREADSHEET_ID = '1-bCZDpK7PwrMPeG7KcUEcpXs1LcsND7C4tnJMInwnoo';

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
  const params = e.parameter;

  const html = HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Lac Manitou — Températures')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.SAMEORIGIN)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0')
    .setSandboxMode(HtmlService.SandboxMode.IFRAME);

  return html;
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
    case '7d':  ms = 7  * 24 * 60 * 60 * 1000; break;
    case '30d': ms = 30 * 24 * 60 * 60 * 1000; break;
    default:    ms =      24 * 60 * 60 * 1000;
  }
  const cutoff = new Date(now - ms);

  // Lire depuis la fin — les données sont triées par date ASC.
  // On estime le nb de lignes nécessaires (5 min interval) + 20% marge.
  const maxRows = Math.ceil(ms / (5 * 60 * 1000) * 1.2);
  const startRow = Math.max(2, lastRow - maxRows + 1);
  const numRows  = lastRow - startRow + 1;

  const rows = sheet.getRange(startRow, 1, numRows, 4).getValues();
  const data = [];

  for (let i = 0; i < rows.length; i++) {
    const ts = new Date(rows[i][0]);
    if (ts >= cutoff) {
      data.push({
        t:       ts.toISOString(),
        air:     rows[i][1],
        surface: rows[i][2],
        depth:   rows[i][3]
      });
    }
  }

  return data;
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
