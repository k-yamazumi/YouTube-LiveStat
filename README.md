# YouTube LiveStat 📊

YouTube Live の同時接続数をリアルタイムで監視・記録するツール。

## 機能

- **リアルタイム監視**: 同時視聴者数・高評価数・コメント数を定期取得
- **複数URL対応**: 複数の配信を並行して監視・比較
- **グラフ表示**: Plotly による対話的なリアルタイムグラフ
- **CSV出力**: 全データを CSV でダウンロード
- **スプレッドシート連携**: Google Sheets にリアルタイム書き込み
- **メール通知**: 定期的にレポートメールを自動送信

## ローカル起動

```bash
pip install -r requirements.txt
streamlit run Streamlit/app.py
```

## Streamlit Cloud デプロイ

1. GitHub にプッシュ
2. [Streamlit Cloud](https://share.streamlit.io/) でリポジトリを接続
3. Main file path → `Streamlit/app.py`
4. **Settings → Secrets** に以下を設定

## Secrets 設定一覧

| キー | 必須 | 説明 |
|------|------|------|
| `YOUTUBE_API_KEY` | ✅ | YouTube Data API v3 のAPIキー |
| `[gcp_service_account]` | スプレッドシート利用時 | GCPサービスアカウントのJSONキー内容 |
| `SMTP_EMAIL` | メール通知利用時 | 送信元Gmailアドレス |
| `SMTP_PASSWORD` | メール通知利用時 | Gmailアプリパスワード |

### secrets.toml の例

```toml
YOUTUBE_API_KEY = "your-api-key"

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "xxx@xxx.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
universe_domain = "googleapis.com"

SMTP_EMAIL = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-password"
```

> **Note**: スプレッドシート連携を使う場合、**共有**->一般的なアクセスで**リンクを知っている全員**を**編集者**にしてください
