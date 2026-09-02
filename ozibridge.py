#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════
# OZIbridge — разведцентр данных OZI (команда). Продукт 3.
# Читает общую Google-таблицу, что наполняет OZIkids.
# Три оси: скорость OZI · накопление данных · МОСТ В ÖZEN.
# ══════════════════════════════════════════════════════════════
import os, io, csv, logging
import _loadenv  # подгружает .env локально
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import sheets, analytics as A

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO)
log = logging.getLogger("ozibridge")

BOT_TOKEN = os.getenv("BRIDGE_TOKEN", "PUT_BRIDGE_TOKEN")   # токен OZIbridge
ADMIN_IDS = [x.strip() for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

def _is_admin(uid): return str(uid) in ADMIN_IDS

def admin_only(func):
    async def wrap(update, ctx):
        if not _is_admin(update.effective_user.id):
            await update.effective_message.reply_text("⛔ Доступ только для команды OZI.")
            return
        return await func(update, ctx)
    return wrap

def _data():
    return (sheets.read_records("События"), sheets.read_records("Лиды"),
            sheets.read_records("Родители-Дети"), sheets.read_records("Центры"))

# ─────────────── КОМАНДЫ ───────────────
@admin_only
async def cmd_start(update, ctx):
    await update.message.reply_text(
        "🛰 *OZIbridge* — пульт и аналитика OZI.\n\n"
        "*Операции:*\n/leads — заявки со статусами\n/stats — сводка\n/today — за сегодня\n/find <центр>\n\n"
        "*Рост и партнёры:*\n/deficit — где спрос > предложения\n/funnel — воронка\n/demand — топ центров\n\n"
        "*Продукт:*\n/lost — искали и не нашли\n/pairs — связки направлений\n\n"
        "*Соцанализ и гранты:*\n/access — карта доступа по районам\n/demandprofile — профиль спроса\n\n"
        "*DBA и ÖZEN:*\n/profiles — профили-семена ÖZEN\n/export — обезличенный датасет\n/hexagon — мэппинг на измерения ÖZEN",
        parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_stats(update, ctx):
    ev, ld, pr, ce = _data()
    s = A.stats(ev, ld, ce)
    txt = (f"📊 *Сводка OZI*\n\n"
           f"Заявок сегодня: *{s['leads_today']}* · неделя: *{s['leads_week']}* · всего: *{s['leads_all']}*\n"
           f"Поисков всего: *{s['searches_all']}* · центров: *{s['centers']}*\n\n"
           f"*По направлениям (заявки):*\n" + ("\n".join(f"• {k}: {v}" for k,v in s['by_dir'][:8]) or "—") +
           f"\n\n*По районам (заявки):*\n" + ("\n".join(f"• {k}: {v}" for k,v in s['by_dist'][:8]) or "—"))
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_today(update, ctx):
    ev, ld, pr, ce = _data()
    t = A.today_activity(ev, ld)
    txt = "📅 *Сегодня*\n\n*События:*\n" + ("\n".join(f"• {k}: {v}" for k,v in t['events']) or "пока пусто")
    txt += f"\n\n*Заявки сегодня:* {len(t['leads'])}"
    for l in t['leads'][:10]:
        txt += f"\n• {l.get('Название_центра','?')} — {l.get('Статус','')}"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_leads(update, ctx):
    _, ld, _, _ = _data()
    if not ld:
        await update.message.reply_text("Заявок пока нет."); return
    await update.message.reply_text(f"🔥 *Последние заявки ({len(ld)})*", parse_mode=ParseMode.MARKDOWN)
    for l in ld[-10:][::-1]:
        lid = l.get("id_лида")
        txt = (f"🔥 *Заявка #{lid}* — {l.get('Статус','новый')}\n"
               f"🏫 {l.get('Название_центра','?')}\n📌 {l.get('Направление','')}\n"
               f"🏙 {l.get('Район','')} · 👦 {l.get('Возраст_ребёнка','')}\n"
               f"📞 {l.get('Контакт_родителя','')}\n🕐 {str(l.get('Дата',''))[:16]}")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📞 Связались", callback_data=f"st:{lid}:связались"),
            InlineKeyboardButton("✅ Записан", callback_data=f"st:{lid}:записан"),
            InlineKeyboardButton("❌ Не дозвон.", callback_data=f"st:{lid}:не дозвонились"),
        ]])
        await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def on_status(update, ctx):
    q = update.callback_query; await q.answer()
    if not _is_admin(q.from_user.id): return
    _, lid, status = q.data.split(":", 2)
    ok = sheets.update_lead_status(lid, status)
    await q.edit_message_text(q.message.text_markdown + f"\n\n➡️ Статус обновлён: *{status}*"
                              if ok else q.message.text + "\n\n⚠️ не удалось обновить",
                              parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_find(update, ctx):
    q = " ".join(ctx.args)
    if not q:
        await update.message.reply_text("Использование: /find <название центра>"); return
    _, _, _, ce = _data()
    res = A.find_center(ce, q)
    if not res:
        await update.message.reply_text("Ничего не нашёл."); return
    txt = f"🔎 Найдено {len(res)}:\n"
    for c in res:
        txt += f"\n🏫 *{c.get('Название')}* — {c.get('Подкатегория')}\n📍 {c.get('Адрес')} · {c.get('Район')}\n📞 {c.get('Телефон')}\n"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_deficit(update, ctx):
    ev, _, _, ce = _data()
    rows = A.deficit(ev, ce)
    if not rows:
        await update.message.reply_text("Данных для дефицита пока мало — накопится с поисками."); return
    cats = A.OZEN_DIMENSIONS
    txt = "📈 *Индекс дефицита* (спрос ÷ предложение)\nГде родители ищут, а центров мало:\n"
    for r in rows:
        txt += f"\n• {r['cat']} × {r['dist']}: спрос {r['demand']}, центров {r['supply']} → *{r['index']}*"
    txt += "\n\n_Аргумент для B2B: «в вашем районе N ищут это, а вас всего M»._"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_funnel(update, ctx):
    ev, ld, _, _ = _data()
    f = A.funnel(ev, ld)
    txt = (f"🫧 *Воронка спроса*\n\nПоиски: *{f['searches']}*\n↓ {f['search_to_lead']}%\n"
           f"Заявки: *{f['leads']}*\n↓ {f['lead_to_booked']}%\nЗаписаны: *{f['booked']}*\n\n"
           f"_Показывает партнёрам: OZI приводит реальных клиентов._")
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_demand(update, ctx):
    _, ld, _, _ = _data()
    r = A.demand_ranking(ld)
    if not r:
        await update.message.reply_text("Заявок пока нет — рейтинг наполнится."); return
    txt = "⭐ *Топ центров по заявкам* (основа PRO):\n" + "\n".join(f"{i}. {n} — {c}" for i,(n,c) in enumerate(r,1))
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_lost(update, ctx):
    ev, _, _, _ = _data()
    l = A.lost(ev)
    txt = "🕳 *Искали и не нашли* (чего добрать в базу):\n\n*Текстом:*\n"
    txt += ("\n".join(f"• {q} ×{n}" for q,n in l['text_lost']) or "—")
    txt += "\n\n*По фильтрам (пустая выдача):*\n"
    txt += ("\n".join(f"• {cat}×{dist} ×{n}" for (cat,dist),n in l['filter_lost']) or "—")
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_pairs(update, ctx):
    _, _, pr, _ = _data()
    p = A.pairs(pr)
    if not p:
        await update.message.reply_text("Связок пока мало — накопятся."); return
    txt = "🧩 *Связки направлений* (подсказка ÖZEN-маршрутов):\n" + "\n".join(f"• {a} + {b} ×{n}" for (a,b),n in p)
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_access(update, ctx):
    ev, ld, _, ce = _data()
    rows = A.access_map(ev, ld, ce)
    txt = "🌍 *Карта доступа по районам*\n(спрос vs число центров — язык грантодателей):\n"
    for r in rows:
        pc = r['per_center'] if r['per_center'] is not None else "нет центров!"
        txt += f"\n• {r['dist']}: центров {r['supply']}, спрос {r['demand']} → нагрузка {pc}"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_demandprofile(update, ctx):
    ev, _, pr, _ = _data()
    d = A.demand_profile(ev, pr)
    txt = "📊 *Профиль спроса Астаны* (обезличенно):\n\n*Что ищут (поиски):*\n"
    txt += ("\n".join(f"• {k}: {v}" for k,v in d['searched_cats']) or "—")
    txt += "\n\n*Интересы родителей:*\n" + ("\n".join(f"• {k}: {v}" for k,v in d['parent_interests']) or "—")
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_profiles(update, ctx):
    _, _, pr, _ = _data()
    profs = A.ozen_profiles(pr)
    if not profs:
        await update.message.reply_text("Профилей пока нет — появятся с первыми поисками."); return
    txt = f"🔮 *Профили-семена ÖZEN* ({len(profs)}) — черновики гексагона:\n_(обезличенно: район + интересы → измерения ÖZEN)_\n"
    for p in profs[:15]:
        txt += (f"\n*#{p['n']}* · {p['dist']}\n  интересы: {', '.join(p['interests'])}\n"
                f"  → ÖZEN: {', '.join(p['ozen_dimensions'])}")
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_hexagon(update, ctx):
    m = A.hexagon_map()
    txt = "⬡ *OZI → ÖZEN: мэппинг на измерения потенциала*\n\n"
    txt += "\n".join(f"• {k} → {v}" for k,v in m.items())
    txt += "\n\n_Данные OZI уже собираются на языке гексагона ÖZEN._"
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def cmd_export(update, ctx):
    ev, ld, pr, _ = _data()
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["тип","дата","район","направление_или_интересы","возраст_год","доп"])
    for l in ld:
        w.writerow(["лид", l.get("Дата"), l.get("Район"), l.get("Направление"),
                    l.get("Возраст_ребёнка"), l.get("Статус")])
    for p in pr:
        w.writerow(["профиль", p.get("Дата_первого_поиска"), p.get("Район"),
                    p.get("Интересы"), p.get("Год_рождения_ребёнка",""), ""])
    for cat,dist,cnt,_ in A._search_events(ev):
        w.writerow(["поиск","", dist, cat, "", cnt])
    data = buf.getvalue().encode("utf-8-sig")
    await update.message.reply_document(document=io.BytesIO(data), filename="ozi_dataset_anon.csv",
        caption="🎓 Обезличенный датасет для DBA (без имён/телефонов — только год рождения, интересы, район).")

def main():
    if BOT_TOKEN == "PUT_BRIDGE_TOKEN":
        print("⚠️ Установите BRIDGE_TOKEN"); return
    app = Application.builder().token(BOT_TOKEN).build()
    cmds = {"start":cmd_start,"leads":cmd_leads,"stats":cmd_stats,"today":cmd_today,"find":cmd_find,
            "deficit":cmd_deficit,"funnel":cmd_funnel,"demand":cmd_demand,"lost":cmd_lost,"pairs":cmd_pairs,
            "access":cmd_access,"demandprofile":cmd_demandprofile,"profiles":cmd_profiles,
            "hexagon":cmd_hexagon,"export":cmd_export}
    for name, fn in cmds.items(): app.add_handler(CommandHandler(name, fn))
    app.add_handler(CallbackQueryHandler(on_status, pattern="^st:"))
    print("🛰 OZIbridge запущен.")
    base = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    port = int(os.environ.get("PORT", "10000"))
    if base:
        app.run_webhook(listen="0.0.0.0", port=port, url_path=BOT_TOKEN,
                        webhook_url=f"{base}/{BOT_TOKEN}", drop_pending_updates=True)
    else:
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
