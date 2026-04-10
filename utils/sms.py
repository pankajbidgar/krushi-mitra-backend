

# # utils/sms.py
# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")

# def send_otp_sms(phone_number: str, otp: str):
#     """Sends OTP using Fast2SMS API"""
#     if not FAST2SMS_API_KEY:
#         print("⚠️ Fast2SMS API key is missing. OTP will not be sent.")
#         return False

#     url = "https://www.fast2sms.com/dev/bulkV2"
#     payload = f"variables_values={otp}&route=otp&numbers={phone_number}"
#     headers = {
#         'authorization': FAST2SMS_API_KEY,
#         'Content-Type': "application/x-www-form-urlencoded",
#         'Cache-Control': "no-cache"
#     }

#     try:
#         response = requests.request("POST", url, data=payload, headers=headers)
#         response_data = response.json()
        
#         if response_data.get('return'):
#             print(f"✅ OTP sent successfully to {phone_number}")
#             return True
#         else:
#             print(f"❌ Fast2SMS Error: {response_data}")
#             return False
#     except Exception as e:
#         print(f"❌ Error sending SMS: {e}")
#         return False






import os
import requests
from dotenv import load_dotenv

load_dotenv()

FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")

def send_otp_sms(phone: str, otp: str) -> bool:
    if not FAST2SMS_API_KEY:
        print("⚠️ Fast2SMS API key missing")
        return False

    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = f"variables_values={otp}&route=otp&numbers={phone}"
    headers = {
        'authorization': FAST2SMS_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        result = response.json()
        if result.get('return'):
            print(f"✅ OTP sent to {phone}")
            return True
        else:
            print(f"❌ Fast2SMS error: {result}")
            return False
    except Exception as e:
        print(f"❌ SMS exception: {e}")
        return False