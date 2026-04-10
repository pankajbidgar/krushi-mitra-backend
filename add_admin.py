from database import SessionLocal
from models import User, UserRole
from auth import get_Password_hashed

db = SessionLocal()

# Admin यूजर तयार करा
admin = User(
    full_name="Admin User",
    email="admin@gmail.com",
    hashed_password=get_Password_hashed("1234"),  # तुमचा पासवर्ड
    role=UserRole.admin,
    phone="9999999999",
    location="Pune"
)

db.add(admin)
db.commit()
print("✅ Admin user created successfully!")
print("Email: admin@example.com")
print("Password: admin123")