from datetime import datetime

from sqlalchemy import Column, ForeignKey,Integer,String,Enum,Boolean,DateTime,Float,Date,Text
from database import Base
import enum
from sqlalchemy.orm import relationship


class UserRole(str,enum.Enum):
    farmer = "farmer"
    buyer = "buyer"
    admin = "admin"


class User(Base):
    __tablename__="users"
    id = Column(Integer,primary_key=True,index=True)
    full_name= Column(String,nullable=False)
    email = Column(String,unique=True,nullable=True)
    hashed_password = Column(String,nullable=True)
    role = Column(Enum(UserRole),default=UserRole.farmer)
    phone = Column(String,nullable=True,unique=True,index=True)
    location = Column(String,nullable=True)
    profile_picture = Column(String,nullable=True)

    products = relationship("Product" ,back_populates="farmer")
    reviews = relationship("Review", back_populates="user")
    orders = relationship("Order", back_populates="buyer")

from sqlalchemy import JSON
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)          # उत्पादनाचे नाव (टोमॅटो, कांदा)
    category = Column(String, nullable=True)       # भाजी, फळ, धान्य
    price = Column(Integer, nullable=False)        # किंमत प्रति किलो/डझन
    unit = Column(String, default="kg")            # kg, dozen, piece
    quantity = Column(Integer, nullable=False)     # उपलब्ध प्रमाण (kg मध्ये)
    description = Column(String, nullable=True)    # थोडक्यात माहिती
    image_urls = Column(Text, default="[]")      # पर्यायी फोटो
    location = Column(JSON,  default=list ,nullable=True)       # शेताचे ठिकाण
    is_available = Column(Boolean, default=True)   # स्टॉक मध्ये आहे का?
    created_at = Column(DateTime, default=datetime.utcnow)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # रिलेशनशिप (User शी)
    farmer = relationship("User", back_populates="products")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")


from datetime import datetime

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_amount = Column(Float, default=0.0)
    status = Column(String, default="pending")  # pending, confirmed, shipped, delivered, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    delivery_date = Column(Date,nullable=True)

    payment_method = Column(String, default="cod")

    advance_paid = Column(Float,default=0.0)
    pending_amount = Column(Float , default=0.0)
    razorpay_order_id = Column(String,nullable=True)

    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)  # snapshot of price at order time

    order = relationship("Order", back_populates="items")
    product = relationship("Product")



class Review(Base):
    __tablename__="reviews"
    id = Column(Integer,primary_key=True,index=True)
    product_id = Column(Integer,ForeignKey("products.id"),nullable=False)
    user_id = Column(Integer,ForeignKey("users.id"),nullable=False)
    rating = Column(Integer,nullable=False)
    comment=Column(Text,nullable=True)
    created_at = Column(DateTime,default=datetime.utcnow)

    product = relationship("Product" , back_populates="reviews")
    user = relationship("User",back_populates="reviews")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])