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
    const values = rows.map(r => [
      new Date(r.timestamp || Date.now()),
      parseFloat(r.air),
      parseFloat(r.surface),
      parseFloat(r.depth)
    ]);

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
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  const params = e.parameter;

  if (params.data === 'true') {
    return getData(params.period || '24h');
  }

  const html = HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Lac Manitou — Températures')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1.0')
    .setSandboxMode(HtmlService.SandboxMode.IFRAME);

  return html;
}

function getData(period) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);

  if (!sheet || sheet.getLastRow() < 2) {
    return ContentService
      .createTextOutput(JSON.stringify({ data: [] }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const now = new Date();
  let cutoff;
  switch (period) {
    case '7d':  cutoff = new Date(now - 7  * 24 * 60 * 60 * 1000); break;
    case '30d': cutoff = new Date(now - 30 * 24 * 60 * 60 * 1000); break;
    default:    cutoff = new Date(now -      24 * 60 * 60 * 1000);
  }

  const rows = sheet.getDataRange().getValues();
  const data = [];

  for (let i = 1; i < rows.length; i++) {
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

  return ContentService
    .createTextOutput(JSON.stringify({ data }))
    .setMimeType(ContentService.MimeType.JSON);
}

// Appelée via google.script.run depuis le client
function getDataJson(period) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);

  if (!sheet || sheet.getLastRow() < 2) return [];

  const now = new Date();
  let cutoff;
  switch (period) {
    case '7d':  cutoff = new Date(now - 7  * 24 * 60 * 60 * 1000); break;
    case '30d': cutoff = new Date(now - 30 * 24 * 60 * 60 * 1000); break;
    default:    cutoff = new Date(now -      24 * 60 * 60 * 1000);
  }

  const rows = sheet.getDataRange().getValues();
  const data = [];

  for (let i = 1; i < rows.length; i++) {
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
