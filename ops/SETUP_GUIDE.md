# Lead-to-Cash System — Setup & Workflow

Autonomous lead pipeline for **VendorCompliance OS** + **RankFixer**.
Phases 1 is fully automated in Google Sheets + Apps Script (free). Phases
2–3 add Make/Zapier, Calendly, and Stripe (free/freemium tiers).

---

## PHASE 1 (DONE — Google Sheets + Apps Script, free)

### 1a. Sheet setup
1. Open your **Leads** Google Sheet → first tab named exactly `Leads`.
2. Header row (14 cols), copy from `leads-template.csv`:
   `Timestamp | Name | Email | Company | Plan Interest | Vendor Count |
   Message | Source | Status | Lead Score | Priority | Last Contact |
   Follow-up Date | Notes`
3. Format Timestamp / Last Contact / Follow-up Date as Date/Time.
4. Import `leads-template.csv` (has 2 sample rows) or just paste the header.

### 1b. Apps Script
1. Extensions → Apps Script → **replace all code** with `google-apps-script.js`.
2. Edit the CONFIG at top: `OWNER_EMAIL` (where digests go).
3. Save. The `doPost` already receives form posts (webhook wired in both sites).

### 1c. Enable time-driven triggers (3 clicks each)
Edit → **Current project's triggers** → **+ Add trigger**:
| Function        | Event source | Type            | Frequency        |
|-----------------|--------------|-----------------|------------------|
| `runNudges`     | Time-driven  | Day timer       | 7am–8am          |
| `sendDailyDigest`| Time-driven  | Day timer       | 8am–9am          |
| `sendWeeklyReport`| Time-driven | Week timer     | Monday, 9am–10am |

Authorize when Google prompts (Gmail + Sheets scopes).

### 1d. What happens automatically (Phase 1)
- **On submit:** row appended with **Lead Score** + **Priority** (High/Med/Low)
  + **Follow-up Date** auto-set (High +1d, Med +2d, Low +4d).
- **High/Medium lead:** instant personalized Gmail intro to the lead +
  🔥 alert to you. Low leads: logged, no email (you can change this).
- **+3 days no reply:** gentle nudge sent, Status → Contacted.
- **+7 days no reply:** Status → Cold.
- **Daily 8am:** digest email (new leads, high-priority count, pipeline $).
- **Monday:** weekly conversion report.

Scoring rules (in script, easy to tune):
Unlimited=90, Pro=82, Growth=80, Paid Report=75, Starter=60, Free Scan=40;
+ vendor-count bump for VC leads (≥50→+8, ≥20→+5, ≥5→+2). Caps at 100.

---

## PHASE 2 (Make.com / Zapier free + Calendly free) — wire next

Apps Script covers Day-1 + Day-3 nudges. For the full Day 1/3/7 sequence,
reply detection, and demo scheduling, use Make/Zapier:

1. **Trigger:** Google Sheets — new row (Status = New).
2. **Day 1:** already sent by `doPost` (skip duplicate in Make).
3. **Day 3 / Day 7:** Make/Zapier sends sequence emails (or rely on runNudges).
4. **Reply detection:** Gmail "new reply" → set Status = Contacted (Make
   writes back to the sheet row). When Status = Demo, Make sends a Calendly
   link via GmailApp.
5. **Calendly:** free account; Calendly webhook → on booked, set Status =
   Demo + send confirmation email.
Free tier: ~100 ops/month (enough for early leads).

Set `REPLY_DETECTION = true` in the script once Phase 2 is live.

---

## PHASE 3 (Stripe) — wire when ready

1. Stripe account (pay-as-you-go; no monthly fee).
2. Store secret key in **Script Properties** (NOT in code):
   script editor → Project Settings → Script Properties → `STRIPE_KEY`.
3. After demo (Status = Negotiating → Won): call `createStripeCheckout()`
   (stub in `google-apps-script.js`) to email a Checkout link.
4. Stripe webhook → on `checkout.session.completed` → send **welcome email
   + onboarding link**, set Status = Won. On decline/reject → log reason,
   Status = Lost.

---

## COMPLIANCE NOTE
Outbound emails include identification + opt-out ("reply unsubscribe").
Keep under Apps Script free quota (~100 sends/day). Only email leads who
opted in via the form (consent).

## FILES
- `google-apps-script.js` — full Code.gs (Phase 1 live + Phase 2/3 stubs).
- `leads-template.csv` — 14-col header + 2 sample rows (now includes Priority).
- Both sites' forms POST to the webhook (verified `{"result":"ok"}`).
