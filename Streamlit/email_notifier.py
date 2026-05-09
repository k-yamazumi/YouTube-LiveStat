"""
メール通知モジュール
監視中の統計情報をメールで定期送信する。
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime, timedelta, timezone

# 日本時間のタイムゾーンを設定
JST = timezone(timedelta(hours=+9), 'JST')


def send_report_email(
    smtp_email: str,
    smtp_password: str,
    recipients: list[str],
    stats_data: list[dict],
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> dict:
    """
    監視レポートをメールで送信する。
    
    Args:
        smtp_email: 送信元メールアドレス
        smtp_password: SMTPパスワード（Gmailの場合はアプリパスワード）
        recipients: 送信先メールアドレスのリスト
        stats_data: 各監視対象の統計情報 [{name, video_id, stats}, ...]
        smtp_server: SMTPサーバー
        smtp_port: SMTPポート
    
    Returns:
        dict: {"status": "ok"} or {"status": "error", "message": "..."}
    """
    try:
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        
        # HTML メール本文を作成
        html = _build_html_report(stats_data, now)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📊 YouTube LiveStat レポート ({now})"
        msg["From"] = smtp_email
        msg["To"] = ", ".join(recipients)
        
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


def _build_html_report(stats_data: list[dict], timestamp: str) -> str:
    """HTML形式のレポートを生成する。"""
    rows_html = ""
    for entry in stats_data:
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
        
        rows_html += f"""
        <tr>
            <td style="padding:8px;border:1px solid #444;color:#fff;">{name}</td>
            <td style="padding:8px;border:1px solid #444;color:#FF4444;font-weight:bold;text-align:right;">{viewers:,}</td>
            <td style="padding:8px;border:1px solid #444;color:#4FC3F7;text-align:right;">{likes:,}</td>
            <td style="padding:8px;border:1px solid #444;color:#81C784;text-align:right;">{comments:,}</td>
            <td style="padding:8px;border:1px solid #444;color:#FFB74D;text-align:right;">{views:,}</td>
        </tr>
        """
    
    html = f"""
    <html>
    <body style="background:#1a1a2e;color:#fff;font-family:Arial,sans-serif;padding:20px;">
        <h2 style="color:#FF4444;">📊 YouTube LiveStat レポート</h2>
        <p style="color:#aaa;">取得時刻: {timestamp}</p>
        <table style="border-collapse:collapse;width:100%;background:#16213e;">
            <tr style="background:#0f3460;">
                <th style="padding:10px;border:1px solid #444;color:#fff;">名前</th>
                <th style="padding:10px;border:1px solid #444;color:#FF4444;">👀 視聴者数</th>
                <th style="padding:10px;border:1px solid #444;color:#4FC3F7;">👍 高評価</th>
                <th style="padding:10px;border:1px solid #444;color:#81C784;">💬 コメント</th>
                <th style="padding:10px;border:1px solid #444;color:#FFB74D;">📺 総視聴回数</th>
            </tr>
            {rows_html}
        </table>
        <p style="color:#666;font-size:12px;margin-top:20px;">
            このメールは YouTube LiveStat から自動送信されました。
        </p>
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
        
        lines.append(f"\n【{name}】")
        lines.append(f"  👀 同時視聴者数: {viewers}")
        lines.append(f"  👍 高評価数: {likes}")
        lines.append(f"  💬 コメント数: {comments}")
        lines.append(f"  📺 総視聴回数: {views}")
    
    lines.append("\n" + "=" * 50)
    lines.append("YouTube LiveStat からの自動送信")
    
    return "\n".join(lines)
