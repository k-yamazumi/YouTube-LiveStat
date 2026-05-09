"""
Google Sheets 書き込みモジュール
gspread + サービスアカウント認証でスプレッドシートに直接書き込む。

【前提条件】
- Streamlit secrets に [gcp_service_account] セクションでサービスアカウントの
  JSONキー内容が設定されていること
- 対象のスプレッドシートがサービスアカウントのメールアドレスと共有されていること
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional

# Google Sheets API のスコープ
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource(ttl=3600)
def _get_gspread_client():
    """
    Streamlit secrets からサービスアカウント認証情報を取得し、
    gspread クライアントを生成する（キャッシュ付き）。
    """
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def write_to_sheet(
    spreadsheet_url: str,
    headers: list[str],
    row: list,
    sheet_name: str = "シート1",
    write_header: bool = False,
) -> dict:
    """
    スプレッドシートにデータ行を追記する。

    Args:
        spreadsheet_url: スプレッドシートのURL
        headers: ヘッダー行（write_header=True の場合のみ書き込み）
        row: データ行
        sheet_name: シート名
        write_header: True の場合、シートが空ならヘッダーを先に書き込む

    Returns:
        dict: {"status": "ok"} or {"status": "error", "message": "..."}
    """
    # シート名が空の場合の安全対策（空だと毎回新しいシートが作られてしまうため）
    sheet_name = sheet_name.strip() if sheet_name else "シート1"
    if not sheet_name:
        sheet_name = "シート1"

    try:
        client = _get_gspread_client()
        spreadsheet = client.open_by_url(spreadsheet_url)

        # シートを取得（存在しなければ新しく作成）
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

        # 書き込むデータの準備
        rows_to_append = []
        if write_header and headers:
            rows_to_append.append(headers)
        if row:
            rows_to_append.append(row)

        # 一括で追記（分散するのを防ぐ）
        if rows_to_append:
            worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")

        return {"status": "ok"}

    except gspread.exceptions.SpreadsheetNotFound:
        return {"status": "error", "message": "スプレッドシートが見つかりません。URLを確認するか、サービスアカウントとの共有設定を確認してください。"}
    except gspread.exceptions.APIError as e:
        return {"status": "error", "message": f"Google Sheets APIエラー: {str(e)}"}
    except KeyError:
        return {"status": "error", "message": "サービスアカウントの認証情報が設定されていません。Streamlit secrets に [gcp_service_account] を設定してください。"}
    except Exception as e:
        return {"status": "error", "message": f"予期しないエラー: {str(e)}"}


def build_headers(monitor_names: list[str]) -> list[str]:
    """
    CSVおよびスプレッドシートのヘッダー行を生成する。
    """
    headers = ["タイムスタンプ"]
    for name in monitor_names:
        headers.extend([
            f"同時視聴者数({name})",
            f"高評価数({name})",
            f"総視聴回数({name})",
        ])
    return headers


def build_row(timestamp: str, stats_list: list[dict]) -> list:
    """
    1行分のデータを生成する。
    """
    row = [timestamp]
    for stats in stats_list:
        row.extend([
            stats.get("concurrent_viewers", ""),
            stats.get("like_count", ""),
            stats.get("view_count", ""),
        ])
    return row
