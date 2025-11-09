# sheets.py
import os
import base64
import json
import gspread
from typing import List, Dict, Optional

SHEET_KEY = os.getenv("GOOGLE_SHEETS_KEY")  # spreadsheet id

def _get_service_account_dict():
    b64 = os.getenv("GSPREAD_SERVICE_ACCOUNT_B64")
    if not b64:
        raise RuntimeError("GSPREAD_SERVICE_ACCOUNT_B64 not set")
    json_str = base64.b64decode(b64).decode("utf-8")
    return json.loads(json_str)

def _open_sheet():
    creds = _get_service_account_dict()
    gc = gspread.service_account_from_dict(creds)
    if not SHEET_KEY:
        raise RuntimeError("GOOGLE_SHEETS_KEY not set")
    sh = gc.open_by_key(SHEET_KEY)
    worksheet = sh.sheet1  # используем первый лист; можно изменить
    return worksheet

def get_all_products() -> List[Dict]:
    """
    Ожидается таблица с колонками:
    id, name, category, price, stock, description, photo_url, active
    """
    ws = _open_sheet()
    rows = ws.get_all_records()
    # Список словарей. Приведём поля к нужному типу
    products = []
    for r in rows:
        try:
            products.append({
                "id": str(r.get("id", "")).strip(),
                "name": r.get("name", ""),
                "category": r.get("category", ""),
                "price": float(r.get("price", 0) or 0),
                "stock": int(r.get("stock", 0) or 0),
                "description": r.get("description", ""),
                "photo_url": r.get("photo_url", ""),
                "active": str(r.get("active", "yes")).lower() in ("yes", "y", "true", "1")
            })
        except Exception:
            # если какая-то строка некорректна — пропустим её
            continue
    return products

def find_product_by_id(pid: str) -> Optional[Dict]:
    products = get_all_products()
    for p in products:
        if p["id"] == str(pid):
            return p
    return None

def add_product(row: Dict) -> None:
    """
    row: словарь с ключами, соответствующими колонкам.
    Добавляет новую строку в конец.
    """
    ws = _open_sheet()
    # сохраняем в порядке: id, name, category, price, stock, description, photo_url, active
    values = [
        row.get("id",""),
        row.get("name",""),
        row.get("category",""),
        row.get("price",""),
        row.get("stock",""),
        row.get("description",""),
        row.get("photo_url",""),
        row.get("active","yes"),
    ]
    ws.append_row(values, value_input_option="USER_ENTERED")
