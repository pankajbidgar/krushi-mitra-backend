import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("SMTP_SENDER")
PASSWORD = os.getenv("SMTP_PASSWORD")

def send_generic_email(to_email: str, subject: str, html_body: str):
    if not EMAIL or not PASSWORD:
        print("⚠️ Email credentials missing")
        return False
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = f"शेतकरी बाजार <{EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False