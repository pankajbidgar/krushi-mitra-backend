from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from enum import Enum
from models import UserRole

class UserRole(str,Enum):
    farmer = "farmer"
    buyer = "buyer"

class UserCreate(BaseModel):
    full_name : str
    email : EmailStr
    password : str
    role : UserRole
    phone :Optional[str] =None
    location :Optional[str] =None

class UserLogin(BaseModel):
    email :EmailStr
    password : str

class UserOut(BaseModel):
    id:int
    full_name: str
    email:Optional[str] =None
    role:str
    phone:Optional[str]
    location:Optional[str]
    profile_picture: Optional[str] = None 

class Token(BaseModel):
    access_token:str
    token_type:str


class MobileLoginRequest(BaseModel):
    phone:str
    password:str

class MobileOtpRequest(BaseModel):
    phone:str

class MobileOtpVerifyRequest(BaseModel):    
    phone:str
    opt:str

class MobileRegisterRequest(BaseModel):
    phone:str
    full_name:str
    password:Optional[str] = None
    role:str="farmer"
    location:Optional[str] = None


from datetime import datetime,date
from typing import Optional

class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None
    price: float
    unit: str = "kg"
    quantity: float
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None
    location: Optional[str] = None

class ProductOut(BaseModel):
    id: int
    name: str
    category: Optional[str]
    price: float
    unit: str
    quantity: float
    description: Optional[str]
    image_urls: Optional[List[str]] = None
    location: Optional[str]
    is_available: bool
    created_at: datetime
    farmer_id: int
    # farmer details for display
    farmer_name: Optional[str] = None
    avg_rating:Optional[float]=None
    review_count:Optional[int] =None

    class Config:
        from_attributes = True



class OrderItemCreate(BaseModel):
    product_id: int
    quantity: float

class OrderCreate(BaseModel):
    items: List[OrderItemCreate]
    payment_method : str = "cod"
    advance_percent : Optional[float] = 30.0

class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: float
    price: float

class OrderOut(BaseModel):
    id: int
    total_amount: float
    status: str
    created_at: datetime
    delivery_date:Optional[date]= None
    items: List[OrderItemOut] = []
    payment_method :str
    advance_paid:float
    pending_amount:float
    buyer_id: int
    items:List[OrderItemOut] = []
    
    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    product_id :int
    rating:int=Field(...,ge=1,le=5)
    comment:Optional[str] =None


class ReviewOut(BaseModel):
    id:int
    product_id:int
    user_id : int
    user_name:Optional[str]=None
    rating:str
    comment:Optional[str]
    created_at :datetime



class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    profile_picture: Optional[str] = None




class ChatMessageCreate(BaseModel):
    receiver_id: int
    message: str

class ChatMessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    message: str
    is_read: bool
    created_at: datetime
    sender_name: Optional[str] = None
    receiver_name: Optional[str] = None



class EmailRequest(BaseModel):
    email: str

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str





class CropRecommendationRequest(BaseModel):
    soil_type: str  # "काळी", "लाल", "वालुकामय", "चिकणमाती"
    season: str     # "खरीप", "रब्बी", "उन्हाळी"
    water: str      # "भरपूर", "मध्यम", "कमी"




# 579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b



class FarmExpenseCreate(BaseModel):
    land_name: Optional[str] = None
    crop_name: Optional[str] = None
    category: str
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    amount: float
    payment_method: Optional[str] = "cash"
    receipt_url: Optional[str] = None
    date: date
    is_recurring: Optional[bool] = False
    recurring_interval: Optional[str] = None
    payment_status: Optional[str] = "paid" 

class FarmExpenseOut(BaseModel):
    id: int
    land_name: Optional[str]
    crop_name: Optional[str]
    category: str
    description: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    amount: float
    payment_method: Optional[str]
    receipt_url: Optional[str]
    date: date
    is_recurring: Optional[bool] = False
    recurring_interval: Optional[str]
    payment_status: Optional[str] = "paid"



class ProfitLossResponse(BaseModel):
    total_revenue: float
    total_expenses: float
    profit: float
    expense_breakdown: dict               # category wise
    land_breakdown: dict                  # land_name wise
    crop_breakdown: dict                  # crop_name wise





from datetime import date

class FarmTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    crop_name: Optional[str] = None
    land_name: Optional[str] = None
    due_date: date

class FarmTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    crop_name: Optional[str] = None
    land_name: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None

class FarmTaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    crop_name: Optional[str]
    land_name: Optional[str]
    due_date: date
    status: str
    created_at: datetime


from typing import Dict, List, Optional
from datetime import date, datetime

class ProfitReportFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    crop_name: Optional[str] = None
    land_name: Optional[str] = None

class MonthlyProfit(BaseModel):
    month: str  # "2025-01"
    revenue: float
    expenses: float
    profit: float

class ProfitReportResponse(BaseModel):
    total_revenue: float
    total_expenses: float
    profit: float
    monthly_breakdown: List[MonthlyProfit]
    crop_breakdown: Dict[str, float]   # crop_name -> profit (revenue - expenses for that crop)
    land_breakdown: Dict[str, float]   # land_name -> profit
    expense_breakdown: Dict[str, float]  # category wise expenses





from datetime import date

class IrrigationScheduleCreate(BaseModel):
    land_name: Optional[str] = None
    crop_name: Optional[str] = None
    irrigation_method: str = "drip"
    last_irrigation_date: Optional[date] = None
    next_irrigation_date: date
    interval_days: int = 3
    is_active: bool = True

class IrrigationScheduleUpdate(BaseModel):
    land_name: Optional[str] = None
    crop_name: Optional[str] = None
    irrigation_method: Optional[str] = None
    last_irrigation_date: Optional[date] = None
    next_irrigation_date: Optional[date] = None
    interval_days: Optional[int] = None
    is_active: Optional[bool] = None

class IrrigationScheduleOut(BaseModel):
    id: int
    land_name: Optional[str]
    crop_name: Optional[str]
    irrigation_method: str
    last_irrigation_date: Optional[date]
    next_irrigation_date: date
    interval_days: int
    is_active: bool
    created_at: datetime



class YieldPredictionRequest(BaseModel):
    crop_name: str
    land_area: float  # in hectares
    soil_type: Optional[str] = None
    seed_type: Optional[str] = None
    irrigation_method: Optional[str] = None
    season: Optional[str] = None  # हंगाम (उदा. रब्बी, खरीफ)

class YieldPredictionResponse(BaseModel):
    predicted_yield: float  # in kilograms
    confidence: Optional[float] = None  # model confidence score (0-1)
    factors:List[str]


class YieldPredictionOut(BaseModel):
    id: int
    crop_name: str
    land_area: float
    soil_type: Optional[str]
    seed_type: Optional[str]
    irrigation_method: Optional[str]
    season: Optional[str]
    predicted_yield: Optional[float]
    created_at: datetime



class AuctionCreate(BaseModel):
    product_id: int
    starting_bid: float
    end_time: datetime

class AuctionBidCreate(BaseModel):

    amount: float


class AuctionOut(BaseModel):
    id: int
    product_id: int
    product_name:str
    seller_id:int
    seller_name:str
    starting_bid:float
    current_bid:float
    highest_bidder_id:Optional[int]
    highest_bidder_name:Optional[str]
    end_time: datetime
    start_time: datetime
    is_active: bool
    bid_count: int

    status : str
    winner_id: Optional[int]
    winner_name: Optional[str]


class AuctionBidOut(BaseModel):
    id: int
    auction_id: int
    bidder_id: int
    bidder_name: str
    amount: float
    created_at: datetime    



class SchemeFinderInput(BaseModel):
    crop_name:str
    land_area:float
    district:Optional[str] = None
    annual_income:Optional[float] = None
    

class GovSchemeOut(BaseModel):
    id:int
    name:str
    description:Optional[str]
    eligibility:Optional[str]
    benefits:Optional[str]
    apply_link:Optional[str]
    category:Optional[str]
