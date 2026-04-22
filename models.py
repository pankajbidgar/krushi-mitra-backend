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
    expenses = relationship("FarmExpense", back_populates="farmer", cascade="all, delete-orphan")
    tasks = relationship("FarmTask", back_populates="farmer", cascade="all, delete-orphan")
    irrigation_schedules = relationship("IrrigationSchedule", back_populates="farmer", cascade="all, delete-orphan")
    yield_predictions = relationship("YieldPrediction", back_populates="farmer", cascade="all, delete-orphan")

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
    auction = relationship("Auction", back_populates="product", uselist=False, cascade="all, delete-orphan")

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






class FarmExpense(Base):
    __tablename__ = "farm_expenses"
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    land_name = Column(String, nullable=True)           # शेताचे नाव / तुकडा
    crop_name = Column(String, nullable=True)           # पीक (टोमॅटो, कांदा)
    category = Column(String, nullable=False)           # seeds, fertilizer, labor, equipment, other
    description = Column(String, nullable=True)         # तपशील
    quantity = Column(Float, nullable=True)             # प्रमाण (kg, liter, etc.)
    unit = Column(String, nullable=True)                # kg, liter, piece
    amount = Column(Float, nullable=False)              # एकूण रक्कम
    payment_method = Column(String, default="cash")     # cash, bank, credit
    receipt_url = Column(String, nullable=True)         # पावतीचा फोटो URL
    date = Column(Date, nullable=False)
    is_recurring = Column(Boolean, default=False)       # आवर्ती खर्च?
    recurring_interval = Column(String, nullable=True)  # monthly, yearly
    created_at = Column(DateTime, default=datetime.utcnow)
    payment_status = Column(String, default="paid")  # paid, pending

    farmer = relationship("User", back_populates="expenses")






class FarmTask(Base):
    __tablename__ = "farm_tasks"
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    crop_name = Column(String, nullable=True)
    land_name = Column(String, nullable=True)
    due_date = Column(Date, nullable=False)
    status = Column(String, default="pending")  # pending, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    farmer = relationship("User", back_populates="tasks")



class IrrigationSchedule(Base):
    __tablename__ = "irrigation_schedules"
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    land_name = Column(String, nullable=True)          # शेताचे नाव
    crop_name = Column(String, nullable=True)          # पीक
    irrigation_method = Column(String, default="drip") # drip, sprinkler, flood
    last_irrigation_date = Column(Date, nullable=True)
    next_irrigation_date = Column(Date, nullable=False)
    interval_days = Column(Integer, default=3)         # किती दिवसांनी सिंचन करायचे
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("User", back_populates="irrigation_schedules")



class YieldPrediction(Base):
    __tablename__ = "yield_predictions"
    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crop_name = Column(String, nullable=False)
    land_area = Column(Float, nullable=False)  # शेताचे क्षेत्रफळ (हेक्टरीमध्ये)
    soil_type = Column(String, nullable=True)  # मातीचा प्रकार
    seed_type = Column(String, nullable=True)  # बियाण्याचा प्रकार
    irrigation_method = Column(String, nullable=True)  # सिंचन पद्धत
    season= Column(String, nullable=True)  # हंगाम (उदा. रब्बी, खरीफ)
    predicted_yield = Column(Float, nullable=True)  # अंदाजे उत्पादन (किलोमध्ये)
    created_at = Column(DateTime, default=datetime.utcnow)

    farmer = relationship("User",back_populates="yield_predictions")




class Auction(Base):
    __tablename__ = "auctions"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    starting_bid = Column(Float, nullable=False)
    current_bid = Column(Float, nullable=True)
    highest_bidder_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # start_time = Column(DateTime, nullable=False)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    status = Column(String, default="active")  # active, completed, cancelled   
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    winner = relationship("User", foreign_keys=[winner_id])

    product = relationship("Product",back_populates="auction")
    seller = relationship("User", foreign_keys=[seller_id])
    highest_bidder = relationship("User", foreign_keys=[highest_bidder_id])
    bids = relationship("AuctionBid", back_populates="auction", cascade="all, delete-orphan")


class AuctionBid(Base):
    __tablename__="auction_bids"
    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("auctions.id"), nullable=False)
    bidder_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    auction = relationship("Auction", back_populates="bids")
    bidder = relationship("User", foreign_keys=[bidder_id])




class GovScheme(Base):
    __tablename__ = "gov_schemes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)           # योजना का नाव
    description = Column(Text, nullable=True)      # योजना का तपशील
    eligibility = Column(Text, nullable=True)      # पात्रता निकष
    benefits = Column(Text, nullable=True)         # योजना का लाभ
    apply_link = Column(String, nullable=True)      # अर्ज करण्याचा लिंक
    category = Column(String, nullable=True)         # योजना का प्रकार (उदा. कर्ज, सबसिडी, प्रशिक्षण)
    crop_type = Column(String, nullable=True)       # योजना कोणत्या पिकांसाठी आहे (उदा. धान्य, भाजी)
    min_land_area = Column(Float, nullable=True)       # किमान शेताचे क्षेत्रफळ
    created_at = Column(DateTime, default=datetime.utcnow)