# -*- coding: utf-8 -*-
"""OZIbridge — доступ к общей Google-таблице (та же, что у OZIkids)."""
import os, json, logging
log = logging.getLogger("sheets")
SHEET_ID = os.getenv("SHEET_ID", "").strip()
_CREDS_RAW = os.getenv("GOOGLE_CREDENTIALS", "").strip()
_sh = None; _ws_cache = {}

def available():
    return bool(SHEET_ID and _CREDS_RAW)

def _client():
    global _sh
    if _sh is not None: return _sh
    if not available(): return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_info(
            json.loads(_CREDS_RAW), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        _sh = gspread.authorize(creds).open_by_key(SHEET_ID)
        log.info("Sheets подключены")
        return _sh
    except Exception as e:
        log.warning(f"Sheets connect failed: {e}"); return None

def _ws(title):
    if title in _ws_cache: return _ws_cache[title]
    sh = _client()
    if not sh: return None
    try:
        ws = sh.worksheet(title); _ws_cache[title] = ws; return ws
    except Exception as e:
        log.warning(f"ws '{title}': {e}"); return None

def read_records(title):
    ws = _ws(title)
    if not ws: return []
    try: return ws.get_all_records()
    except Exception as e:
        log.warning(f"read '{title}': {e}"); return []

def update_lead_status(lead_id, new_status):
    """Найти лид по id_лида и записать новый Статус."""
    ws = _ws("Лиды")
    if not ws: return False
    try:
        headers = ws.row_values(1)
        id_col = headers.index("id_лида") + 1
        st_col = headers.index("Статус") + 1
        col_vals = ws.col_values(id_col)
        for r, v in enumerate(col_vals[1:], start=2):
            if str(v) == str(lead_id):
                ws.update_cell(r, st_col, new_status)
                return True
        return False
    except Exception as e:
        log.warning(f"update_lead_status: {e}"); return False
