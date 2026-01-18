"""
ai_news_mailer.py

NewsAPI を使って AI 関連のニュースを取得し、整形した本文を Gmail(SMTP) 経由で
自分宛にメール送信するスクリプト。

想定用途:
- ローカル実行（.env を利用）
- GitHub Actions 等での定期実行（環境変数 / Secrets を利用）

必要な環境変数:
- NEWS_API_KEY: NewsAPI の API Key
- GMAIL_ADDRESS: 送信元/送信先の Gmail アドレス（このスクリプトは自分宛に送る）
- GMAIL_APP_PASSWORD: Gmail のアプリパスワード（SMTPログイン用）
"""

import os
import requests
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from datetime import date

# ローカル開発時は .env から環境変数を読み込む。
# GitHub Actions 等では .env を使わず、Secrets -> env 経由で注入する想定。
load_dotenv()

# Secrets / 環境変数から取得（コードに直書きしない）
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# 「AI関連」の判定に使うキーワード（英語/日本語）
KEYWORDS = [
    "artificial intelligence",
    "openai",
    "chatgpt",
    "llm",
    "生成ai",
    "人工知能",
]


def is_ai_related(article: dict) -> bool:
    """
    NewsAPI の article（辞書）が AI 関連かどうかを判定する。

    判定方法:
    - article の title / description / content を連結して小文字化
    - KEYWORDS のいずれかが含まれていれば True

    Args:
        article: NewsAPI の articles 配列要素（dict）

    Returns:
        AI 関連と判定できる場合 True、それ以外 False
    """
    text = " ".join(
        [
            article.get("title", ""),
            article.get("description", "") or "",
            article.get("content", "") or "",
        ]
    ).lower()

    return any(k.lower() in text for k in KEYWORDS)


def build_email_body(articles: list[dict]) -> str:
    """
    記事一覧からメール本文（プレーンテキスト）を生成する。

    本文フォーマット:
    - 先頭に日付と件数
    - 記事ごとに「タイトル / description（あれば） / URL（あれば）」を列挙
    - 記事が0件のときは「見つかりませんでした」メッセージ

    Args:
        articles: NewsAPI の articles をフィルタしたリスト

    Returns:
        メール本文文字列（UTF-8想定）
    """
    today = date.today().isoformat()

    if not articles:
        return f"{today}\n\n本日はAI関連の新着ニュースは見つかりませんでした。"

    lines = [f"{today} / AI関連ニュース {len(articles)}件", ""]

    for a in articles:
        title = a.get("title", "(no title)")
        desc = a.get("description") or ""
        url = a.get("url", "")

        lines.append(f"■ {title}")
        if desc:
            lines.append(desc)
        if url:
            lines.append(url)
        lines.append("")

    return "\n".join(lines)


def send_email(body: str) -> None:
    """
    Gmail(SMTP over SSL) を使って、生成した本文を自分宛にメール送信する。

    注意:
    - Gmail の通常パスワードではなく、アプリパスワードを利用する想定。
    - 送信先(To)も自分自身にして、通知用途で使う。

    Args:
        body: 送信する本文（プレーンテキスト）

    Raises:
        RuntimeError: 必要な環境変数が不足している場合
        smtplib.SMTPException: SMTP送信に失敗した場合（実際は下位例外が上がる）
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_ADDRESS or GMAIL_APP_PASSWORD is not set")

    today = date.today().isoformat()
    subject = f"Daily AI News - {today}"

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)


def request_news(language: str) -> list[dict]:
    """
    NewsAPI の /v2/everything を利用してニュース記事を取得する。

    検索条件:
    - AI関連キーワードを OR 条件で指定（英日ミックス）
    - language を "ja" / "en" で切り替え
    - title と description のみ検索対象（searchIn="title,description"）
    - 新着順（publishedAt）
    - 最大 10 件（pageSize=10）

    Args:
        language: 取得言語（"ja" または "en" を想定）

    Returns:
        NewsAPI が返す articles の配列（各要素は dict）

    Raises:
        RuntimeError: NEWS_API_KEY が設定されていない場合
        requests.HTTPError: NewsAPI がエラーを返した場合（raise_for_status）
        requests.RequestException: 通信エラーやタイムアウト等
    """
    if not NEWS_API_KEY:
        raise RuntimeError("NEWS_API_KEY is not set")

    url = "https://newsapi.org/v2/everything"

    # 日本語でも英語でも効くように、クエリは英日ミックス
    params = {
        "q": '("artificial intelligence" OR OpenAI OR ChatGPT OR LLM OR 生成AI OR 人工知能)',
        "language": language,  # "ja" / "en"
        "searchIn": "title,description",
        "sortBy": "publishedAt",
        "pageSize": 10,
        "apiKey": NEWS_API_KEY,
    }

    res = requests.get(url, params=params, timeout=20)
    res.raise_for_status()
    return res.json().get("articles", [])


def main() -> None:
    """
    エントリポイント。

    処理の流れ:
    1. 日本語でニュース取得 → AI関連フィルタ
    2. 0件なら英語でニュース取得 → AI関連フィルタ（救済）
    3. メール本文生成
    4. Gmail で送信
    """
    # まず日本語で取得→フィルタ
    articles = [a for a in request_news("ja") if is_ai_related(a)]

    # フィルタ後0件なら英語で救済
    if not articles:
        articles = [a for a in request_news("en") if is_ai_related(a)]

    body = build_email_body(articles)
    send_email(body)


if __name__ == "__main__":
    main()
