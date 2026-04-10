import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# .env फाइलचा योग्य पाथ शोधा (backend फोल्डर)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)

# क्रेडेन्शियल्स मिळवा
EMAIL = os.getenv("SMTP_SENDER")
PASSWORD = os.getenv("SMTP_PASSWORD")

# टेस्टिंगसाठी फॉलबॅक (तुझे दिलेले क्रेडेन्शियल्स)
if not EMAIL or not PASSWORD:
    EMAIL = "pankajbidgar07@gmail.com"
    PASSWORD = "ahku obas jrhu dhah"
    print("⚠️ Using hardcoded email credentials (for testing only).")

def send_otp_email(to_email: str, otp: str):
    if not EMAIL or not PASSWORD:
        print("❌ Email credentials missing. Cannot send email.")
        return False

    subject = f"{otp} is your verification code"
    
    html_body = f"""
    <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7ff; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 40px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #eef2f6;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background-color: #2e7d32; width: 60px; height: 60px; border-radius: 15px; display: inline-block; line-height: 60px; color: white; font-size: 30px; font-weight: bold;">
                        🌾
                    </div>
                    <h2 style="color: #1e293b; margin-top: 20px; font-size: 24px; font-weight: 800;">Forgot Password?</h2>
                    <p style="color: #64748b; font-size: 14px;">Please use the following One-Time Password (OTP) to reset your password.</p>
                </div>
                
                <div style="background-color: #f8fafc; border: 2px dashed #e2e8f0; border-radius: 15px; padding: 20px; text-align: center; margin: 30px 0;">
                    <span style="font-size: 36px; font-weight: 900; letter-spacing: 10px; color: #2e7d32;">{otp}</span>
                </div>
                
                <p style="color: #94a3b8; font-size: 12px; text-align: center; line-height: 1.5;">
                    This code is valid for 10 minutes. If you didn't request this, please ignore this email.
                </p>
                
                <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 30px 0;">
                
                <p style="color: #cbd5e1; font-size: 10px; text-align: center; text-transform: uppercase; letter-spacing: 1px;">
                    शेतकरी बाजार © 2026
                </p>
            </div>
        </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"शेतकरी बाजार <{EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"✅ OTP email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False