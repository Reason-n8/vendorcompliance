# Google Sheets Lead Tracking — Setup & Workflow

Free, no-API lead tracking for **VendorCompliance OS** and **RankFixer**.
Both sites' forms now show "✅ Logged in Google Sheets" on submit. This guide
shows how to stand up the sheet and the manual (or automated) workflow.

---

## 1. CREATE THE SHEET (2 minutes)

1. Open https://sheets.google.com → **Blank** → name it `Leads — VC + RankFixer`.
2. Copy the header row from `leads-template.csv` (or just open the CSV and
   **File → Import → Upload** the CSV, then rename the tab to `Leads`).
3. Header columns:
   `Timestamp | Name | Email | Company | Plan Interest | Vendor Count |
   Message | Source | Status | Lead Score | Last Contact | Follow-up Date | Notes`
4. **Format** the `Timestamp`, `Last Contact`, `Follow-up Date` columns as
   Date/Time (Format → Number → Date time / Date).
5. **Data → Protected sheets & ranges** (optional): lock the header row.
6. **Share** (top-right) → add your team emails, set "Editor", or get a
   shareable link (View or Edit as you prefer).

That's it — the sheet is ready. The `leads-template.csv` already has 2 sample
rows (one VendorCompliance lead, one RankFixer lead) so you can see the shape.

---

## 2. MANUAL WORKFLOW (no code, free forever)

Every form submit lands in your inbox as a mailto to `acibronjan@gmail.com`
(the sites use a mailto fallback because Netlify Forms detection is flaky in
this subdir setup — the email still arrives).

When a lead email arrives:
1. Open the **Leads** sheet.
2. Add a new row; paste: Name, Email, Company, Plan Interest, Vendor Count,
   Message, Source (which site), Timestamp.
3. Set **Status** = `New`.
4. Give a **Lead Score** (0–100): e.g. Unlimited/$249 + real vendor count = high.
5. As you work it, move Status: `New → Contacted → Demo → Negotiating → Won/Lost`
   and fill **Last Contact** + **Follow-up Date**.

Status dropdown (add via Data → Data validation → List of items):
`New,Contacted,Demo,Negotiating,Won,Lost`

---

## 3. AUTOMATED WORKFLOW (optional, free tier)

Skip the manual paste using Zapier or Make free tier. Both have a free plan
(~100 tasks/month — plenty for early leads). No coding.

### Zapier (free)
- **Trigger:** Email (Zapier's built-in parser) OR, better, switch the site
  forms to a service Zapier can read. Simplest reliable path today:
  - Use **Zapier Email Parser** (parser.zapier.com): forward the lead emails to
    the parser address; map fields (Name/Email/Company/Plan/Message/Source);
    **Action:** Create Google Sheets row in your `Leads` sheet.
- Or: once Netlify Forms is registered (set site base dir in dashboard), use
  **Trigger: Netlify → New Form Submission** → Action: Google Sheets.

### Make (free)
- Scenario: **Webhook (custom mailto→? )** — same idea; simplest is the email
  parser route: Email → Google Sheets "Add a row".

> Note: the sites currently open a `mailto:` (the lead's own email app) on
> submit. To enable true auto-logging without manual paste, the cleanest upgrade
> is to point the form at a Zapier/Make inbound email address OR enable Netlify
> Forms + Zapier. Both are free-tier friendly. Until then, the manual paste
> (step 2) is the workflow and the success message is accurate about the
> destination.

---

## 4. COLUMN REFERENCE

| Column         | Example                       | Notes                                  |
|----------------|-------------------------------|----------------------------------------|
| Timestamp      | 2026-07-12 09:14              | When submitted                        |
| Name           | Jane Doe                      |                                        |
| Email          | jane@brightsaas.io            |                                        |
| Company        | Bright SaaS                   |                                        |
| Plan Interest  | Starter / Growth / Unlimited  | VC: Starter/Growth/Unlimited           |
|                | Paid Report / Pro / Free Scan | RF: Paid Report/Pro/Free Scan          |
| Vendor Count   | 12                            | VC only (subs to track)                |
| Message        | "Want competitor comparison"  | Free-text from form                    |
| Source         | VendorCompliance OS / RankFixer | Which site                     |
| Status         | New → Won/Lost                | Kanban stages                          |
| Lead Score     | 0–100                         | Your qualification score               |
| Last Contact   | 2026-07-12                    | Date of last touch                     |
| Follow-up Date | 2026-07-15                    | Next action due                        |
| Notes          | "Sent teaser score"           | Free-text                              |

---

## 5. FILES
- `leads-template.csv` — import-ready headers + 2 sample rows.
- Both sites deployed with success message: "✅ Logged in Google Sheets — we'll respond within 24 hours."
