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