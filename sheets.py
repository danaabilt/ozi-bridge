# -*- coding: utf-8 -*-
"""
OZI — слой Google Sheets. Единое хранилище для всех трёх ботов.
Подключение по service account (креды — в переменной окружения GOOGLE_CREDENTIALS).
Если Sheets не настроен или недоступен — модули выше используют локальный запас (fallback),
поэтому бот никогда не падает из-за таблицы.
"""
import os, json, time, logging

log = logging.getLogger("sheets")

SHEET_ID = os.getenv("SHEET_ID", "").strip()
_CREDS_RAW = os.getenv("GOOGLE_CREDENTIALS", "").strip()

_gc = None
_sh = None
_ws_cache = {}

def available():
    return bool(SHEET_ID and _CREDS_RAW)

def _client():
    global _gc, _sh
    if _sh is not None:
        return _sh
    if not available():
        return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        info = json.loads(_CREDS_RAW)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        _gc = gspread.authorize(creds)
        _sh = _gc.open_by_key(SHEET_ID)
        log.info("Google Sheets подключены")
        return _sh
    except Exception as e:
        log.warning(f"Sheets connect failed: {e}")
        return None

def _ws(title):
    if title in _ws_cache:
        return _ws_cache[title]
    sh = _client()
    if not sh:
        return None
    try:
        ws = sh.worksheet(title)
        _ws_cache[title] = ws
        return ws
    except Exception as e:
        log.warning(f"worksheet '{title}' not found: {e}")
        return None

def read_records(title):
    """Вернуть все строки листа как список словарей (ключи = заголовки)."""
    ws = _ws(title)
    if not ws:
        return None
    try:
        return ws.get_all_records()
    except Exception as e:
        log.warning(f"read '{title}' failed: {e}")
        return None

def append_by_header(title, data: dict):
    """Дописать строку, сопоставив ключи data с заголовками листа (по имени, не по позиции)."""
    ws = _ws(title)
    if not ws:
        return False
    try:
        headers = ws.row_values(1)
        row = [str(data.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        log.warning(f"append '{title}' failed: {e}")
        return False

def count_rows(title):
    ws = _ws(title)
    if not ws:
        return 0
    try:
        return max(0, len(ws.get_all_values()) - 1)  # минус заголовок
    except Exception:
        return 0
