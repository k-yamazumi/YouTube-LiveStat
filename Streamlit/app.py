"""
YouTube LiveStat - 同時接続数リアルタイム監視ツール
Streamlit Cloud で公開するアプリケーション
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import io
import csv

from youtube_api import extract_video_id, fetch_video_stats, fetch_multiple_video_stats
from sheets_writer import write_to_sheet, build_headers, build_row
from email_notifier import send_report_email

# ─────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube LiveStat",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# カスタムCSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* 全体フォント */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* メトリクスカード */
div[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1a1d23 0%, #252830 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.4);
}

/* サイドバー */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0E1117 0%, #151820 100%);
    border-right: 1px solid rgba(255,255,255,0.05);
}

/* ボタン */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
    border: none;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(255,0,0,0.3);
}

/* タイトル装飾 */
.main-title {
    background: linear-gradient(90deg, #FF0000, #FF4444, #FF6B6B);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.2rem;
    font-weight: 700;
    margin-bottom: 0;
}
.sub-title {
    color: #888;
    font-size: 0.95rem;
    margin-top: 0;
}

/* ステータスバッジ */
.badge-live {
    display: inline-block;
    background: #FF0000;
    color: white;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
.badge-offline {
    display: inline-block;
    background: #444;
    color: #aaa;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 700;
}

/* 監視対象テーブル */
.monitor-item {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
}

/* 横スクロール対応（メトリクス行） */
div[data-testid="element-container"]:has(#monitor-metrics-scroll) + div[data-testid="stHorizontalBlock"] {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: 15px;
}
div[data-testid="element-container"]:has(#monitor-metrics-scroll) + div[data-testid="stHorizontalBlock"]::-webkit-scrollbar {
    height: 8px;
}
div[data-testid="element-container"]:has(#monitor-metrics-scroll) + div[data-testid="stHorizontalBlock"]::-webkit-scrollbar-track {
    background: rgba(255,255,255,0.05);
    border-radius: 4px;
}
div[data-testid="element-container"]:has(#monitor-metrics-scroll) + div[data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.2);
    border-radius: 4px;
}
div[data-testid="element-container"]:has(#monitor-metrics-scroll) + div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    min-width: 320px;
    flex: 0 0 auto;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session State 初期化
# ─────────────────────────────────────────────
def init_session_state():
    default_email = ""
    try:
        default_email = st.secrets.get("SMTP_EMAIL", "")
    except Exception:
        pass

    defaults = {
        "monitors": {},          # {name: {"url": str, "video_id": str, "title": str}}
        "monitoring": False,     # 監視中かどうか
        "history": {},           # {name: [{"time": datetime, "viewers": int, ...}, ...]}
        "all_rows": [],          # CSV用の全行データ
        "last_fetch_time": None,
        "last_email_time": None,
        "api_key": "",
        "fetch_interval": 30,
        # スプレッドシート設定
        "use_sheets": False,
        "spreadsheet_url": "",
        "sheet_name": "シート1",
        "sheets_header_written": False,
        # メール設定
        "use_email": False,
        "email_recipients": default_email,
        "email_interval": 15,  # 分
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()


# ─────────────────────────────────────────────
# APIキー取得
# ─────────────────────────────────────────────
def get_api_key() -> str:
    """st.secrets または session_state からAPIキーを取得"""
    try:
        return st.secrets["YOUTUBE_API_KEY"]
    except Exception:
        return st.session_state.get("api_key", "")


def has_sheets_credentials() -> bool:
    """サービスアカウント認証情報が設定されているかチェック"""
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False


# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown('<p class="main-title">📊 YouTube LiveStat</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">同時接続数リアルタイム監視</p>', unsafe_allow_html=True)
        st.divider()

        # APIキー設定
        api_key = get_api_key()
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            st.session_state.api_key = st.text_input(
                "🔑 YouTube API Key",
                type="password",
                value=st.session_state.api_key,
                help="YouTube Data API v3 のAPIキーを入力してください",
            )

        # ─── 取得間隔 ───
        st.session_state.fetch_interval = st.slider(
            "⏱️ 取得間隔（秒）", 10, 180, st.session_state.fetch_interval, 5,
            disabled=st.session_state.monitoring,
        )

        st.divider()

        # ─── 監視対象の追加 ───
        st.subheader("➕ 監視対象を追加")
        with st.form("add_monitor", clear_on_submit=True):
            name = st.text_input("名前", placeholder="例: チャンネルA")
            url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...")
            submitted = st.form_submit_button("追加", use_container_width=True)
            
            if submitted:
                if not name:
                    st.error("名前を入力してください")
                elif not url:
                    st.error("URLを入力してください")
                elif name in st.session_state.monitors:
                    st.error(f"「{name}」は既に登録されています")
                else:
                    video_id = extract_video_id(url)
                    if not video_id:
                        st.error("有効なYouTube URLを入力してください")
                    else:
                        st.session_state.monitors[name] = {
                            "url": url,
                            "video_id": video_id,
                            "title": "",
                        }
                        st.session_state.history[name] = []
                        st.success(f"✅ 「{name}」を追加しました (ID: {video_id})")
                        st.rerun()

        # ─── 登録済みリスト ───
        if st.session_state.monitors:
            st.subheader("📋 監視対象一覧")
            for name, info in list(st.session_state.monitors.items()):
                with st.container():
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        title_display = info.get("title", "") or info["video_id"]
                        st.markdown(f"**{name}** — <a href='{info['url']}' target='_blank' style='color: #4CAF50; text-decoration: none;'>{title_display}</a>", unsafe_allow_html=True)
                    with c2:
                        if st.button("🗑️", key=f"del_{name}", disabled=st.session_state.monitoring):
                            del st.session_state.monitors[name]
                            if name in st.session_state.history:
                                del st.session_state.history[name]
                            st.rerun()

        st.divider()

        # ─── スプレッドシート設定（トグル） ───
        st.session_state.use_sheets = st.toggle(
            "📄 スプレッドシート連携",
            value=st.session_state.use_sheets,
            disabled=st.session_state.monitoring,
        )
        if st.session_state.use_sheets:
            with st.expander("スプレッドシート設定", expanded=True):
                if not has_sheets_credentials():
                    st.warning("⚠️ サービスアカウント認証情報が未設定です。Streamlit Cloud の Secrets に `[gcp_service_account]` を設定してください。")
                else:
                    st.success("✅ サービスアカウント認証OK")
                
                st.session_state.spreadsheet_url = st.text_input(
                    "スプレッドシートURL",
                    value=st.session_state.spreadsheet_url,
                    help="サービスアカウントのメールアドレスと共有済みのスプレッドシートURL",
                    disabled=st.session_state.monitoring,
                )
                st.session_state.sheet_name = st.text_input(
                    "シート名",
                    value=st.session_state.sheet_name,
                    disabled=st.session_state.monitoring,
                )
                st.caption("ℹ️ スプレッドシートの共有設定で「リンクを知っている全員」を「編集者」に設定してください。")

        # ─── メール設定（トグル） ───
        st.session_state.use_email = st.toggle(
            "📧 メール通知",
            value=st.session_state.use_email,
            disabled=st.session_state.monitoring,
        )
        if st.session_state.use_email:
            with st.expander("メール設定", expanded=True):
                # SMTP認証情報はsecretsから取得
                has_smtp = False
                try:
                    has_smtp = bool(st.secrets.get("SMTP_EMAIL")) and bool(st.secrets.get("SMTP_PASSWORD"))
                except Exception:
                    pass
                if not has_smtp:
                    st.warning("⚠️ SMTP認証情報が未設定です。")
                else:
                    st.success("✅ SMTP認証OK")

                st.session_state.email_recipients = st.text_area(
                    "送信先（1行1アドレス）",
                    value=st.session_state.email_recipients,
                    height=80,
                    disabled=st.session_state.monitoring,
                )
                st.session_state.email_interval = st.number_input(
                    "通知間隔（分）",
                    min_value=5,
                    value=st.session_state.email_interval,
                    step=1,
                    disabled=st.session_state.monitoring,
                )


# ─────────────────────────────────────────────
# データ取得
# ─────────────────────────────────────────────
def fetch_all_stats():
    """全監視対象のデータを取得しhistoryに追加する"""
    api_key = get_api_key()
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return

    monitors = st.session_state.monitors
    if not monitors:
        return

    names = list(monitors.keys())
    video_ids = [monitors[n]["video_id"] for n in names]
    
    results = fetch_multiple_video_stats(video_ids, api_key)
    now = datetime.now()
    
    stats_for_row = []
    
    for name, stats in zip(names, results):
        # タイトル更新
        if stats.get("title"):
            st.session_state.monitors[name]["title"] = stats["title"]
        
        # 履歴に追加
        entry = {
            "time": now,
            "concurrent_viewers": stats.get("concurrent_viewers"),
            "like_count": stats.get("like_count"),
            "comment_count": stats.get("comment_count"),
            "view_count": stats.get("view_count"),
            "is_live": stats.get("is_live", False),
            "error": stats.get("error"),
        }
        st.session_state.history[name].append(entry)
        stats_for_row.append(stats)
    
    # CSV用の行データを保存
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    row = build_row(timestamp_str, stats_for_row)
    st.session_state.all_rows.append(row)
    
    # スプレッドシートへの書き込み
    if st.session_state.use_sheets and st.session_state.spreadsheet_url and has_sheets_credentials():
        headers = build_headers(names)
        write_to_sheet(
            st.session_state.spreadsheet_url,
            headers,
            row,
            st.session_state.sheet_name,
            write_header=not st.session_state.sheets_header_written,
        )
        st.session_state.sheets_header_written = True
    
    # メール通知
    if st.session_state.use_email:
        smtp_email = ""
        smtp_password = ""
        try:
            smtp_email = st.secrets.get("SMTP_EMAIL", "")
            smtp_password = st.secrets.get("SMTP_PASSWORD", "")
        except Exception:
            pass

        if smtp_email and smtp_password:
            should_send = False
            if st.session_state.last_email_time is None:
                should_send = True
            else:
                elapsed = (now - st.session_state.last_email_time).total_seconds() / 60
                if elapsed >= st.session_state.email_interval:
                    should_send = True
            
            if should_send:
                recipients = [
                    r.strip() for r in st.session_state.email_recipients.split("\n")
                    if r.strip()
                ]
                if recipients:
                    email_data = []
                    for name, stats in zip(names, results):
                        email_data.append({"name": name, "stats": stats})
                    
                    try:
                        send_report_email(
                            smtp_email,
                            smtp_password,
                            recipients,
                            email_data,
                        )
                        st.session_state.last_email_time = now
                    except Exception:
                        pass  # メール送信失敗は無視
    
    st.session_state.last_fetch_time = now


# ─────────────────────────────────────────────
# グラフ描画
# ─────────────────────────────────────────────
COLORS = [
    "#FF4444", "#4FC3F7", "#81C784", "#FFB74D", "#CE93D8",
    "#F06292", "#4DD0E1", "#AED581", "#FFD54F", "#90A4AE",
]

def render_chart(selected_names: list[str], metric: str, title: str, y_label: str):
    """選択された監視対象のデータをPlotlyグラフで表示する"""
    fig = go.Figure()
    
    for i, name in enumerate(selected_names):
        history = st.session_state.history.get(name, [])
        if not history:
            continue
        
        times = [h["time"] for h in history]
        values = [h.get(metric) for h in history]
        
        color = COLORS[i % len(COLORS)]
        
        fig.add_trace(go.Scatter(
            x=times,
            y=values,
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=2.5),
            marker=dict(size=4, color=color),
            connectgaps=False,
        ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color="#fff")),
        xaxis=dict(
            title="時刻",
            gridcolor="rgba(255,255,255,0.05)",
            color="#888",
        ),
        yaxis=dict(
            title=y_label,
            gridcolor="rgba(255,255,255,0.08)",
            color="#888",
            rangemode="tozero",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#ccc"),
        legend=dict(
            bgcolor="rgba(0,0,0,0.3)",
            bordercolor="rgba(255,255,255,0.1)",
            borderwidth=1,
            font=dict(color="#fff"),
        ),
        height=400,
        margin=dict(l=60, r=20, t=50, b=60),
        hovermode="x unified",
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────
# メインUI
# ─────────────────────────────────────────────
def render_main():
    # ヘッダー
    st.markdown('<p class="main-title">📊 YouTube LiveStat</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">YouTube Live 同時接続数リアルタイム監視ツール</p>', unsafe_allow_html=True)
    
    monitors = st.session_state.monitors
    
    if not monitors:
        st.info("👈 サイドバーから監視対象のYouTube URLを追加してください")
        return
    
    # ─── コントロールボタン ───
    col_start, col_stop, col_spacer = st.columns([1, 1, 3])
    
    with col_start:
        if st.button(
            "▶️ 監視開始" if not st.session_state.monitoring else "⏸️ 監視中...",
            use_container_width=True,
            type="primary",
            disabled=st.session_state.monitoring,
        ):
            api_key = get_api_key()
            if not api_key or api_key == "YOUR_API_KEY_HERE":
                st.error("APIキーを設定してください")
            else:
                st.session_state.monitoring = True
                st.session_state.sheets_header_written = False
                st.session_state.last_email_time = None
                st.rerun()
    
    with col_stop:
        if st.button(
            "⏹️ 監視終了",
            use_container_width=True,
            disabled=not st.session_state.monitoring,
        ):
            st.session_state.monitoring = False
            st.rerun()

    # ─── リアルタイム数値表示 ───
    if st.session_state.history:
        st.divider()
        st.markdown('<div id="monitor-metrics-scroll"></div>', unsafe_allow_html=True)
        names = list(monitors.keys())
        cols = st.columns(max(len(names), 1))
        
        for i, name in enumerate(names):
            history = st.session_state.history.get(name, [])
            col = cols[i]
            
            with col:
                if history:
                    latest = history[-1]
                    viewers = latest.get("concurrent_viewers")
                    is_live = latest.get("is_live", False)
                    
                    # ステータスバッジ
                    badge = '<span class="badge-live">● LIVE</span>' if is_live else '<span class="badge-offline">終了</span>'
                    st.markdown(f"**{name}** {badge}", unsafe_allow_html=True)
                    
                    # メトリクス
                    viewer_str = f"{viewers:,}" if viewers is not None else "—"
                    last_time = latest.get("time").strftime("%H:%M:%S") if latest.get("time") else "—"
                    
                    st.metric("👀 同時視聴者数", viewer_str, delta=f"最終取得: {last_time}", delta_color="off")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        likes = latest.get("like_count")
                        st.metric("👍 高評価", f"{likes:,}" if likes is not None else "—")
                    with c2:
                        comments = latest.get("comment_count")
                        st.metric("💬 コメント", f"{comments:,}" if comments is not None else "—")
                    
                    if latest.get("error"):
                        st.caption(f"⚠️ {latest['error']}")
                else:
                    st.markdown(f"**{name}**")
                    st.caption("データなし")

    # ─── グラフ表示 ───
    if any(st.session_state.history.get(n) for n in monitors):
        st.divider()
        st.subheader("📈 グラフ")
        
        all_names = list(monitors.keys())
        
        # グラフに表示する対象を選択
        selected = st.multiselect(
            "表示する監視対象を選択",
            all_names,
            default=all_names,
            key="chart_select",
        )
        
        if selected:
            # タブでメトリクスを切り替え
            tab_viewers, tab_likes, tab_comments = st.tabs([
                "👀 同時視聴者数", "👍 高評価数", "💬 コメント数"
            ])
            
            with tab_viewers:
                render_chart(selected, "concurrent_viewers", "同時視聴者数", "視聴者数")
            with tab_likes:
                render_chart(selected, "like_count", "高評価数", "高評価")
            with tab_comments:
                render_chart(selected, "comment_count", "コメント数", "コメント")

    # ─── CSV出力 ───
    if st.session_state.all_rows:
        st.divider()
        st.subheader("💾 データ出力")
        
        names = list(monitors.keys())
        headers = build_headers(names)
        
        # CSVデータを生成
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in st.session_state.all_rows:
            # 行の列数をヘッダーに合わせる
            padded = row + [""] * (len(headers) - len(row)) if len(row) < len(headers) else row[:len(headers)]
            writer.writerow(padded)
        
        csv_data = output.getvalue()
        
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv_data.encode("utf-8-sig"),  # Excel対応BOM付きUTF-8
            file_name=f"youtube_livestat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=False,
        )
        
        with st.expander("プレビュー（最新10件）"):
            preview_rows = []
            for r in st.session_state.all_rows[-10:]:
                padded = r + [""] * (len(headers) - len(r)) if len(r) < len(headers) else r[:len(headers)]
                preview_rows.append(padded)
            df = pd.DataFrame(preview_rows, columns=headers)
            st.dataframe(df, use_container_width=True)

    # ─── 自動更新ループ ───
    if st.session_state.monitoring:
        fetch_all_stats()
        time.sleep(st.session_state.fetch_interval)
        st.rerun()


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────
render_sidebar()
render_main()
