import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
import json

def get_gspread_client():
    creds_b64 = os.environ.get("GSPREAD_SERVICE_ACCOUNT_B64")
    creds_json = json.loads(base64.b64decode(creds_b64))
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client

def get_catalog():
    """Возвращает список товаров из Google Sheets"""
    client = get_gspread_client()
    sheet = client.open_by_key(os.environ.get("GOOGLE_SHEETS_KEY")).sheet1
    return sheet.get_all_records()
