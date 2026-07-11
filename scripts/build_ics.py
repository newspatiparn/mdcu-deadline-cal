"""Build the MDCU deadline calendar.

Reads deadlines.yaml (+ every data/auto/*.yaml, same schema) and writes:
    _site/deadlines.ics   subscribable calendar feed (RFC 5545)
    _site/index.html      Thai landing page rendered from site/index.template.html
    _site/qr.png          QR code pointing at the landing page

Run:  python scripts/build_ics.py --config config.yaml --out _site
"""

import argparse
import html
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import qrcode
import yaml
from icalendar import Alarm, Calendar, Event, Timezone, TimezoneStandard

# Asia/Bangkok is a fixed UTC+7 with no DST, so a constant offset is enough.
# (No zoneinfo on purpose: Windows has no system tz database and tzdata is not
# an allowed dependency.)
BANGKOK_TZ = timezone(timedelta(hours=7))

THAI_MONTHS = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]


def parse_date(value):
    """Accept a datetime.date (unquoted YAML date) or a 'YYYY-MM-DD' string."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    raise ValueError(f"expected YYYY-MM-DD, got {value!r}")


def parse_time(value):
    """Accept an 'HH:MM' string; None means all-day.

    Unquoted 08:00 in YAML arrives as the integer 480 (base-60 int), which is
    why deadlines.yaml tells maintainers to keep time in quotes.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.strptime(value.strip(), "%H:%M").time()
    raise ValueError(f'expected "HH:MM" in quotes, got {value!r}')


def format_thai_date(d):
    return f"{d.day} {THAI_MONTHS[d.month]} {d.year + 543}"


def format_thai_datetime(dt):
    return f"{format_thai_date(dt)} เวลา {dt.strftime('%H:%M')} น. (เวลาไทย)"


def load_entries(root):
    """Read deadlines.yaml plus every data/auto/*.yaml (Phase 2 pullers drop
    files there — same schema, zero build-script changes)."""
    files = [root / "deadlines.yaml"]
    auto_dir = root / "data" / "auto"
    if auto_dir.is_dir():
        files.extend(sorted(auto_dir.glob("*.yaml")))

    entries = []
    for path in files:
        if not path.is_file():
            continue
        items = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(items, list):
            entries.append({"_file": path.name, "_position": 0,
                            "_broken": "file is not a YAML list of entries"})
            continue
        for position, item in enumerate(items, start=1):
            entry = dict(item) if isinstance(item, dict) else {
                "_broken": f"entry is not a mapping: {item!r}"}
            entry["_file"] = path.name
            entry["_position"] = position
            entries.append(entry)
    return entries


def validate(entries):
    """Return a list of human-readable error lines (empty list = all good)."""
    errors = []
    seen_ids = {}
    for entry in entries:
        where = f"{entry['_file']} entry #{entry['_position']}"
        if "_broken" in entry:
            errors.append(f"{where}: {entry['_broken']}")
            continue

        entry_id = str(entry.get("id") or "").strip()
        if not entry_id:
            errors.append(f"{where}: missing required field 'id'")
        elif entry_id in seen_ids:
            errors.append(f"{where}: duplicate id '{entry_id}' "
                          f"(first seen in {seen_ids[entry_id]})")
        else:
            seen_ids[entry_id] = where

        label = f"{where} (id: {entry_id or '?'})"
        if not str(entry.get("title") or "").strip():
            errors.append(f"{label}: missing required field 'title'")

        if entry.get("date") is None:
            errors.append(f"{label}: missing required field 'date'")
        else:
            try:
                parse_date(entry["date"])
            except (ValueError, TypeError):
                errors.append(f"{label}: invalid date {entry['date']!r} "
                              f"(expected YYYY-MM-DD)")

        if entry.get("time") is not None:
            try:
                parse_time(entry["time"])
            except (ValueError, TypeError):
                errors.append(f"{label}: invalid time {entry['time']!r} "
                              f'(write it as "HH:MM" in quotes)')
    return errors


def _bangkok_vtimezone():
    """Static VTIMEZONE: Bangkok has been UTC+7 with no DST transitions."""
    tz = Timezone()
    tz.add("tzid", "Asia/Bangkok")
    standard = TimezoneStandard()
    standard.add("dtstart", datetime(1970, 1, 1, 0, 0, 0))
    standard.add("tzoffsetfrom", timedelta(hours=7))
    standard.add("tzoffsetto", timedelta(hours=7))
    standard.add("tzname", "ICT")
    tz.add_component(standard)
    return tz


def build_calendar(entries, config, now_bkk):
    cal = Calendar()
    cal.add("version", "2.0")
    cal.add("prodid", "-//mdcu-deadline-cal//build_ics//TH")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", config["calendar_name"])
    cal.add("x-wr-timezone", "Asia/Bangkok")
    # RFC 7986 refresh hints; clients may still use their own schedule.
    cal["REFRESH-INTERVAL;VALUE=DURATION"] = "PT12H"
    cal["X-PUBLISHED-TTL"] = "PT12H"
    cal.add_component(_bangkok_vtimezone())

    uid_domain = config.get("uid_domain", "mdcu-deadline-cal")
    alarm_lead_hours = int(config.get("alarm_lead_hours", 24))

    for entry in entries:
        entry_id = str(entry["id"]).strip()
        title = str(entry["title"]).strip()
        course = str(entry.get("course") or "").strip()
        summary = f"[{course}] {title}" if course else title

        event = Event()
        # UID derives from id ONLY — stable across edits, so subscribed
        # clients update the event in place instead of duplicating it.
        event.add("uid", f"{entry_id}@{uid_domain}")
        event.add("summary", summary)

        start_date = parse_date(entry["date"])
        start_time = parse_time(entry.get("time"))
        if start_time is None:
            # All-day event: DTEND is the NEXT day (RFC 5545 exclusive end).
            event.add("dtstart", start_date)
            event.add("dtend", start_date + timedelta(days=1))
        else:
            start = datetime.combine(start_date, start_time)  # naive Bangkok wall time
            event.add("dtstart", start, parameters={"TZID": "Asia/Bangkok"})
            event.add("dtend", start + timedelta(minutes=30),
                      parameters={"TZID": "Asia/Bangkok"})

        parts = []
        notes = str(entry.get("notes") or "").strip()
        source = str(entry.get("source") or "").strip()
        url = str(entry.get("url") or "").strip()
        if notes:
            parts.append(notes)
        if source:
            parts.append(f"ที่มา: {source}")
        if url:
            parts.append(url)
        if parts:
            event.add("description", "\n".join(parts))

        event.add("dtstamp", now_bkk.astimezone(timezone.utc))

        # One display alarm. Many calendar apps IGNORE alarms embedded in
        # subscribed feeds — the landing page tells users to also set their
        # own default reminder, which is why this is best-effort only.
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", summary)
        alarm["TRIGGER"] = f"-PT{alarm_lead_hours}H"
        event.add_component(alarm)

        cal.add_component(event)
    return cal


def render_page(template, entries, config, now_bkk):
    now_local = now_bkk.replace(tzinfo=None)  # Bangkok wall-clock time
    today = now_local.date()

    upcoming = []
    for entry in entries:
        start_date = parse_date(entry["date"])
        start_time = parse_time(entry.get("time"))
        if start_time is None:
            if start_date < today:  # all-day counts as upcoming its whole day
                continue
            sort_key = datetime.combine(start_date, datetime.min.time())
        else:
            sort_key = datetime.combine(start_date, start_time)
            if sort_key < now_local:
                continue
        upcoming.append((sort_key, start_date, start_time, entry))
    upcoming.sort(key=lambda item: item[0])

    rows = []
    for _, start_date, start_time, entry in upcoming[:10]:
        course = str(entry.get("course") or "").strip()
        title = str(entry.get("title") or "").strip()
        summary = f"[{course}] {title}" if course else title
        when = "ทั้งวัน" if start_time is None else f"{start_time.strftime('%H:%M')} น."
        rows.append(f"<tr><td>{html.escape(format_thai_date(start_date))}</td>"
                    f"<td>{html.escape(when)}</td>"
                    f"<td>{html.escape(summary)}</td></tr>")
    if not rows:
        rows.append('<tr><td colspan="3">ยังไม่มีกำหนดส่งที่กำลังจะถึง</td></tr>')

    base_url = config["base_url"].rstrip("/")
    ics_url = f"{base_url}/deadlines.ics"
    if ics_url.startswith("https://"):
        webcal_url = "webcal://" + ics_url[len("https://"):]
    elif ics_url.startswith("http://"):
        webcal_url = "webcal://" + ics_url[len("http://"):]
    else:
        webcal_url = ics_url
    google_add_url = ("https://calendar.google.com/calendar/r?cid="
                      + urllib.parse.quote(webcal_url, safe=""))

    # Footer repo link: derive github.com/<user>/<repo> from a Pages URL.
    repo_url = base_url
    host_path = base_url.split("://", 1)[-1].split("/")
    if len(host_path) == 2 and host_path[0].endswith(".github.io"):
        user = host_path[0][:-len(".github.io")]
        repo_url = f"https://github.com/{user}/{host_path[1]}"

    page = template
    page = page.replace("{{CAL_NAME}}", config["calendar_name"])
    page = page.replace("{{ICS_URL}}", ics_url)
    page = page.replace("{{WEBCAL_URL}}", webcal_url)
    page = page.replace("{{GOOGLE_ADD_URL}}", google_add_url)
    page = page.replace("{{UPDATED_AT}}", format_thai_datetime(now_local))
    page = page.replace("{{UPCOMING_ROWS}}", "\n".join(rows))
    page = page.replace("{{REPO_URL}}", repo_url)
    return page


def make_qr(url, path):
    qr = qrcode.QRCode(box_size=16, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build deadlines.ics + Thai landing page + QR code")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default="_site")
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve()
    root = config_path.parent  # repo root = the folder holding config.yaml
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    entries = load_entries(root)
    errors = validate(entries)
    if errors:
        for line in errors:
            print(f"ERROR: {line}", file=sys.stderr)
        sys.exit(1)

    now_bkk = datetime.now(timezone.utc).astimezone(BANGKOK_TZ)
    cutoff = now_bkk.date() - timedelta(days=int(config.get("keep_past_days", 60)))
    entries = [e for e in entries if parse_date(e["date"]) >= cutoff]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = build_calendar(entries, config, now_bkk)
    # to_ical() emits CRLF line endings as RFC 5545 requires — write the raw
    # bytes, never decode/re-join them.
    (out_dir / "deadlines.ics").write_bytes(cal.to_ical())

    template = (root / "site" / "index.template.html").read_text(encoding="utf-8")
    page = render_page(template, entries, config, now_bkk)
    if "{{" in page:
        print("ERROR: template token left unreplaced in index.html", file=sys.stderr)
        sys.exit(1)
    (out_dir / "index.html").write_text(page, encoding="utf-8")

    make_qr(config["base_url"], out_dir / "qr.png")
    print(f"OK: {len(entries)} events -> {out_dir}")


if __name__ == "__main__":
    main()
