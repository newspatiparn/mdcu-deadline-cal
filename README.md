# MDCU Deadlines — ปฏิทินกำหนดส่งแบบกดติดตามครั้งเดียว

ปฏิทินรวมกำหนดส่งงานของรายวิชา เผยแพร่เป็น calendar feed (`deadlines.ics`) ที่นิสิตกดติดตาม**ครั้งเดียว**
แล้วกำหนดส่งใหม่ ๆ เด้งเข้าแอปปฏิทินที่มีอยู่แล้ว (Google / Apple / Outlook) พร้อมแจ้งเตือนของเครื่องเอง
— ไม่ต้องโหลดแอปเพิ่ม ไม่มีการเก็บข้อมูลผู้ใช้ใด ๆ

**🔗 กดติดตามได้ที่:** `https://USERNAME.github.io/REPO` *(แก้ลิงก์นี้หลังเปิด GitHub Pages แล้ว)*

---

## วิธีเพิ่ม deadline (สำหรับผู้ดูแล)

1. เปิดไฟล์ [`deadlines.yaml`](./deadlines.yaml)
2. copy บล็อกตัวอย่างที่มีอยู่ 1 บล็อก แล้วแก้ค่า (`id` ห้ามซ้ำ และ**ห้ามเปลี่ยนทีหลัง**)
3. `date:` รูปแบบ `YYYY-MM-DD` · `time:` ใส่ในเครื่องหมายคำพูด `"HH:MM"` (ไม่ใส่ = งาน all-day) · เวลาไทยเสมอ
4. commit + push ขึ้น branch `main`
5. จบ — GitHub Actions สร้างและปล่อยปฏิทินใหม่ให้เอง ผู้ติดตามได้อัปเดตอัตโนมัติ

## วิธีติดตามปฏิทิน (สำหรับนิสิต)

เปิดหน้า **`https://USERNAME.github.io/REPO`** แล้วกดปุ่มของแพลตฟอร์มตัวเอง
(iPhone/iPad/Mac · Google Calendar · Outlook) — มีขั้นตอนละเอียดบนหน้านั้นแล้ว

## How it works

```
deadlines.yaml (แก้มือ)  ──►  scripts/build_ics.py  ──►  GitHub Actions (push + cron รายวัน)
                                                              │  test → build → deploy
                                                              ▼
                                              GitHub Pages: index.html + deadlines.ics + qr.png
                                                              │
                                              นิสิตกดติดตามครั้งเดียว → ปฏิทิน + แจ้งเตือนในเครื่องเอง
```

แก้ YAML → push → ระบบ validate อย่างเข้มงวด (id ซ้ำ / วันที่ผิด = build ล้ม บอกทุกจุดที่ผิด) →
สร้างไฟล์ `.ics` ตาม RFC 5545 (UID คงที่ต่อรายการ — แก้รายละเอียดแล้ว event เดิมอัปเดตแทนที่ ไม่งอกซ้ำ) →
ปล่อยขึ้น Pages ด้วย official artifact flow (ไม่มี bot commit เข้า repo)

### Repo map

```
deadlines.yaml               # จุดเดียวที่ต้องแก้เป็นประจำ (source of truth)
config.yaml                  # ชื่อปฏิทิน / base_url / timezone / เวลาแจ้งเตือน
scripts/build_ics.py         # สคริปต์เดียวของระบบ: YAML → .ics + landing page + QR
site/index.template.html     # เทมเพลตหน้า landing (ภาษาไทย)
data/auto/                   # จุดเสียบ Phase 2 (ดูด้านล่าง) — ตอนนี้ว่าง
tests/test_build_ics.py      # pytest — รันอัตโนมัติทุก push ก่อน deploy
.github/workflows/build.yml  # test → build → deploy (Pages)
```

### Phase 2 plug-in (ยังไม่ทำ — เผื่ออนาคต)

`build_ics.py` อ่านทุกไฟล์ `data/auto/*.yaml` (schema เดียวกับ `deadlines.yaml`) รวมเข้า feed ให้อยู่แล้ว
ตัวดูดประกาศอัตโนมัติในอนาคต (อีเมล MS Graph / เว็บคณะ) แค่เขียนไฟล์ YAML ลงโฟลเดอร์นี้
โดย**ไม่ต้องแก้สคริปต์ build เลย** — ถ้า `id` ชนกันข้ามไฟล์ build จะล้มทันที (ตั้งใจให้แก้ชนด้วยมือ)
หมายเหตุ: LINE อ่านอัตโนมัติไม่ได้ (ทั้งกลุ่มปกติและ OpenChat) — การคีย์มือลง YAML เป็นส่วนถาวรของระบบ

## Handoff / ส่งต่อรุ่นน้อง

- เพิ่มรุ่นน้องเป็น collaborator (Settings → Collaborators) หรือโอน repo ให้เลย (Settings → Transfer)
- งานประจำมี**อย่างเดียว**: แก้ `deadlines.yaml` ตาม 5 ขั้นตอนข้างบน — ที่เหลือระบบทำเอง
- คนรับช่วงต้องมีแค่ git พื้นฐาน (clone / edit / commit / push)

## Troubleshooting

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| ปฏิทินหยุดอัปเดตทั้งที่ไม่ได้แตะอะไร | GitHub ปิด scheduled workflow อัตโนมัติเมื่อ repo ไม่มีความเคลื่อนไหว ~60 วัน → เข้า repo → แท็บ **Actions** → เลือก workflow → กด **Enable workflow** (คลิกเดียว) |
| ย้าย/เปลี่ยนชื่อ repo หรือแก้ `base_url` | แก้ `base_url` ใน `config.yaml` แล้ว push (หรือกด Run workflow) เพื่อ build ใหม่ — ลิงก์บนหน้า landing และ QR จะชี้ที่ใหม่ |
| push แล้ว Action แดง | เปิด log ของ job `test`/`build` — สคริปต์พิมพ์ทุกบรรทัดที่ผิดพร้อม `id` ที่มีปัญหา (ส่วนใหญ่คือ `id` ซ้ำ หรือ `time` ไม่ได้อยู่ในเครื่องหมายคำพูด) |
| นิสิตบอกปฏิทินไม่เด้งสักที | ปฏิทินแบบติดตามรีเฟรชช้า (Google ~วันละครั้ง) — เป็นพฤติกรรมปกติของ subscribed feed |

## Privacy

ปฏิทินนี้เป็น feed อ่านอย่างเดียว ผู้จัดทำไม่เห็นและไม่เก็บข้อมูลว่าใครติดตาม
ไม่มีบัญชี ไม่มีการล็อกอิน ไม่มี analytics — repo นี้เป็นสาธารณะและห้ามใส่ secret/ข้อมูลส่วนบุคคลทุกชนิด
