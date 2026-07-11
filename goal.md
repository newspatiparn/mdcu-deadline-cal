# GOAL — MDCU Deadline Calendar (subscribe-once ICS feed)

> **Executor instructions:** Read this ENTIRE file before writing any code. Build exactly what is
> specified — nothing more. If anything is ambiguous, or you want to add a dependency/feature/file
> not listed here, STOP and ask first. Spec is written in English for precision;
> **all user-facing text must be Thai** (marked where relevant).

---

## 1. What we are building

A zero-cost system that publishes **one subscribable calendar feed** (`deadlines.ics`) of course
deadlines for medical students.

- Deadlines live in **one hand-edited YAML file** in this repo.
- **GitHub Actions** rebuilds the feed on every push and on a daily cron.
- **GitHub Pages** serves the feed + a small Thai landing page with subscribe buttons and a QR code.
- Students subscribe **once**; events then appear in the calendar app they already have
  (Google / Apple / Outlook) and their phone reminds them natively.
- **We collect no user data.** No accounts, no forms, no cookies, no analytics.
  Subscribers are anonymous to us. This is a deliberate design constraint, not an omission.

**Non-goals (v1):** no web UI for editing, no user accounts, no database, no notifications we send
ourselves, no LINE integration (impossible — see §2), no Microsoft Graph puller, no web scraper.

---

## 2. Context & hard constraints (do not violate)

1. Deadline announcements arrive via **LINE groups, the faculty website, and university email
   (Microsoft 365)**. LINE (both normal groups and OpenChat) **cannot be read programmatically** —
   manual YAML entry is a permanent, accepted part of the design. **Never attempt LINE integration.**
2. Automated pullers (MS Graph for email, website scraper) are **Phase 2 — out of scope**.
   Design the build script so pullers can plug in later (see §9), but do not implement them.
3. **Maintainability > cleverness.** A junior med student with basic git skills must be able to
   run and hand this over. Prefer boring, obvious code. No frameworks, no JS build tooling, no Docker.
4. Local dev happens on **Windows 11**; CI runs on `ubuntu-latest`. Code must be OS-agnostic:
   use `pathlib`, pass `encoding="utf-8"` on **every** text file open/read/write
   (Thai text + Windows default codepage = real mojibake risk), no shell-specific calls in Python.
5. Timezone is **Asia/Bangkok (UTC+7, no DST)** everywhere.
6. Repo will be **public** (required for free Pages + eases handoff). Therefore:
   **never** put tokens/secrets/personal data in the repo. Phase 2 pullers will use GitHub Secrets.
7. Allowed dependencies ONLY: `PyYAML`, `icalendar`, `qrcode[pil]`, `pytest` (dev).
   Python 3.11+. Ask before adding anything else.

---

## 3. Architecture (fixed — do not redesign)

```
deadlines.yaml  (single source of truth, hand-edited)
      │
      ▼
scripts/build_ics.py            (YAML → RFC 5545 .ics + render landing page + QR)
      │
      ▼
GitHub Actions                  (on: push + daily cron + manual dispatch)
      │  test → build → deploy (official Pages artifact flow, no bot commits)
      ▼
GitHub Pages                    (serves /index.html + /deadlines.ics + /qr.png)
      │
      ▼
Students subscribe ONCE via URL → native calendar + native reminders
```

---

## 4. Repository layout (create exactly this)

```
/
├── deadlines.yaml               # manual deadline entries (Thai header comments for maintainers)
├── config.yaml                  # base_url, calendar name, timezone, alarm lead, uid domain
├── scripts/
│   └── build_ics.py             # the only script
├── site/
│   └── index.template.html      # landing page template (Thai), tokens filled at build time
├── data/
│   └── auto/                    # Phase 2 pullers will write YAML here; keep .gitkeep
├── tests/
│   └── test_build_ics.py
├── .github/workflows/build.yml
├── requirements.txt
├── .gitignore                   # _site/, __pycache__/, .venv/
└── README.md
```

---

## 5. `config.yaml`

```yaml
calendar_name: "MDCU Deadlines"
base_url: "https://USERNAME.github.io/REPO"   # user fills after enabling Pages
timezone: "Asia/Bangkok"
uid_domain: "mdcu-deadline-cal"               # UID suffix; never change after launch
alarm_lead_hours: 24                          # VALARM lead time
keep_past_days: 60                            # drop events older than this from the feed
```

---

## 6. `deadlines.yaml` — schema + seed data

Top of file must carry Thai maintainer comments (this file IS the maintainer UI):

```yaml
# ─── วิธีเพิ่ม deadline ───────────────────────────────────────────
# 1) copy บล็อกตัวอย่างด้านล่าง  2) แก้ค่า  3) commit + push — จบ ระบบทำที่เหลือเอง
# กติกา:
#   id:   ห้ามซ้ำ และ "ห้ามเปลี่ยนทีหลัง" (เปลี่ยนแล้วคนที่ติดตามจะเห็น event เก่าซ้ำ/ค้าง)
#   date: รูปแบบ YYYY-MM-DD    time: "HH:MM" (ไม่ใส่ = งาน all-day ทั้งวัน)
#   เวลาเป็นเวลาไทย (Asia/Bangkok) เสมอ
# ──────────────────────────────────────────────────────────────────

- id: 3050202-topic
  course: "3050202"
  title: "แจ้งหัวข้อกิจกรรมที่สนใจ"
  date: 2026-08-03
  time: "08:00"
  source: "ประกาศรายวิชา"
  url: ""
  notes: "แจ้งผ่านช่องทางที่รายวิชาประกาศ เพื่อไม่ให้ซ้ำกับกลุ่มอื่น"

- id: 3050202-proposal
  course: "3050202"
  title: "ส่ง proposal โครงการ (mentor ต้องเห็นชอบแล้ว)"
  date: 2026-08-13
  time: "08:00"
  source: "ประกาศรายวิชา"
  url: ""
  notes: "มี template ให้"

- id: 3050202-report
  course: "3050202"
  title: "ส่ง Project report (evaluation + reflection + AAR)"
  date: 2026-11-20
  time: "08:00"
  source: "ประกาศรายวิชา"
  url: ""
  notes: ""

- id: 3050202-poster
  course: "3050202"
  title: "ส่ง poster ประกอบการนำเสนอนิทรรศการ"
  date: 2026-11-30
  time: "08:00"
  source: "ประกาศรายวิชา"
  url: ""
  notes: ""

- id: 203-69-cap-exhibition
  course: "203-69"
  title: "CAP exhibition นำเสนอผลงาน (รอยืนยัน)"
  date: 2027-01-12
  source: "ประกาศรายวิชา"
  url: ""
  notes: "ช่วงเช้า ใต้ตึกอานันทมหิดล — to be confirmed"
```

Required fields: `id`, `title`, `date`. Optional: `course`, `time`, `source`, `url`, `notes`.

---

## 7. `scripts/build_ics.py`

CLI: `python scripts/build_ics.py --config config.yaml --out _site`

Behavior:

1. Read `config.yaml`, `deadlines.yaml`, and every `data/auto/*.yaml` (same schema) if present.
2. **Validate hard, fail loud.** On any problem, print ALL errors (one line each, human-readable,
   include the offending `id` or file/position) and `sys.exit(1)`. Check at minimum:
   missing required fields, unparseable date/time, duplicate `id` across ALL files,
   `time` without valid `HH:MM` format.
3. Drop events older than `keep_past_days`.
4. Write `_site/deadlines.ics`, `_site/qr.png`, `_site/index.html`.

### ICS requirements (RFC 5545)

- `VCALENDAR`: `VERSION:2.0`, `PRODID`, `CALSCALE:GREGORIAN`, `METHOD:PUBLISH`,
  `X-WR-CALNAME` (from config), `X-WR-TIMEZONE:Asia/Bangkok`,
  `REFRESH-INTERVAL;VALUE=DURATION:PT12H` and `X-PUBLISHED-TTL:PT12H`.
- Include a correct static `VTIMEZONE` block for Asia/Bangkok (fixed +07:00, no DST).
- Per `VEVENT`:
  - `UID` = `{id}@{uid_domain}` — **deterministic and stable**. Editing an entry's details must
    keep the same UID so subscribed clients update in place instead of duplicating.
  - `SUMMARY` = `[{course}] {title}` when course present, else `{title}`.
  - Timed entry → `DTSTART;TZID=Asia/Bangkok`, `DTEND` = start + 30 min.
  - No `time` → all-day: `DTSTART;VALUE=DATE`, `DTEND;VALUE=DATE` = next day.
  - `DESCRIPTION` = notes + source + url (skip empty parts).
  - `DTSTAMP` = build time (UTC). Fine that it changes per build.
  - One `VALARM` (DISPLAY, `-PT{alarm_lead_hours}H`). Add a code comment: many clients ignore
    alarms on *subscribed* feeds — the landing page tells users to set default reminders.
- Serialize with the `icalendar` library; write **bytes** (it emits CRLF per RFC — do not mangle).

### Landing page rendering

Render `site/index.template.html` → `_site/index.html` by plain `str.replace` of tokens
(no template engine): `{{CAL_NAME}}`, `{{ICS_URL}}`, `{{WEBCAL_URL}}`, `{{GOOGLE_ADD_URL}}`,
`{{UPDATED_AT}}` (Thai-formatted Bangkok time), `{{UPCOMING_ROWS}}` (next 10 upcoming events as
table rows: วันที่ / เวลา / รายการ). After rendering, no `{{` may remain (test this).

- `ICS_URL` = `{base_url}/deadlines.ics`
- `WEBCAL_URL` = same but scheme `webcal://` (strip `https://`)
- `GOOGLE_ADD_URL` = `https://calendar.google.com/calendar/r?cid={url-encoded WEBCAL_URL}`

### QR

Generate `_site/qr.png` encoding **the landing page URL** (`base_url`) — not the ics directly —
so one QR works for every platform. Use `qrcode[pil]`, sensible size (~512 px).

---

## 8. `site/index.template.html` — landing page (Thai, mobile-first, ZERO JavaScript)

Single self-contained HTML file, inline CSS, no external assets except `qr.png`. Must contain:

1. **Header:** calendar name + one-line pitch —「กดติดตามครั้งเดียว ทุกกำหนดส่งเด้งเข้าปฏิทินมือถือ
   พร้อมแจ้งเตือนอัตโนมัติ — ไม่ต้องโหลดแอปเพิ่ม」
2. **Subscribe buttons (big, thumb-friendly):**
   - iPhone / iPad / Mac → `{{WEBCAL_URL}}` (opens native subscribe dialog)
   - Google Calendar (Android) → `{{GOOGLE_ADD_URL}}`
   - Outlook → collapsible `<details>` with short manual steps (Add calendar → Subscribe from web)
   - A visible copyable raw URL line showing `{{ICS_URL}}`
3. **How-to:** 2–3 bullet steps per platform inside `<details>` accordions.
4. **Upcoming deadlines table:** `{{UPCOMING_ROWS}}` — so the page is useful even without subscribing.
5. **Expectation note (must include, Thai):** Google Calendar refreshes subscribed feeds roughly
   once a day — เหมาะกับ deadline ที่รู้ล่วงหน้า ไม่เหมาะกับประกาศด่วนรายชั่วโมง; และแนะนำให้ผู้ใช้
   ตั้ง default reminder ของปฏิทินตัวเองด้วย เพราะบางแอปไม่รับการแจ้งเตือนที่ฝังมากับ feed.
6. **Privacy note (must include, Thai):**「ปฏิทินนี้เป็น feed อ่านอย่างเดียว ผู้จัดทำไม่เห็นและ
   ไม่เก็บข้อมูลว่าใครติดตาม ไม่มีบัญชี ไม่มีการล็อกอิน ไม่มี analytics」
7. **Footer:** `{{UPDATED_AT}}` + link to the GitHub repo.

Design: clean, generous whitespace, system Thai fonts stack
(`'Noto Sans Thai','Sarabun',system-ui,sans-serif`), one accent color, looks fine on a phone.

---

## 9. Phase 2 plug-in rule (build now, use later)

`build_ics.py` already merges `data/auto/*.yaml` (same schema as `deadlines.yaml`).
Future pullers (MS Graph, website scraper) simply write YAML files there — zero changes to the
build script. Duplicate `id` across any files = build error (keep conflict resolution manual).
Create `data/auto/.gitkeep` and one short paragraph in README explaining this. **Do not implement
any puller.**

---

## 10. `.github/workflows/build.yml`

```yaml
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 22 * * *"      # 05:00 Asia/Bangkok (cron is UTC)
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write
```

Jobs:
1. **test** — checkout, setup Python 3.12, `pip install -r requirements.txt`, `pytest -q`.
2. **build** (needs: test) — run `build_ics.py --out _site`, `actions/upload-pages-artifact` on `_site`.
3. **deploy** (needs: build) — `actions/deploy-pages` (official flow; **no bot commits to the repo**).

---

## 11. Tests — `tests/test_build_ics.py` (pytest, fast, no network)

Use tmp dirs + a small fixture YAML. Cover at minimum:

1. Build succeeds on seed-style data; output `.ics` re-parses with `icalendar`; event count correct.
2. **UID stability:** two consecutive builds → identical UID set.
3. Timed entry encodes `TZID=Asia/Bangkok` + correct local time; all-day entry encodes `VALUE=DATE`.
4. Thai text survives round-trip (parse output, compare SUMMARY equals input string).
5. Duplicate `id` → `SystemExit` non-zero; missing `date` → `SystemExit` non-zero.
6. Rendered `index.html` contains no `{{` after token replacement.

---

## 12. `README.md` (bilingual: Thai for maintainers/users, English OK for technical bits)

Must contain:
1. What this is (3 lines) + subscribe link placeholder.
2. **วิธีเพิ่ม deadline (สำหรับผู้ดูแล)** — max 5 steps, mirrors the YAML header comments.
3. วิธีติดตามปฏิทิน (ลิงก์ไปหน้า landing page).
4. How it works (one diagram/paragraph) + repo map.
5. **Handoff / ส่งต่อรุ่นน้อง:** add collaborator or transfer repo; the ONLY recurring duty is
   editing `deadlines.yaml`.
6. **Troubleshooting:** incl. — GitHub disables scheduled workflows after ~60 days without repo
   activity → fix: repo → Actions → enable workflow (one click); and: changed `base_url`? re-run build.
7. Privacy statement (same as landing page).

---

## 13. Working agreement (how to execute)

- Order: config + schemas → `build_ics.py` **with tests first (TDD-lite)** → template/render →
  workflow → README. Small, meaningful commits.
- Run `pytest -q` and a full local build before declaring done.
- Do not touch anything outside the layout in §4.

## 14. Definition of Done — self-verify every box

- [ ] `pytest -q` green.
- [ ] `python scripts/build_ics.py --config config.yaml --out _site` produces
      `deadlines.ics`, `index.html`, `qr.png`.
- [ ] `deadlines.ics` re-parses with `icalendar`; contains the 5 seed events; CRLF line endings.
- [ ] `index.html`: no leftover `{{tokens}}`; contains privacy note + expectation note + upcoming table.
- [ ] Workflow YAML is valid; uses the official Pages artifact flow; cron comment shows Bangkok time.
- [ ] README complete per §12. No secrets anywhere in the repo.

## 15. Final message to the user (print after DoD passes)

Tell the user these exact remaining manual steps, in Thai:
1. สร้าง GitHub repo สาธารณะ (แนะนำชื่อ `mdcu-deadline-cal`) แล้ว push โค้ดขึ้นไป
2. Repo → Settings → Pages → Source = **GitHub Actions**
3. แก้ `base_url` ใน `config.yaml` เป็น URL จริงของ Pages แล้ว push อีกครั้ง
4. รอ Action เขียวแล้วเปิด `base_url` — ทดสอบกดติดตามด้วยมือถือตัวเอง 1 เครื่อง
5. แชร์ URL / QR ให้เพื่อน — จบ
