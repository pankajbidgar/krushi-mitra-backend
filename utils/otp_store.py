# Simple in-memory store (for development)
# In production, use Redis or database
otp_store = {}  # {email: otp}


phone_otp_store = {}  # phone -> otp