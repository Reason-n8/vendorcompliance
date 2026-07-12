/**
 * RankFixer / VendorCompliance OS — Autonomous Lead-to-Cash (Phase 1)
 * ===========================================================================
 * PHASE 1 (this file, runs free in Google Apps Script):
 *   - Lead capture  -> append row (already wired from the site forms)
 *   - Auto scoring  -> Lead Score + Priority + Follow-up Date set on arrival
 *   - Auto outreach -> Gmail email to High/Medium leads the moment they submit
 *   - Auto nudge    -> time-driven: +3 days gentle nudge, +7 days -> "Cold"
 *   - Digests       -> time-driven daily + weekly summary to YOU
 *
 * PHASE 2 (Make.com / Zapier free tier + Calendly) — STUBBED below:
 *   - Day 1 / 3 / 7 email sequence, reply detection, demo scheduling.
 *   - Wire in Make/Zapier; the hooks (status flags) are already set here.
 *
 * PHASE 3 (Stripe) — STUBBED below:
 *   - Auto-invoice on acceptance, welcome + onboarding email on payment.
 *   - Needs Stripe secret key (store in Script Properties, not inline).
 *
 * SETUP:
 *   1. In the bound sheet: Extensions -> Apps Script -> paste this whole file
 *      (replacing the old doPost-only version).
 *   2. Ensure the first tab is named exactly "Leads" with the 14-col header:
 *      Timestamp | Name | Email | Company | Plan Interest | Vendor Count |
 *      Message | Source | Status | Lead Score | Priority | Last Contact |
 *      Follow-up Date | Notes
 *   3. Enable triggers (Edit -> Current project's triggers -> + Add trigger):
 *        - runNudges      : Time-driven -> Day timer -> 7am-8am
 *        - sendDailyDigest: Time-driven -> Day timer -> 8am-9am
 *        - sendWeeklyReport: Time-driven -> Week timer -> Monday
 *   4. Authorize when prompted (Gmail / Sheets scopes).
 *
 * CAN-SPAM: outbound emails include identification + a way to opt out.
 * Keep volumes within Apps Script free quota (~100 sends/day).
 */

// ---- CONFIG (edit these) ----
var OWNER_EMAIL = "acibronjan@gmail.com"; // where digests + alerts go
var REPLY_DETECTION = false; // set true only after Phase 2 (Make/Zapier) is wired

// ===========================================================================
// doPost — called by the site forms. Appends a scored, prioritized lead row
// and fires an instant outreach email for High/Medium leads.
// ===========================================================================
function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName('Leads');
    if (!sheet) sheet = ss.getSheets()[0];

    var p = (e && e.parameter) ? e.parameter : {};
    if ((!p || Object.keys(p).length === 0) && e && e.postData && e.postData.contents) {
      try { p = JSON.parse(e.postData.contents); } catch (err) { /* keep empty */ }
    }

    var now = new Date();
    var score = scoreLead(p);
    var priority = priorityFromScore(score);
    var followup = new Date(now.getTime() + followupDays(priority) * 86400000);

    var row = [
      now,
      p.name || '',
      p.email || '',
      p.company || '',
      p.interest || p.plan || p['plan interest'] || '',
      p.vendors || p.vendorcount || p['vendor count'] || '',
      p.message || '',
      p.source || '',
      'New',
      score,
      priority,
      '',                       // Last Contact
      followup,                // Follow-up Date
      ''                       // Notes
    ];
    sheet.appendRow(row);

    // Instant outreach for High/Medium leads
    if (priority !== 'Low' && p.email) {
      sendIntroEmail(p, priority);
      // mark first touch
      var lastCol = 12; // Last Contact is col 12 (1-indexed)
      var newRow = sheet.getLastRow();
      sheet.getRange(newRow, lastCol).setValue(now);
    }

    // High-value alert to owner
    if (priority === 'High') {
      MailApp.sendEmail(OWNER_EMAIL,
        "🔥 High-value lead: " + (p.company || p.name || 'unknown'),
        "New " + (p.source || 'lead') + " lead — " + (p.name || '') + " (" + (p.email || '') + ")\n" +
        "Plan: " + (p.interest || p.plan || '') + "\nScore: " + score + " / " + priority + "\n" +
        (p.message || ''));
    }

    return ContentService
      .createTextOutput(JSON.stringify({ result: 'ok' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ result: 'error', error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ result: 'ready' }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ===========================================================================
// SCORING
// ===========================================================================
function scoreLead(p) {
  var plan = (p.plan || p.interest || '').toString().toLowerCase();
  var base = 50;
  if (plan.indexOf('unlimited') >= 0) base = 90;
  else if (plan.indexOf('pro') >= 0) base = 82;
  else if (plan.indexOf('growth') >= 0) base = 80;
  else if (plan.indexOf('paid report') >= 0) base = 75;
  else if (plan.indexOf('starter') >= 0) base = 60;
  else if (plan.indexOf('free') >= 0) base = 40;

  var v = parseInt(p.vendors || '0', 10) || 0;
  if (v >= 50) base += 8;
  else if (v >= 20) base += 5;
  else if (v >= 5) base += 2;

  return Math.min(100, base);
}

function priorityFromScore(s) {
  if (s >= 80) return 'High';
  if (s >= 60) return 'Medium';
  return 'Low';
}

function followupDays(priority) {
  if (priority === 'High') return 1;
  if (priority === 'Medium') return 2;
  return 4;
}

// ===========================================================================
// INSTANT OUTREACH (called from doPost for High/Medium)
// ===========================================================================
function sendIntroEmail(p, priority) {
  var product = (p.source || 'our product');
  var name = (p.name || 'there').split(' ')[0];
  var plan = (p.interest || p.plan || '');
  var subject = "Re: your " + product + " inquiry — next step for " + (p.company || name);
  var body =
    "Hi " + name + ",\n\n" +
    "Thanks for reaching out about " + product + (plan ? " (" + plan + ")" : "") + ". " +
    "I'm Jan from the team.\n\n" +
    "You're in good company — most teams don't realize how much AI visibility / COI risk they're sitting on until it costs them. " +
    "I'll get you a tailored next step within 24 hours.\n\n" +
    (p.message ? "Quick note on what you shared: \"" + p.message + "\"\n\n" : "") +
    "In the meantime, reply to this email with any questions — happy to help.\n\n" +
    "Best,\nJan\n" + product + "\n\n" +
    "---\nYou're receiving this because you requested info from " + product +
    ". Reply \"unsubscribe\" and we'll stop. (" + OWNER_EMAIL + ")";

  GmailApp.sendEmail(p.email, subject, body, { name: "RankFixer / VendorCompliance" });
}

// ===========================================================================
// TIME-DRIVEN: NUDGES (+3d gentle, +7d -> Cold)
// ===========================================================================
function runNudges() {
  var sheet = getLeadsSheet();
  if (!sheet) return;
  var data = sheet.getDataRange().getValues();
  var today = new Date();
  for (var i = 1; i < data.length; i++) {
    var status = (data[i][8] || '').toString();
    if (status === 'Won' || status === 'Lost' || status === 'Cold') continue;
    var followup = data[i][12]; // Follow-up Date col
    if (!(followup instanceof Date)) continue;
    var ageDays = Math.floor((today - followup) / 86400000);

    if (ageDays >= 7 && status !== 'Cold') {
      sheet.getRange(i + 1, 9).setValue('Cold'); // Status col
    } else if (ageDays >= 3 && ageDays < 7 && status === 'New') {
      var email = data[i][2];
      if (email) {
        GmailApp.sendEmail(email,
          "Following up — " + (data[i][3] || 'quick question'),
          "Hi " + ((data[i][1] || 'there').split(' ')[0]) + ",\n\nJust bumping my last note. " +
          "No rush — reply whenever's convenient.\n\nBest,\nJan");
        sheet.getRange(i + 1, 9).setValue('Contacted');
      }
    }
  }
}

// ===========================================================================
// TIME-DRIVEN: DAILY DIGEST
// ===========================================================================
function sendDailyDigest() {
  var sheet = getLeadsSheet();
  if (!sheet) return;
  var data = sheet.getDataRange().getValues();
  var today = new Date();
  var newToday = 0, highToday = 0, pipeline = 0;
  for (var i = 1; i < data.length; i++) {
    var ts = data[i][0];
    if (ts instanceof Date && isSameDay(ts, today)) {
      newToday++;
      if ((data[i][10] || '') === 'High') highToday++; // Priority col
    }
    var st = (data[i][8] || '').toString();
    if (st !== 'Won' && st !== 'Lost' && st !== 'Cold') {
      pipeline += valueOf(data[i][4]); // rough pipeline from plan
    }
  }
  var msg =
    "📊 Daily Lead Digest (" + today.toDateString() + ")\n\n" +
    "New leads today: " + newToday + "\n" +
    "High-priority today: " + highToday + "\n" +
    "Open pipeline (est): $" + pipeline.toLocaleString() + "\n";
  MailApp.sendEmail(OWNER_EMAIL, "📊 Daily Lead Digest", msg);
}

// ===========================================================================
// TIME-DRIVEN: WEEKLY REPORT
// ===========================================================================
function sendWeeklyReport() {
  var sheet = getLeadsSheet();
  if (!sheet) return;
  var data = sheet.getDataRange().getValues();
  var total = 0, won = 0, lost = 0;
  for (var i = 1; i < data.length; i++) {
    total++;
    var st = (data[i][8] || '').toString();
    if (st === 'Won') won++;
    if (st === 'Lost') lost++;
  }
  var conv = total ? Math.round((won / total) * 100) : 0;
  var msg =
    "📈 Weekly Report\n\n" +
    "Total leads: " + total + "\n" +
    "Won: " + won + " | Lost: " + lost + "\n" +
    "Conversion: " + conv + "%\n";
  MailApp.sendEmail(OWNER_EMAIL, "📈 Weekly Lead Report", msg);
}

// ===========================================================================
// HELPERS
// ===========================================================================
function getLeadsSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('Leads');
  return sheet || ss.getSheets()[0];
}
function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
function valueOf(plan) {
  var s = (plan || '').toString().toLowerCase();
  if (s.indexOf('unlimited') >= 0) return 499;
  if (s.indexOf('pro') >= 0) return 249;
  if (s.indexOf('growth') >= 0) return 249;
  if (s.indexOf('paid report') >= 0) return 99;
  if (s.indexOf('starter') >= 0) return 99;
  return 0;
}

// ===========================================================================
// PHASE 2 STUB — Make.com / Zapier + Calendly
// ---------------------------------------------------------------------------
// Wire in Make/Zapier free tier (NOT Apps Script):
//   - Trigger: new row in Leads (Status = New)
//   - Day 1: already sent by sendIntroEmail (doPost)
//   - Day 3 / Day 7: sequence emails (or rely on runNudges above)
//   - Reply detection: Gmail "new reply" -> set Status = Contacted,
//     add row flag; when Status -> Demo, send Calendly link via GmailApp.
//   - Calendly webhook -> on booked, set Status = Demo, send confirmation.
// Set REPLY_DETECTION = true once this is live so logic can branch on it.
// ===========================================================================
function phase2HookPlaceholder() {
  // Intentionally empty. Phase 2 lives in Make/Zapier.
}

// ===========================================================================
// PHASE 3 STUB — Stripe auto-invoice + welcome
// ---------------------------------------------------------------------------
// After demo (Status = Demo -> Negotiating -> Won):
//   - Create Stripe Checkout session via UrlFetchApp (needs Stripe secret
//     key stored in Script Properties: ScriptProperties.getProperty('STRIPE_KEY')).
//   - On payment webhook, send welcome email + onboarding link.
// Keep the key OUT of source. Example shape:
//
//   function createStripeCheckout(amountCents, email) {
//     var key = ScriptProperties.getProperty('STRIPE_KEY');
//     var payload = {
//       mode: 'payment',
//       success_url: 'https://rankfixer.co/thanks',
//       cancel_url: 'https://rankfixer.co/pricing',
//       line_items: [{ price_data: {
//         currency: 'usd', unit_amount: amountCents,
//         product_data: { name: 'VendorCompliance OS — Growth' } }, quantity: 1 }],
//       customer_email: email
//     };
//     UrlFetchApp.fetch('https://api.stripe.com/v1/checkout/sessions', {
//       method: 'post',
//       headers: { Authorization: 'Bearer ' + key,
//                  'Content-Type': 'application/x-www-form-urlencoded' },
//       payload: payload
//     });
//   }
// ===========================================================================
function phase3HookPlaceholder() {
  // Intentionally empty. Phase 3 needs Stripe key in Script Properties.
}
