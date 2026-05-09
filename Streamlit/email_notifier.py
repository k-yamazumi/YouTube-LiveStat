"""
メール通知モジュール
監視中の統計情報をメールで定期送信する。
"""

import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional
from datetime import datetime, timedelta, timezone

# 日本時間のタイムゾーンを設定
JST = timezone(timedelta(hours=+9), 'JST')


def send_report_email(
    smtp_email: str,
    smtp_password: str,
    recipients: list[str],
    stats_data: list[dict],
    sender_name: str = "YouTube LiveStat 自動通知",
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    image_bytes: Optional[bytes] = None,
) -> dict:
    """
    監視レポートをメールで送信する。
    
    Args:
        smtp_email: 送信元メールアドレス
        smtp_password: SMTPパスワード（Gmailの場合はアプリパスワード）
        recipients: 送信先メールアドレスのリスト
        stats_data: 各監視対象の統計情報 [{name, video_id, stats}, ...]
        sender_name: 送信元の表示名
        smtp_server: SMTPサーバー
        smtp_port: SMTPポート
        image_bytes: グラフ画像のバイトデータ
    
    Returns:
        dict: {"status": "ok"} or {"status": "error", "message": "..."}
    """
    try:
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        
        # 画像をBase64エンコード
        image_base64 = None
        if image_bytes:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        
        # HTML メール本文を作成
        html = _build_html_report(stats_data, now, image_base64=image_base64)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📊 YouTubeLive 監視レポート ({now})"
        msg["From"] = formataddr((sender_name, smtp_email))
        
        # 宛先一覧を隠す（BCCとして扱う）
        msg["To"] = "undisclosed-recipients:;"
        
        # テキスト版
        text = _build_text_report(stats_data, now)
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, recipients, msg.as_string())
        
        return {"status": "ok"}
    
    except smtplib.SMTPAuthenticationError:
        return {"status": "error", "message": "SMTP認証に失敗しました。メールアドレスとパスワードを確認してください。"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _build_html_report(stats_data: list[dict], timestamp: str, image_base64: str | None = None) -> str:
    """HTML形式のレポートを生成する。"""
    rows_html = ""
    for i, entry in enumerate(stats_data):
        name = entry.get("name", "")
        stats = entry.get("stats", {})
        viewers = stats.get("concurrent_viewers", "—")
        likes = stats.get("like_count", "—")
        comments = stats.get("comment_count", "—")
        views = stats.get("view_count", "—")
        
        if viewers is None:
            viewers = "—"
        if likes is None:
            likes = "—"
        if comments is None:
            comments = "—"
        if views is None:
            views = "—"
        
        # フォーマット（数値ならカンマ区切り、文字列ならそのまま）
        viewers_str = f"{int(viewers):,}" if isinstance(viewers, (int, float, str)) and str(viewers).isdigit() else viewers
        likes_str = f"{int(likes):,}" if isinstance(likes, (int, float, str)) and str(likes).isdigit() else likes
        comments_str = f"{int(comments):,}" if isinstance(comments, (int, float, str)) and str(comments).isdigit() else comments
        views_str = f"{int(views):,}" if isinstance(views, (int, float, str)) and str(views).isdigit() else views

        bg_color = "#ffffff" if i % 2 == 0 else "#f8f9fa"

        rows_html += f"""
        <tr style="background-color: {bg_color};">
            <td style="padding: 12px 15px; border-bottom: 1px solid #eeeeee; color: #333333; font-weight: bold;">{name}</td>
            <td style="padding: 12px 15px; border-bottom: 1px solid #eeeeee; color: #d32f2f; font-weight: bold; text-align: right;">{viewers_str}</td>
            <td style="padding: 12px 15px; border-bottom: 1px solid #eeeeee; color: #1976d2; text-align: right;">{likes_str}</td>
            <td style="padding: 12px 15px; border-bottom: 1px solid #eeeeee; color: #f57c00; text-align: right;">{views_str}</td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f0f2f5; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333333;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f0f2f5; padding: 30px 10px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 4px solid #ff0000; border-bottom: 1px solid #dddddd; border-left: 1px solid #dddddd; border-right: 1px solid #dddddd;">
                        <tr>
                            <td style="padding: 25px 30px; border-bottom: 1px solid #eeeeee; background-color: #ffffff;">
                                <h2 style="margin: 0; color: #222222; font-size: 22px;">📊 YouTubeLive 監視レポート</h2>
                                <p style="margin: 8px 0 0 0; color: #777777; font-size: 13px;">取得時刻: {timestamp}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 15px 20px; background-color: #ffffff;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse; font-size: 14px;">
                                    <thead>
                                        <tr>
                                            <th style="padding: 12px 15px; border-bottom: 2px solid #dddddd; color: #555555; text-align: left; font-weight: bold; background-color: #f4f6f8;">名前</th>
                                            <th style="padding: 12px 15px; border-bottom: 2px solid #dddddd; color: #555555; text-align: right; font-weight: bold; background-color: #f4f6f8;">👀 視聴者数</th>
                                            <th style="padding: 12px 15px; border-bottom: 2px solid #dddddd; color: #555555; text-align: right; font-weight: bold; background-color: #f4f6f8;">👍 高評価</th>
                                            <th style="padding: 12px 15px; border-bottom: 2px solid #dddddd; color: #555555; text-align: right; font-weight: bold; background-color: #f4f6f8;">📺 総視聴回数</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {rows_html}
                                    </tbody>
                                </table>
                            </td>
                        </tr>
                        {f'''
                        <tr>
                            <td style="padding: 20px 30px; background-color: #ffffff; text-align: center; border-top: 1px solid #eeeeee;">
                                <h3 style="margin: 0 0 10px 0; color: #555555; font-size: 16px; text-align: left;">📈 同時視聴者数 推移グラフ</h3>
                                <img src="data:image/png;base64,{image_base64}" alt="グラフ" style="max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #eeeeee;">
                            </td>
                        </tr>
                        ''' if image_base64 else ''}
                        <tr>
                            <td style="padding: 20px 30px; background-color: #fafafa; border-top: 1px solid #eeeeee; text-align: center;">
                                <p style="margin: 0; color: #999999; font-size: 12px;">
                                    このメールはアプリから自動送信されました。<br>
                                    <a href="https://ytlivestat.streamlit.app/" target="_blank" style="color: #1976d2; text-decoration: none;">https://ytlivestat.streamlit.app/</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


def _build_text_report(stats_data: list[dict], timestamp: str) -> str:
    """テキスト形式のレポートを生成する。"""
    lines = [
        "📊 YouTube LiveStat レポート",
        f"取得時刻: {timestamp}",
        "=" * 50,
    ]
    
    for entry in stats_data:
        name = entry.get("name", "")
        stats = entry.get("stats", {})
        viewers = stats.get("concurrent_viewers", "—")
        likes = stats.get("like_count", "—")
        comments = stats.get("comment_count", "—")
        views = stats.get("view_count", "—")
        
        # フォーマット（数値ならカンマ区切り、文字列ならそのまま）
        viewers_str = f"{int(viewers):,}" if isinstance(viewers, (int, float, str)) and str(viewers).isdigit() else viewers
        likes_str = f"{int(likes):,}" if isinstance(likes, (int, float, str)) and str(likes).isdigit() else likes
        comments_str = f"{int(comments):,}" if isinstance(comments, (int, float, str)) and str(comments).isdigit() else comments
        views_str = f"{int(views):,}" if isinstance(views, (int, float, str)) and str(views).isdigit() else views

        lines.append(f"\n【{name}】")
        lines.append(f"  👀 同時視聴者数: {viewers_str}")
        lines.append(f"  👍 高評価数: {likes_str}")
        lines.append(f"  📺 総視聴回数: {views_str}")
    
    lines.append("\n" + "=" * 50)
    lines.append("YouTube LiveStat からの自動送信")
    
    return "\n".join(lines)
