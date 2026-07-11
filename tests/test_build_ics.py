import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from icalendar import Calendar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_ics  # noqa: E402

NOW_BKK = datetime(2099, 8, 1, 12, 0, 0, tzinfo=build_ics.BANGKOK_TZ)

CONFIG = {
    "calendar_name": "Test Deadlines",
    "base_url": "https://tester.github.io/test-repo",
    "timezone": "Asia/Bangkok",
    "uid_domain": "test-domain",
    "alarm_lead_hours": 24,
    "keep_past_days": 60,
}

# Far-future seed-style data so keep_past_days never drops anything,
# no matter when the tests run.
SEED_ENTRIES = [
    {"id": "3050202-topic", "course": "3050202", "title": "แจ้งหัวข้อกิจกรรมที่สนใจ",
     "date": "2099-08-03", "time": "08:00", "source": "ประกาศรายวิชา", "url": "", "notes": ""},
    {"id": "3050202-proposal", "course": "3050202", "title": "ส่ง proposal โครงการ",
     "date": "2099-08-13", "time": "08:00", "source": "ประกาศรายวิชา", "url": "", "notes": ""},
    {"id": "3050202-report", "course": "3050202", "title": "ส่ง Project report",
     "date": "2099-11-20", "time": "08:00", "source": "ประกาศรายวิชา", "url": "", "notes": ""},
    {"id": "3050202-poster", "course": "3050202", "title": "ส่ง poster",
     "date": "2099-11-30", "time": "08:00", "source": "ประกาศรายวิชา", "url": "", "notes": ""},
    # no "time" -> exercises the all-day path
    {"id": "203-69-cap-exhibition", "course": "203-69", "title": "CAP exhibition นำเสนอผลงาน",
     "date": "2100-01-12", "source": "ประกาศรายวิชา", "url": "", "notes": "ช่วงเช้า"},
]

TEMPLATE = """<!DOCTYPE html><html lang="th"><body>
<h1>{{CAL_NAME}}</h1><p>{{ICS_URL}}</p><p>{{WEBCAL_URL}}</p>
<p>{{GOOGLE_ADD_URL}}</p><p>{{UPDATED_AT}}</p>
<table>{{UPCOMING_ROWS}}</table><a href="{{REPO_URL}}">repo</a>
</body></html>"""


def make_repo(tmp_path, entries):
    """Lay out a minimal repo (config + deadlines + template) under tmp_path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    (tmp_path / "deadlines.yaml").write_text(
        yaml.safe_dump(entries, allow_unicode=True), encoding="utf-8")
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.template.html").write_text(TEMPLATE, encoding="utf-8")
    return tmp_path


def run_build(tmp_path):
    build_ics.main(["--config", str(tmp_path / "config.yaml"),
                    "--out", str(tmp_path / "_site")])
    return tmp_path / "_site"


def test_build_succeeds_on_seed_style_data(tmp_path):
    out = run_build(make_repo(tmp_path, SEED_ENTRIES))

    for name in ("deadlines.ics", "index.html", "qr.png"):
        assert (out / name).is_file()

    ics = (out / "deadlines.ics").read_bytes()
    assert b"\r\n" in ics  # RFC 5545 CRLF line endings
    parsed = Calendar.from_ical(ics)
    assert len(parsed.walk("vevent")) == len(SEED_ENTRIES)


def test_uid_set_is_stable_across_builds():
    cal1 = build_ics.build_calendar(SEED_ENTRIES, CONFIG, NOW_BKK)
    cal2 = build_ics.build_calendar(SEED_ENTRIES, CONFIG, NOW_BKK)
    uids1 = sorted(str(e["uid"]) for e in cal1.walk("vevent"))
    uids2 = sorted(str(e["uid"]) for e in cal2.walk("vevent"))
    assert uids1 == uids2
    assert "3050202-topic@test-domain" in uids1


def test_timed_has_bangkok_tzid_and_allday_has_value_date():
    entries = [
        {"id": "timed-1", "title": "Timed", "date": "2099-08-03", "time": "08:00"},
        {"id": "allday-1", "title": "All day", "date": "2099-08-04"},
    ]
    ics = build_ics.build_calendar(entries, CONFIG, NOW_BKK).to_ical()
    assert b"DTSTART;TZID=Asia/Bangkok:20990803T080000" in ics
    assert b"DTEND;TZID=Asia/Bangkok:20990803T083000" in ics  # start + 30 min
    assert b"DTSTART;VALUE=DATE:20990804" in ics
    assert b"DTEND;VALUE=DATE:20990805" in ics  # exclusive next day


def test_thai_summary_survives_roundtrip():
    thai_title = "แจ้งหัวข้อกิจกรรมที่สนใจ"
    entries = [{"id": "thai-1", "title": thai_title, "date": "2099-08-03"}]
    cal = build_ics.build_calendar(entries, CONFIG, NOW_BKK)
    parsed = Calendar.from_ical(cal.to_ical())
    assert str(parsed.walk("vevent")[0]["summary"]) == thai_title


def test_duplicate_id_and_missing_date_exit_nonzero(tmp_path):
    dup = [
        {"id": "dup", "title": "A", "date": "2099-08-03"},
        {"id": "dup", "title": "B", "date": "2099-08-04"},
    ]
    repo1 = make_repo(tmp_path / "dup", dup)
    with pytest.raises(SystemExit) as excinfo:
        run_build(repo1)
    assert excinfo.value.code != 0

    missing = [{"id": "no-date", "title": "No date"}]
    repo2 = make_repo(tmp_path / "missing", missing)
    with pytest.raises(SystemExit) as excinfo:
        run_build(repo2)
    assert excinfo.value.code != 0


def test_rendered_index_has_no_leftover_tokens(tmp_path):
    out = run_build(make_repo(tmp_path, SEED_ENTRIES))
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "{{" not in page
    assert "Test Deadlines" in page
    assert "https://tester.github.io/test-repo/deadlines.ics" in page
    assert "webcal://tester.github.io/test-repo/deadlines.ics" in page
    assert "https://github.com/tester/test-repo" in page
