"""邮件发送 — SMTP → Kindle EPUB 推送。支持 CLI 调用。"""
import argparse
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from datetime import datetime, date
from pathlib import Path
from config import KINDLE_EMAIL, SMTP_USER, SMTP_PASS, SMTP_HOST, SMTP_PORT

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"


def find_epub(issue_date: str = None) -> Path | None:
    """Find the EPUB file for a given issue date (default: today)."""
    if issue_date is None:
        issue_date = date.today().isoformat()
    epub_path = OUTPUT_DIR / f"三千要看-{issue_date}.epub"
    if epub_path.exists():
        return epub_path
    return None


def send_epub(epub_path: str, max_retries: int = 3) -> bool:
    if not KINDLE_EMAIL or not SMTP_USER or not SMTP_PASS:
        logger.error("Missing email config. Check .env")
        return False

    for attempt in range(1, max_retries + 1):
        try:
            msg = MIMEMultipart("mixed")
            msg["From"] = SMTP_USER
            msg["To"] = KINDLE_EMAIL
            msg["Subject"] = "三千要看"

            body = f"三千要看 — {datetime.now().strftime('%Y-%m-%d')}"
            msg.attach(MIMEText(body, "plain", "utf-8"))

            filename = epub_path.split("/")[-1]
            with open(epub_path, "rb") as f:
                epub_data = f.read()

            attachment = MIMEApplication(epub_data, "epub+zip")
            attachment.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(attachment)

            if SMTP_PORT == 465:
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_USER, [KINDLE_EMAIL], msg.as_string())
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASS)
                    server.sendmail(SMTP_USER, [KINDLE_EMAIL], msg.as_string())

            logger.info(f"Sent {filename} to {KINDLE_EMAIL}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP auth failed. Check SMTP_USER/PASS.")
            return False
        except Exception as e:
            logger.warning(f"Send error (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(30)

    logger.error(f"Failed after {max_retries} attempts")
    return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="三千要看 Kindle 推送")
    parser.add_argument("--issue-date", default=None, help="Issue date in YYYY-MM-DD (default: latest)")
    args = parser.parse_args()

    epub_path = find_epub(args.issue_date)
    if not epub_path:
        issue_str = args.issue_date or date.today().isoformat()
        logger.error(f"No EPUB found for issue {issue_str}")
        exit(1)

    ok = send_epub(str(epub_path))
    exit(0 if ok else 1)
