import os
import requests
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
from datetime import date

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

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
    タイトル + description を小文字化して、KEYWORDS のどれかが含まれていればAI関連と判定
    """
    text = " ".join([
        article.get("title", ""),
        article.get("description", "") or "",
        article.get("content", "") or "",
    ]).lower()

    return any(k.lower() in text for k in KEYWORDS)


def build_email_body(articles: list[dict]) -> str:
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
    if not NEWS_API_KEY:
        raise RuntimeError("NEWS_API_KEY is not set")

    url = "https://newsapi.org/v2/everything"

    # 日本語でも英語でも効くように、クエリは英日ミックス
    params = {
    "q": '("artificial intelligence" OR OpenAI OR ChatGPT OR LLM OR 生成AI OR 人工知能)',
    "language": language,         # "ja" / "en"
    "searchIn": "title,description",
    "sortBy": "publishedAt",
    "pageSize": 10,
    "apiKey": NEWS_API_KEY,
    }

    res = requests.get(url, params=params, timeout=20)
    res.raise_for_status()
    return res.json().get("articles", [])


if __name__ == "__main__":
    # まず日本語で取得→フィルタ
    articles = [a for a in request_news("ja") if is_ai_related(a)]

    # フィルタ後0件なら英語で救済
    if not articles:
        articles = [a for a in request_news("en") if is_ai_related(a)]

    body = build_email_body(articles)
    send_email(body)
