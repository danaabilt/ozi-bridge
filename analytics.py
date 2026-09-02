# -*- coding: utf-8 -*-
"""
OZIbridge — аналитика над данными OZI. Чистые функции (тестируются без Telegram/Sheets).
Три оси каждого расчёта: скорость OZI · накопление данных · МОСТ В ÖZEN.
Регуляторная граница: по детям — только год рождения/интересы; без имён/точных дат/медданных.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

KZ = timezone(timedelta(hours=5))

# 8 направлений OZI → 6 измерений потенциала ÖZEN (черновой мэппинг гексагона)
OZEN_DIMENSIONS = {
    "academic":    "Интеллект / знания",
    "mind":        "Логика / мышление",
    "art":         "Творчество / самовыражение",
    "sport":       "Тело / здоровье",
    "combat":      "Воля / дисциплина",
    "development": "Коммуникация / ценности",
}

def _today(): return datetime.now(KZ).date()

def _parse_date(s):
    try: return datetime.fromisoformat(str(s)).date()
    except Exception:
        try: return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
        except Exception: return None

# ─── парсинг событий ───
def _search_events(events):
    """search: детали 'cat/age/dist/budget=count'. Возвращает [(cat,dist,count,date)]."""
    out = []
    for e in events:
        if e.get("Тип_события") != "search": continue
        d = str(e.get("Детали", ""))
        try:
            body, cnt = d.rsplit("=", 1); cnt = int(cnt)
            cat, age, dist, budget = body.split("/")
            out.append((cat, dist, cnt, _parse_date(e.get("Дата"))))
        except Exception: continue
    return out

def _text_searches(events):
    """text_search: детали 'query=count'."""
    out = []
    for e in events:
        if e.get("Тип_события") != "text_search": continue
        d = str(e.get("Детали", ""))
        try:
            q, cnt = d.rsplit("=", 1); out.append((q, int(cnt), _parse_date(e.get("Дата"))))
        except Exception: continue
    return out

# ─── ОПЕРАЦИИ ───
def stats(events, leads, centers):
    t = _today(); wk = t - timedelta(days=7)
    ldates = [_parse_date(l.get("Дата")) for l in leads]
    leads_today = sum(1 for d in ldates if d == t)
    leads_week = sum(1 for d in ldates if d and d >= wk)
    by_dir = Counter(l.get("Направление","?") for l in leads)
    by_dist = Counter(l.get("Район","?") for l in leads)
    searches = sum(1 for e in events if e.get("Тип_события") in ("search","text_search"))
    return {
        "leads_today": leads_today, "leads_week": leads_week, "leads_all": len(leads),
        "searches_all": searches, "centers": len(centers),
        "by_dir": by_dir.most_common(), "by_dist": by_dist.most_common(),
    }

def today_activity(events, leads):
    t = _today()
    ev_today = [e for e in events if _parse_date(e.get("Дата")) == t]
    types = Counter(e.get("Тип_события") for e in ev_today)
    leads_today = [l for l in leads if _parse_date(l.get("Дата")) == t]
    return {"events": types.most_common(), "leads": leads_today}

def find_center(centers, q):
    q = q.lower().strip()
    return [c for c in centers if q in str(c.get("Название","")).lower()
            or q in str(c.get("Подкатегория","")).lower()][:8]

# ─── РОСТ и ПАРТНЁРЫ ───
def deficit(events, centers):
    """Индекс дефицита: спрос(поиски) ÷ предложение(центры) по паре направление×район."""
    demand = Counter()
    for cat, dist, cnt, _ in _search_events(events):
        demand[(cat, dist)] += 1
    supply = Counter()
    for c in centers:
        supply[(c.get("Ключ_категории"), c.get("Ключ_района"))] += 1
    rows = []
    for (cat, dist), dem in demand.items():
        sup = supply.get((cat, dist), 0)
        idx = dem / sup if sup else dem * 2  # нет предложения → максимальный дефицит
        rows.append({"cat": cat, "dist": dist, "demand": dem, "supply": sup, "index": round(idx,2)})
    rows.sort(key=lambda r: -r["index"])
    return rows[:12]

def funnel(events, leads):
    searches = sum(1 for e in events if e.get("Тип_события") in ("search","text_search"))
    n_leads = len(leads)
    booked = sum(1 for l in leads if "Записан" in str(l.get("Статус","")))
    conv1 = round(100*n_leads/searches,1) if searches else 0
    conv2 = round(100*booked/n_leads,1) if n_leads else 0
    return {"searches": searches, "leads": n_leads, "booked": booked,
            "search_to_lead": conv1, "lead_to_booked": conv2}

def demand_ranking(leads):
    c = Counter(l.get("Название_центра","?") for l in leads if l.get("Название_центра"))
    return c.most_common(10)

# ─── КЛИЕНТЫ и ПРОДУКТ ───
def lost(events):
    """Что искали и НЕ нашли (count=0)."""
    out = []
    for q, cnt, date in _text_searches(events):
        if cnt == 0: out.append(q)
    zero_cat = [(cat,dist) for cat,dist,cnt,_ in _search_events(events) if cnt == 0]
    return {"text_lost": Counter(out).most_common(15), "filter_lost": Counter(zero_cat).most_common(10)}

def pairs(parents):
    """Популярные связки направлений (по интересам родителей) → подсказка ÖZEN-маршрутов."""
    by_user = defaultdict(set)
    for p in parents:
        uid = p.get("TgID_родителя")
        for i in str(p.get("Интересы","")).split(","):
            i = i.strip()
            if i: by_user[uid].add(i)
    pc = Counter()
    for ints in by_user.values():
        ints = sorted(ints)
        for a in range(len(ints)):
            for b in range(a+1, len(ints)):
                pc[(ints[a], ints[b])] += 1
    return pc.most_common(12)

# ─── СОЦАНАЛИЗ и ГРАНТЫ ───
def access_map(events, leads, centers):
    """Карта доступа по районам: спрос vs число центров (язык грантодателей)."""
    dist_names = {}
    supply = Counter()
    for c in centers:
        supply[c.get("Ключ_района")] += 1
        dist_names[c.get("Ключ_района")] = c.get("Район", c.get("Ключ_района"))
    demand = Counter()
    for _, dist, _, _ in _search_events(events):
        demand[dist] += 1
    rows = []
    for dist in set(list(supply) + list(demand)):
        dem = demand.get(dist,0); sup = supply.get(dist,0)
        rows.append({"dist": dist_names.get(dist, dist), "demand": dem, "supply": sup,
                     "per_center": round(dem/sup,2) if sup else None})
    rows.sort(key=lambda r: -(r["per_center"] or 999))
    return rows

def demand_profile(events, parents):
    """Профиль спроса Астаны (обезличенно): что ищут для детей."""
    cats = Counter()
    for cat, dist, cnt, _ in _search_events(events):
        cats[cat] += 1
    interests = Counter()
    for p in parents:
        for i in str(p.get("Интересы","")).split(","):
            i=i.strip()
            if i: interests[i]+=1
    return {"searched_cats": cats.most_common(), "parent_interests": interests.most_common()}

# ─── ÖZEN-МОСТ ───
def ozen_profiles(parents):
    """Анонимные профили-семена (черновики гексагона ÖZEN). Только район+интересы, без имён."""
    agg = {}
    for p in parents:
        uid = p.get("TgID_родителя")
        if uid not in agg:
            agg[uid] = {"dist": p.get("Район",""), "interests": set(), "since": p.get("Дата_первого_поиска","")}
        for i in str(p.get("Интересы","")).split(","):
            i=i.strip()
            if i: agg[uid]["interests"].add(i)
    profiles = []
    for i,(uid,d) in enumerate(agg.items(), 1):
        dims = sorted({OZEN_DIMENSIONS.get(x, x) for x in d["interests"]})
        profiles.append({"n": i, "dist": d["dist"], "interests": sorted(d["interests"]),
                         "ozen_dimensions": dims})
    return profiles

def hexagon_map():
    """Мэппинг 8 направлений OZI → измерения ÖZEN."""
    return OZEN_DIMENSIONS
