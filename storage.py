# -*- coding: utf-8 -*-
"""
OZI — хранилище лидов, профилей родителей, событий.
ГЛАВНОЕ: если настроен Google Sheets — пишем ТУДА (данные не теряются при рестарте Render).
Иначе — локальные JSONL (запасной вариант, данные живут только до перезапуска).
Регуляторная граница: по ребёнку — только год рождения/интересы; без имени, точной даты, фото, медданных.
"""
import json, os, threading, logging

log = logging.getLogger("storage")
try:
    import sheets
except Exception:
    sheets = None

_LOCK = threading.Lock()
LEADS, PARENTS, EVENTS = "ozi_leads.jsonl", "ozi_parents.jsonl", "ozi_events.jsonl"

def _use_sheets():
    return sheets is not None and sheets.available()

def _append_local(path, obj):
    with _LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _count_local(path):
    if not os.path.exists(path): return 0
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)

# ─────────────── ЛИДЫ ───────────────
def create_lead(date, center_id, center_name, direction, child_age,
                district, contact, consent):
    if _use_sheets():
        lead_id = sheets.count_rows("Лиды") + 1
        ok = sheets.append_by_header("Лиды", {
            "id_лида": lead_id, "Дата": date, "id_центра": center_id,
            "Название_центра": center_name, "Направление": direction,
            "Возраст_ребёнка": child_age, "Район": district,
            "Контакт_родителя": contact, "Согласие_на_передачу": consent,
            "Статус": "новый", "Отзыв_через_7_дней": "",
        })
        if ok: return lead_id
        log.warning("lead → Sheets не удалось, пишу локально")
    lead_id = _count_local(LEADS) + 1
    _append_local(LEADS, {"id_lead": lead_id, "date": date, "center_id": center_id,
        "center_name": center_name, "direction": direction, "child_age": child_age,
        "district": district, "contact": contact, "consent": consent, "status": "новый"})
    return lead_id

# ─────────────── РОДИТЕЛИ ───────────────
def upsert_parent(tg_id, username, dist, interests, first_seen):
    if _use_sheets():
        ok = sheets.append_by_header("Родители-Дети", {
            "TgID_родителя": tg_id, "Username": username, "Район": dist,
            "Интересы": interests, "Дата_первого_поиска": first_seen,
        })
        if ok: return
    _append_local(PARENTS, {"tg_id": tg_id, "username": username,
        "district": dist, "interests": interests, "first_seen": first_seen})

# ─────────────── СОБЫТИЯ ───────────────
def log_event(date, etype, tg_id, details):
    if _use_sheets():
        ok = sheets.append_by_header("События", {
            "Дата": date, "Тип_события": etype, "TgID": tg_id, "Детали": details})
        if ok: return
    _append_local(EVENTS, {"date": date, "type": etype, "tg_id": tg_id, "details": details})

# ─────────────── СТАТИСТИКА ───────────────
def stats():
    if _use_sheets():
        return {"leads": sheets.count_rows("Лиды"),
                "parents": sheets.count_rows("Родители-Дети"),
                "events": sheets.count_rows("События"),
                "source": "Google Sheets"}
    return {"leads": _count_local(LEADS), "parents": _count_local(PARENTS),
            "events": _count_local(EVENTS), "source": "локальные файлы (не сохраняются!)"}
