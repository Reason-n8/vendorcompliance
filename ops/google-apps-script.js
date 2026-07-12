/**
 * Google Apps Script — Lead Logger for VendorCompliance OS + RankFixer
 * ---------------------------------------------------------------------------
 * SETUP (2 min, free):
 *   1. Go to https://script.google.com → New project → paste this code.
 *   2. Create (or open) your Google Sheet, name the first tab "Leads",
 *      and add the header row (see leads-template.csv):
 *      Timestamp | Name | Email | Company | Plan Interest | Vendor Count |
 *      Message | Source | Status | Lead Score | Last Contact | Follow-up Date | Notes
 *   3. In the script, click the folder icon → "Add a script-bound sheet"
 *      OR just run it from the sheet's Extensions → Apps Script (so
 *      SpreadsheetApp.getActiveSpreadsheet() resolves to YOUR sheet).
 *   4. Deploy → New deployment → type "Web app" →
 *        Execute as: Me   |   Who has access: Anyone
 *   5. Copy the Web app URL (https://script.google.com/macros/s/XXXX/exec)
 *      and paste it into each site form's  data-webhook="..."  attribute.
 *
 * The web app returns CORS headers automatically (Apps Script "Anyone"
 * deployments send Access-Control-Allow-Origin: *), so the browser fetch
 * from the static site works without extra config.
 */

function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Leads');
    if (!sheet) sheet = ss.getSheets()[0]; // fallback to first tab

    // Prefer URL-encoded params; fall back to JSON body.
    var p = (e && e.parameter) ? e.parameter : {};
    if ((!p || Object.keys(p).length === 0) && e && e.postData && e.postData.contents) {
      try { p = JSON.parse(e.postData.contents); } catch (err) { /* keep empty */ }
    }

    var now = new Date();
    var row = [
      now,                                   // Timestamp
      p.name || '',                          // Name
      p.email || '',                         // Email
      p.company || '',                       // Company
      p.interest || p.plan || p['plan interest'] || '', // Plan Interest
      p.vendors || p.vendorcount || p['vendor count'] || '', // Vendor Count
      p.message || '',                       // Message
      p.source || '',                        // Source
      'New',                                 // Status
      p.score || '',                         // Lead Score
      '',                                    // Last Contact
      '',                                    // Follow-up Date
      p.notes || ''                          // Notes
    ];
    sheet.appendRow(row);

    return ContentService
      .createTextOutput(JSON.stringify({ result: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ result: 'error', error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Silence OPTIONS preflight if any proxy injects it (Apps Script handles CORS,
// but returning 200 keeps strict clients happy).
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ result: 'ready' }))
    .setMimeType(ContentService.MimeType.JSON);
}
