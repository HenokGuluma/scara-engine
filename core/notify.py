"""Delivers the PDF to Telegram and/or email — whichever secrets you set."""
import os
import smtplib
from email.message import EmailMessage

import requests


def send(pdf_path, caption):
    sent = []
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        with open(pdf_path, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendDocument",
                              data={"chat_id": chat, "caption": caption[:1000]},
                              files={"document": (os.path.basename(pdf_path), f, "application/pdf")}, timeout=60)
        print("[notify] telegram:", "ok" if r.ok else f"failed ({r.status_code})")
        sent.append("telegram" if r.ok else "telegram-failed")
    user, pw, to = (os.environ.get("EMAIL_USER"), os.environ.get("EMAIL_APP_PASSWORD"),
                    os.environ.get("EMAIL_TO") or os.environ.get("EMAIL_USER"))
    if user and pw:
        msg = EmailMessage()
        msg["Subject"], msg["From"], msg["To"] = caption.split("\n")[0], user, to
        msg.set_content(caption)
        with open(pdf_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf",
                               filename=os.path.basename(pdf_path))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
            smtp.login(user, pw)
            smtp.send_message(msg)
        print("[notify] email: ok")
        sent.append("email")
    if not sent:
        print("[notify] No TELEGRAM_* or EMAIL_* secrets set — report built but not delivered.")
    return sent


def ping(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if tok and chat:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          data={"chat_id": chat, "text": text}, timeout=30)
        return r.ok
    return False
