import uuid
import os
import shutil
import json
from typing import List
from datetime import datetime, timedelta
from models import ChatMessage   

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func

import models, database, schemas, auth
from models import *
from database import get_db

import razorpay
import socketio
import uvicorn

# ------------------- App Initialization -------------------
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------- Socket.IO Setup -------------------
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
socket_app = socketio.ASGIApp(sio, app)

# Store user socket ids
user_sid_map = {}

@sio.event
async def connect(sid, environ):
    print(f"Client Connected: {sid}")

@sio.event
async def disconnect(sid):
    for uid, s in list(user_sid_map.items()):
        if s == sid:
            del user_sid_map[uid]
            break

@sio.event
async def register_user(sid, data):
    user_id = data.get("user_id")
    if user_id:
        user_sid_map[user_id] = sid
        print(f"User {user_id} registered with sid {sid}")

# ------------------- Razorpay Client -------------------
client = razorpay.Client(auth=("YOUR_KEY_ID", "YOUR_KEY_SECRET"))

# ------------------- User Endpoints -------------------

from utils.email_templates import get_welcome_email
from utils.email_sender import send_generic_email

@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = auth.get_user_by_email(db, user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = auth.get_Password_hashed(user.password)

    phone = user.phone if user.phone and user.strip() else None
    db_user = models.User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed,
        role=user.role,
        phone=phone,
        location=user.location
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    
    try:
        send_generic_email(user.email, "शेतकरी बाजार मध्ये स्वागत आहे", get_welcome_email(user.full_name))
    except Exception as e:
        print(f"Welcome email failed: {e}")  # पर्यायी: लॉग करा, पण रजिस्टरेशन रोखू नका
    
    return db_user

@app.post("/login", response_model=schemas.Token)
def login(user_creds: schemas.UserLogin, db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, user_creds.email, user_creds.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.UserOut)
def read_me(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        "phone": current_user.phone,
        "location": current_user.location,
        "profile_picture": current_user.profile_picture,   
    }

@app.get("/farmer-only")
def farmer_endpoint(current_user: models.User = Depends(auth.get_current_farmer)):
    return {"message": f"Welcome farmer {current_user.full_name}"}

@app.get("/buyer-only")
def buyer_endpoint(current_user: models.User = Depends(auth.get_current_buyer)):
    return {"message": f"Welcome buyer {current_user.full_name}"}

# ------------------- Upload Endpoints -------------------
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")
    file_ext = file.filename.split(".")[-1]
    safe_filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file_url = f"/uploads/{safe_filename}"
    return {"image_url": file_url}

@app.post("/upload-multiple/")
async def upload_multiple_images(files: List[UploadFile] = File(...)):
    saved_paths = []
    for file in files:
        if not file.content_type.startswith("image/"):
            continue
        file_ext = file.filename.split(".")[-1]
        safe_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_url = f"/uploads/{safe_filename}"
        saved_paths.append(file_url)
    return {"image_urls": saved_paths}

# ------------------- Product Endpoints -------------------
@app.post("/products", response_model=schemas.ProductOut)
def create_product(
    product: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    product_dict = product.dict()
    if "image_urls" in product_dict and isinstance(product_dict["image_urls"], list):
        product_dict["image_urls"] = json.dumps(product_dict["image_urls"])
    db_product = models.Product(**product_dict, farmer_id=current_user.id)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    if db_product.image_urls:
        db_product.image_urls = json.loads(db_product.image_urls)
    return db_product

@app.get("/products/my", response_model=List[schemas.ProductOut])
def get_my_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    products = db.query(models.Product).filter(models.Product.farmer_id == current_user.id).all()
    for p in products:
        if p.image_urls:
            p.image_urls = json.loads(p.image_urls)
        else:
            p.image_urls = []
        avg = db.query(func.avg(models.Review.rating)).filter(models.Review.product_id == p.id).scalar()
        count = db.query(func.count(models.Review.id)).filter(models.Review.product_id == p.id).scalar()
        p.avg_rating = float(avg) if avg else None
        p.review_count = count or 0
    return products

from typing import Optional
@app.get("/products", response_model=List[schemas.ProductOut])
def get_all_products(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    category:Optional[str]=None
):
    query = db.query(models.Product).filter(models.Product.is_available == True )

    if category:
        query = query.filter(models.Product.category == category)
    products = query.offset(skip).limit(limit).all()
    for p in products:
        if p.image_urls:
            p.image_urls = json.loads(p.image_urls)
        else:
            p.image_urls = []
        p.farmer_name = p.farmer.full_name if p.farmer else None
        avg = db.query(func.avg(models.Review.rating)).filter(models.Review.product_id == p.id).scalar()
        count = db.query(func.count(models.Review.id)).filter(models.Review.product_id == p.id).scalar()
        p.avg_rating = float(avg) if avg else None
        p.review_count = count or 0
    return products




import qrcode
from io import BytesIO
from fastapi.responses import StreamingResponse

@app.get("/product/qrcode/{product_id}")
def generate_product_qrcode(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    
    product_url = f"http://localhost:3000/buyer/products?productId={product_id}"
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(product_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Return image
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return StreamingResponse(img_bytes, media_type="image/png")

@app.get("/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.image_urls:
        product.image_urls = json.loads(product.image_urls)
    else:
        product.image_urls = []
    if product.farmer:
        product.farmer_name = product.farmer.full_name
    return product

@app.put("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    product_update: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db_product.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    update_dict = product_update.dict()
    if "image_urls" in update_dict and isinstance(update_dict["image_urls"], list):
        update_dict["image_urls"] = json.dumps(update_dict["image_urls"])
    for key, value in update_dict.items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    if db_product.image_urls:
        db_product.image_urls = json.loads(db_product.image_urls)
    else:
        db_product.image_urls = []
    return db_product

@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db_product.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(db_product)
    db.commit()
    return {"message": "Product deleted successfully"}

@app.patch("/products/{product_id}/toggle-status")
def toggle_product_status(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if db_product.farmer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db_product.is_available = not db_product.is_available
    db.commit()
    return {"is_available": db_product.is_available}


from utils.email_templates import get_new_order_email
from utils.email_sender import send_generic_email

@app.post("/orders", response_model=schemas.OrderOut)
async def create_order(
    order: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_buyer)
):
    default_delivery_date = datetime.utcnow().date() + timedelta(days=5)
    new_order = models.Order(
        buyer_id=current_user.id,
        total_amount=0,
        status="pending",
        payment_method=order.payment_method,
        delivery_date=default_delivery_date
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    total = 0.0
    order_items = []
    farmer_emails = set()   

    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if not product.is_available:
            raise HTTPException(status_code=400, detail=f"{product.name} is not available")
        if product.quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient quantity for {product.name}. Available: {product.quantity}")

        # Reduce quantity
        product.quantity -= item.quantity
        if product.quantity == 0:
            product.is_available = False

        order_item = models.OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=item.quantity,
            price=product.price
        )
        db.add(order_item)
        order_items.append(order_item)
        total += product.price * item.quantity

        # Socket notification to farmer
        farmer_id = product.farmer_id
        sid = user_sid_map.get(farmer_id)
        if sid:
            await sio.emit('new_order', {
                'order_id': new_order.id,
                'message': f'नवीन ऑर्डर आला! ऑर्डर # {new_order.id}',
                'total': total
            }, room=sid)

        # Collect farmer email for later
        farmer = db.query(models.User).filter(models.User.id == farmer_id).first()
        if farmer and farmer.email:
            farmer_emails.add(farmer.email)

    new_order.total_amount = total

    if order.payment_method == "cod":
        new_order.advance_paid = 0
        new_order.pending_amount = total
    elif order.payment_method == "online_full":
        new_order.advance_paid = total
        new_order.pending_amount = 0
    elif order.payment_method == "online_advance":
        percent = order.advance_percent if order.advance_percent else 30
        advance = (percent / 100) * total
        new_order.advance_paid = advance
        new_order.pending_amount = total - advance
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    db.commit()
    db.refresh(new_order)

    if order.payment_method in ["online_advance", "online_full"]:
        try:
            razorpay_order = client.order.create({
                "amount": int(new_order.advance_paid * 100),
                "currency": "INR",
                "receipt": f"order_{new_order.id}",
                "payment_capture": 1
            })
            new_order.razorpay_order_id = razorpay_order["id"]
            db.commit()
            db.refresh(new_order)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Razorpay order creation failed: {str(e)}")

    items_out = []
    for oi in order_items:
        prod = db.query(models.Product).filter(models.Product.id == oi.product_id).first()
        items_out.append(schemas.OrderItemOut(
            product_id=oi.product_id,
            product_name=prod.name if prod else "Unknown",
            quantity=oi.quantity,
            price=oi.price
        ))

    response = schemas.OrderOut(
        id=new_order.id,
        total_amount=new_order.total_amount,
        status=new_order.status,
        created_at=new_order.created_at,
        delivery_date=new_order.delivery_date,
        payment_method=new_order.payment_method,
        advance_paid=new_order.advance_paid,
        pending_amount=new_order.pending_amount,
        buyer_id=current_user.id,
        items=items_out
    )

    # ---------- Email Notification to Farmers ----------
    buyer_name = current_user.full_name
    for farmer_email in farmer_emails:
        farmer_user = db.query(models.User).filter(models.User.email == farmer_email).first()
        if farmer_user:
            html = get_new_order_email(farmer_user.full_name, new_order.id, total, buyer_name)
            send_generic_email(farmer_email, f"नवीन ऑर्डर #{new_order.id}", html)



    if order.payment_method in ["online_advance", "online_full"]:
        return {
            **response.dict(),
            "razorpay_order_id": new_order.razorpay_order_id,
            "razorpay_key": "YOUR_KEY_ID",
            "buyer_id":current_user.id
        }
    return response

@app.get("/orders/my", response_model=List[schemas.OrderOut])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_buyer)
):
    orders = db.query(models.Order).filter(models.Order.buyer_id == current_user.id).all()
    result = []
    for order in orders:
        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        items_out = []
        for item in items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            items_out.append(schemas.OrderItemOut(
                product_id=item.product_id,
                product_name=product.name if product else "Unknown",
                quantity=item.quantity,
                price=item.price
            ))
        result.append(schemas.OrderOut(
            id=order.id,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            delivery_date=order.delivery_date,
            payment_method=order.payment_method,
            advance_paid=order.advance_paid,
            pending_amount=order.pending_amount,
            buyer_id = order.buyer_id,
            items=items_out
        ))
    return result

@app.get("/orders/farmer", response_model=List[schemas.OrderOut])
def get_farmer_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    farmer_products = db.query(models.Product).filter(models.Product.farmer_id == current_user.id).all()
    product_ids = [p.id for p in farmer_products]
    if not product_ids:
        return []
    order_items = db.query(models.OrderItem).filter(models.OrderItem.product_id.in_(product_ids)).all()
    order_ids = list(set([oi.order_id for oi in order_items]))
    orders = db.query(models.Order).filter(models.Order.id.in_(order_ids)).all()
    result = []
    for order in orders:
        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        items_out = []
        for item in items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            items_out.append(schemas.OrderItemOut(
                product_id=item.product_id,
                product_name=product.name if product else "Unknown",
                quantity=item.quantity,
                price=item.price
            ))
        result.append(schemas.OrderOut(
            id=order.id,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            delivery_date=order.delivery_date,
            payment_method=order.payment_method,
            advance_paid=order.advance_paid,
            pending_amount=order.pending_amount,
            buyer_id=order.buyer_id,
            items=items_out
        ))
    return result



from utils.email_templates import get_order_status_email
from utils.email_sender import send_generic_email

@app.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if current_user.role == "farmer":
        order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        product_ids = [oi.product_id for oi in order_items]
        farmer_products = db.query(models.Product).filter(
            models.Product.farmer_id == current_user.id,
            models.Product.id.in_(product_ids)
        ).all()
        if not farmer_products:
            raise HTTPException(status_code=403, detail="Not authorized to update this order")
    elif current_user.role == "buyer":
        if order.buyer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    old_status = order.status
    order.status = status
    db.commit()

    # Socket notification to buyer
    buyer_id = order.buyer_id
    sid = user_sid_map.get(buyer_id)
    if sid:
        await sio.emit('order_status_update', {
            'order_id': order.id,
            'status': order.status,
            'message': f'तुमची ऑर्डर # {order.id} आता {order.status} झाली आहे.'
        }, room=sid)

    # ---------- Email Notification to Buyer ----------
    buyer = db.query(models.User).filter(models.User.id == buyer_id).first()
    if buyer and buyer.email:
        html = get_order_status_email(buyer.full_name, order.id, old_status, status)
        send_generic_email(buyer.email, f"ऑर्डर #{order.id} स्टेटस बदलला", html)

    return {"message": "Status updated", "status": order.status}

@app.patch("/orders/{order_id}/delivery-date")
def update_delivery_date(
    order_id: int,
    delivery_date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
    product_ids = [oi.product_id for oi in order_items]
    farmer_products = db.query(models.Product).filter(
        models.Product.farmer_id == current_user.id,
        models.Product.id.in_(product_ids)
    ).first()
    if not farmer_products:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        parsed_date = datetime.strptime(delivery_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    order.delivery_date = parsed_date
    db.commit()
    return {"message": "Delivery date updated", "delivery_date": str(parsed_date)}

# ------------------- Review Endpoints -------------------
@app.post("/reviews")
def create_review(
    review: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_buyer)
):
    order_items = db.query(models.OrderItem).join(models.Order).filter(
        models.Order.buyer_id == current_user.id,
        models.Order.status == "delivered",
        models.OrderItem.product_id == review.product_id
    ).first()
    if not order_items:
        raise HTTPException(status_code=403, detail="You can only review products you have purchased and delivered")
    existing = db.query(models.Review).filter(
        models.Review.product_id == review.product_id,
        models.Review.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")
    db_review = models.Review(
        product_id=review.product_id,
        user_id=current_user.id,
        rating=review.rating,
        comment=review.comment
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return {"message": "Review Added"}

@app.get("/reviews/product/{product_id}", response_model=List[schemas.ReviewOut])
def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    reviews = db.query(models.Review).filter(models.Review.product_id == product_id).all()
    result = []
    for r in reviews:
        user = db.query(models.User).filter(models.User.id == r.user_id).first()
        result.append(schemas.ReviewOut(
            id=r.id,
            product_id=r.product_id,
            user_id=r.user_id,
            user_name=user.full_name if user else "Unknown",
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at
        ))
    return result

@app.get("/reviews/my")
def get_my_reviews(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_buyer)):
    reviews = db.query(models.Review).filter(models.Review.user_id == current_user.id).all()
    return [{"product_id": r.product_id} for r in reviews]

# ------------------- Payment Verification -------------------
@app.post("/verify-payment")
def verify_payment(data: dict, db: Session = Depends(get_db)):
    client.utility.verify_payment_signature({
        'razorpay_order_id': data['razorpay_order_id'],
        'razorpay_payment_id': data['razorpay_payment_id'],
        'razorpay_signature': data['razorpay_signature']
    })
    order = db.query(models.Order).filter(models.Order.id == data['order_id']).first()
    order.status = "confirmed"
    db.commit()
    return {"message": "success"}



# ------------------- Admin Endpoints -------------------
from typing import List
import schemas, models, auth
from sqlalchemy.orm import Session
from database import get_db

@app.get("/admin/users", response_model=List[schemas.UserOut])
def admin_get_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    users = db.query(models.User).all()
    return users

@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
  
    if user.role == models.UserRole.farmer:
        products = db.query(models.Product).filter(models.Product.farmer_id == user_id).all()
        for product in products:
            
            db.query(models.OrderItem).filter(models.OrderItem.product_id == product.id).delete()
            db.delete(product)
    
    if user.role == models.UserRole.buyer:
        orders = db.query(models.Order).filter(models.Order.buyer_id == user_id).all()
        for order in orders:
            db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).delete()
            db.delete(order)
  
    db.delete(user)
    db.commit()
    return {"message": "User and all related data deleted"}

@app.get("/admin/products", response_model=List[schemas.ProductOut])
def admin_get_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    products = db.query(models.Product).all()
    for p in products:
        if p.image_urls:
            p.image_urls = json.loads(p.image_urls)
        else:
            p.image_urls = []
        p.farmer_name = p.farmer.full_name if p.farmer else None
    return products

@app.delete("/admin/products/{product_id}")
def admin_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@app.get("/admin/orders", response_model=List[schemas.OrderOut])
def admin_get_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    orders = db.query(models.Order).all()
    result = []
    for order in orders:
        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        items_out = []
        for item in items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            items_out.append(schemas.OrderItemOut(
                product_id=item.product_id,
                product_name=product.name if product else "Unknown",
                quantity=item.quantity,
                price=item.price
            ))
        result.append(schemas.OrderOut(
            id=order.id,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            delivery_date=order.delivery_date,
            payment_method=order.payment_method,
            advance_paid=order.advance_paid,
            pending_amount=order.pending_amount,
            buyer_id=order.buyer_id,   
            items=items_out
        ))
    return result

@app.patch("/admin/orders/{order_id}/status")
def admin_update_order_status(
    order_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    order.status = status
    db.commit()
    return {"message": "Order status updated"}



@app.get("/test-admin")
def test_admin(current_user: models.User = Depends(auth.get_current_admin)):
    return {"message": "Admin works"}

from datetime import datetime
from sqlalchemy import func

@app.get("/admin/stats")
def admin_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    # Total users
    total_users = db.query(models.User).count()
    
    # Total products
    total_products = db.query(models.Product).count()
    
    # Total orders
    total_orders = db.query(models.Order).count()
    
    # Monthly income (current month)
    today = datetime.utcnow().date()
    first_day = today.replace(day=1)
    monthly_orders = db.query(models.Order).filter(
        models.Order.created_at >= first_day,
        models.Order.status == "delivered"
    ).all()
    monthly_income = sum(o.total_amount for o in monthly_orders)
    
    # Orders by status
    status_counts = db.query(models.Order.status, func.count(models.Order.id)).group_by(models.Order.status).all()
    order_statuses = {status: count for status, count in status_counts}
    
    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_orders": total_orders,
        "monthly_income": monthly_income,
        "order_statuses": order_statuses
    }

@app.patch("/admin/users/{user_id}/role")
def admin_change_role(
    user_id: int,
    new_role: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if new_role not in ["farmer", "buyer", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    user.role = models.UserRole(new_role)
    db.commit()
    return {"message": f"Role updated to {new_role}"}




# ------------------- Profile Endpoints -------------------

@app.get("/profile", response_model=schemas.UserOut)
def get_profile(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        "phone": current_user.phone,
        "location": current_user.location,
        "profile_picture": current_user.profile_picture, 
    }

@app.put("/profile", response_model=schemas.UserOut)
def update_profile(
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    if user_update.phone is not None:
        current_user.phone = user_update.phone
    if user_update.location is not None:
        current_user.location = user_update.location
    if user_update.profile_picture is not None:
        current_user.profile_picture = user_update.profile_picture
    db.commit()
    db.refresh(current_user)
    return current_user

@app.post("/upload-profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")
    file_ext = file.filename.split(".")[-1]
    safe_filename = f"profile_{current_user.id}_{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file_url = f"/uploads/{safe_filename}"
    current_user.profile_picture = file_url
    db.commit()
    return {"profile_picture": file_url}




# ------------------- Chat Endpoints -------------------

@app.get("/users/all")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    users = db.query(models.User).filter(models.User.id != current_user.id).all()
    return [{
        "id": u.id,
        "full_name": u.full_name,
        "role": u.role.value,
        "profile_picture": u.profile_picture
    } for u in users]


@app.get("/chat/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    sent = db.query(models.ChatMessage.receiver_id).filter(models.ChatMessage.sender_id == current_user.id).distinct()
    received = db.query(models.ChatMessage.sender_id).filter(models.ChatMessage.receiver_id == current_user.id).distinct()
    user_ids = set([r[0] for r in sent] + [r[0] for r in received])
    conversations = []
    for uid in user_ids:
        other_user = db.query(models.User).filter(models.User.id == uid).first()
        last_msg = db.query(models.ChatMessage).filter(
            ((models.ChatMessage.sender_id == current_user.id) & (models.ChatMessage.receiver_id == uid)) |
            ((models.ChatMessage.sender_id == uid) & (models.ChatMessage.receiver_id == current_user.id))
        ).order_by(models.ChatMessage.created_at.desc()).first()
        unread = db.query(models.ChatMessage).filter(
            models.ChatMessage.sender_id == uid,
            models.ChatMessage.receiver_id == current_user.id,
            models.ChatMessage.is_read == False
        ).count()
        conversations.append({
            "user_id": other_user.id,
            "last_message": last_msg.message if last_msg else "",
            "unread_count": unread
        })
    return conversations


@app.get("/chat/unread-count")
def get_unread_chat_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    count = db.query(models.ChatMessage).filter(
        models.ChatMessage.receiver_id == current_user.id,
        models.ChatMessage.is_read == False
    ).count()
    return {"unread_count": count}



@app.get("/chat/messages/{other_user_id}")
def get_messages(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    messages = db.query(models.ChatMessage).filter(
        ((models.ChatMessage.sender_id == current_user.id) & (models.ChatMessage.receiver_id == other_user_id)) |
        ((models.ChatMessage.sender_id == other_user_id) & (models.ChatMessage.receiver_id == current_user.id))
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    # Mark unread messages as read
    db.query(models.ChatMessage).filter(
        models.ChatMessage.sender_id == other_user_id,
        models.ChatMessage.receiver_id == current_user.id,
        models.ChatMessage.is_read == False
    ).update({"is_read": True})
    db.commit()
    
    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "message": msg.message,
            "is_read": msg.is_read,
            "created_at": msg.created_at,
            "sender_name": msg.sender.full_name,
            "receiver_name": msg.receiver.full_name
        })
    return result

@app.post("/chat/send")
async def send_message(
    msg: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    new_msg = models.ChatMessage(
        sender_id=current_user.id,
        receiver_id=msg.receiver_id,
        message=msg.message
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    
    # Notify receiver via socket
    sid = user_sid_map.get(msg.receiver_id)
    if sid:
        await sio.emit('new_chat_message', {
            'message_id': new_msg.id,
            'sender_id': current_user.id,
            'sender_name': current_user.full_name,
            'receiver_id': msg.receiver_id,
            'message': msg.message,
            'created_at': str(new_msg.created_at)
        }, room=sid)
    
    return {"message": "sent"}


@app.get("/users/{user_id}")
def get_user_info(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "full_name": user.full_name,
        "role": user.role.value
    }




# ------------------- Chat Delete & Clear Endpoints -------------------
@app.delete("/chat/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    msg = db.query(models.ChatMessage).filter(models.ChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(msg)
    db.commit()
    return {"message": "Message deleted"}

@app.delete("/chat/clear/{other_user_id}")
def clear_chat(
    other_user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Delete all messages between current_user and other_user
    messages = db.query(models.ChatMessage).filter(
        ((models.ChatMessage.sender_id == current_user.id) & (models.ChatMessage.receiver_id == other_user_id)) |
        ((models.ChatMessage.sender_id == other_user_id) & (models.ChatMessage.receiver_id == current_user.id))
    ).all()
    for msg in messages:
        db.delete(msg)
    db.commit()
    return {"message": f"Cleared chat with user {other_user_id}"}





from utils.otp import generate_otp
from utils.otp_store import otp_store
from utils.email import send_otp_email
from schemas import AuctionBidCreate, CropRecommendationRequest, EmailRequest, ResetPasswordRequest, VerifyOtpRequest, YieldPredictionRequest
from auth import get_Password_hashed, get_current_farmer

@app.post("/forgot-password/send-otp")
def send_forgot_password_otp(data: EmailRequest, db: Session = Depends(get_db)):
    # Check if user exists
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        # For security, still return success (avoid email enumeration)
        return {"message": "If the email is registered, you will receive an OTP"}
    
    otp = generate_otp()
    otp_store[data.email] = otp
    send_otp_email(data.email, otp)
    return {"message": "OTP sent successfully"}

@app.post("/forgot-password/verify-otp")
def verify_forgot_password_otp(data: VerifyOtpRequest):
    stored_otp = otp_store.get(data.email)
    if not stored_otp or stored_otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    # OTP verified; keep it in store for reset step (or delete after reset)
    return {"message": "OTP verified"}

@app.post("/forgot-password/reset")
def reset_forgot_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    # Verify OTP again (optional, but secure)
    stored_otp = otp_store.get(data.email)
    if not stored_otp or stored_otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    hashed = get_Password_hashed(data.new_password)
    user.hashed_password = hashed
    db.commit()
    
    # Remove OTP after successful reset
    otp_store.pop(data.email, None)
    
    return {"message": "Password reset successfully"}


from schemas import ChangePasswordRequest

@app.post("/change-password")
def change_password(
    data: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Verify current password
    if not auth.verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash new password
    new_hashed = auth.get_Password_hashed(data.new_password)
    current_user.hashed_password = new_hashed
    db.commit()
    
    return {"message": "Password changed successfully"}

@app.post("/crop-recommendation")
def recommend_crop(data: CropRecommendationRequest):
    # Rule-based logic
    recommendations = []
    
    
    if data.season == "खरीप":
        if data.soil_type == "काळी":
            recommendations = ["कापूस", "ज्वारी", "मका"]
        elif data.soil_type == "लाल":
            recommendations = ["भुईमूग", "सूर्यफूल", "तूर"]
        else:
            recommendations = ["ज्वारी", "बाजरी", "मका"]
    
    
    elif data.season == "रब्बी":
        if data.water == "भरपूर":
            recommendations = ["गहू", "हरभरा", "मटर"]
        elif data.water == "मध्यम":
            recommendations = ["जवस", "मोहरी", "चणा"]
        else:
            recommendations = ["बाजरी", "हरभरा", "ज्वारी"]
    
    
    else:
        recommendations = ["करडई", "सूर्यफूल", "भुईमूग"]
    
    return {"recommendations": recommendations, "message": f"{data.season} साठी {data.soil_type} जमिनीत {data.water} पाण्यात ही पिके उत्तम"}


import aiohttp
import os
from datetime import date
from fastapi import HTTPException
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("AGMARKNET_API_KEY")


market_cache = {"data": None, "date": None}

async def fetch_all_agmarknet_prices(api_key: str):
    """
    AGMARKNET API वरून सर्व उपलब्ध रेकॉर्ड्स पेजिनेशन वापरून मिळवते.
    """
    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    all_records = []
    offset = 0
    limit = 2000 

    async with aiohttp.ClientSession() as session:
        while True:
            params = {
                "api-key": api_key,
                "format": "json",
                "limit": limit,
                "offset": offset,
            }
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    
                    break
                data = await resp.json()
                records = data.get("records", [])
                if not records:
                    break
                all_records.extend(records)
                
                if len(records) < limit:
                    break
                offset += limit
               
                if offset > 5000:
                    break

    print(f"✅ Fetched total {len(all_records)} records from AGMARKNET API")
    return {"records": all_records}







demo_maharashtra_prices = [
    {"commodity": "टोमॅटो", "variety": "हायब्रिड", "market": "पुणे, पुणे, महाराष्ट्र", "price_min": 20, "price_max": 30, "price_modal": 25, "arrival_date": "2026-04-09"},
    {"commodity": "कांदा", "variety": "लाल", "market": "नाशिक, नाशिक, महाराष्ट्र", "price_min": 15, "price_max": 20, "price_modal": 18, "arrival_date": "2026-04-09"},
    {"commodity": "बटाटा", "variety": "लाल", "market": "मुंबई, मुंबई, महाराष्ट्र", "price_min": 25, "price_max": 35, "price_modal": 30, "arrival_date": "2026-04-09"},
    {"commodity": "हिरवी मिरची", "variety": "हिरवी", "market": "कोल्हापूर, कोल्हापूर, महाराष्ट्र", "price_min": 40, "price_max": 50, "price_modal": 45, "arrival_date": "2026-04-09"},
    {"commodity": "फ्लॉवर", "variety": "पांढरा", "market": "सांगली, सांगली, महाराष्ट्र", "price_min": 30, "price_max": 40, "price_modal": 35, "arrival_date": "2026-04-09"},
    {"commodity": "कोबी", "variety": "हिरवी", "market": "सोलापूर, सोलापूर, महाराष्ट्र", "price_min": 15, "price_max": 25, "price_modal": 20, "arrival_date": "2026-04-09"},
]

@app.get("/market-prices/dynamic")
async def get_dynamic_market_prices():
    global market_cache
    today = date.today()

    if market_cache.get("date") == today and market_cache.get("data"):
        return market_cache["data"]

    if not API_KEY:
       
        market_cache["data"] = demo_maharashtra_prices
        market_cache["date"] = today
        return demo_maharashtra_prices

    try:
        raw_data = await fetch_all_agmarknet_prices(API_KEY)
        processed = []
        for record in raw_data.get("records", []):
            state = record.get("state")
            if state and state.strip().lower() == "maharashtra":
                processed.append({
                    "commodity": record.get("commodity"),
                    "variety": record.get("variety"),
                    "market": f"{record.get('market')}, {record.get('district')}, {record.get('state')}",
                    "price_min": record.get("min_price"),
                    "price_max": record.get("max_price"),
                    "price_modal": record.get("modal_price"),
                    "arrival_date": record.get("arrival_date"),
                })
        if len(processed) == 0:
            
            processed = demo_maharashtra_prices
        market_cache["data"] = processed
        market_cache["date"] = today
        return processed
    except Exception as e:
       
        print(f"API error: {e}, using demo data")
        market_cache["data"] = demo_maharashtra_prices
        market_cache["date"] = today
        return demo_maharashtra_prices




import aiohttp
from urllib.parse import quote



# ------------------- LIVE WEATHER ADVICE (Open-Meteo) -------------------
import aiohttp
from urllib.parse import quote


async def get_coordinates(city_name: str):
    """शहराचे नाव देऊन त्याचे अक्षांश (latitude) आणि रेखांश (longitude) मिळवा."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote(city_name)}&count=1&language=en"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None, None
            data = await resp.json()
            if data.get("results"):
                result = data["results"][0]
                return result.get("latitude"), result.get("longitude")
    return None, None



@app.get("/weather-advice")
async def get_weather_advice(city: str = None, lat: float = None, lon: float = None):

    if not city and (lat is None or lon is None):
        raise HTTPException(status_code=400, detail="Provide either 'city' or both 'lat' and 'lon'.")
    
  
    if lat is not None and lon is not None:
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relative_humidity_2m&forecast_days=1"
        city_name = f"lat:{lat},lon:{lon}" 
    else:
       
        lat, lon = await get_coordinates(city)
        if lat is None or lon is None:
            raise HTTPException(status_code=404, detail=f"City '{city}' not found.")
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relative_humidity_2m&forecast_days=1"
        city_name = city

   
    async with aiohttp.ClientSession() as session:
        async with session.get(weather_url) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="Weather service error.")
            data = await resp.json()

    current = data.get("current_weather", {})
    temp = current.get("temperature")
    wind_speed = current.get("windspeed")
    weather_code = current.get("weathercode")

    hourly = data.get("hourly", {})
    humidity = hourly.get("relative_humidity_2m", [None])[0]

    
    description = "स्वच्छ आकाश"
    if weather_code and weather_code > 50:
        description = "पाऊस किंवा ढगाळ"


    advice = []
    if weather_code and weather_code > 50:
        advice.append("🌧️ आज पाऊस/ढगाळ हवामान आहे. उत्पादनांची कापणी टाळा. पिकांना आश्रय द्या.")
    if temp and temp > 35:
        advice.append("🔥 तापमान खूप वाढले आहे. पिकांना सकाळी/संध्याकाळी पाणी द्या.")
    elif temp and temp < 10:
        advice.append("❄️ थंडी आहे. पिकांना झाकण ठेवा, दंवापासून संरक्षण करा.")
    if humidity and humidity > 80:
        advice.append("💧 आर्द्रता खूप आहे. बुरशीजन्य रोगांची शक्यता, फवारणी करा.")
    elif humidity and humidity < 30:
        advice.append("🌵 आर्द्रता कमी आहे. पिकांना ठिबक सिंचनाचा वापर करा.")
    if not advice:
        advice.append("✅ हवामान सामान्य आहे. नियमित शेती कामे सुरू ठेवा.")

    return {
        "city": city_name,
        "temperature": temp,
        "humidity": humidity,
        "description": description,
        "wind_speed": wind_speed,
        "advice": advice
    }


from utils.ai import get_ai_response
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str

@app.post("/chatbot")
async def chatbot_endpoint(request: ChatRequest):
    user_query = request.query
    ai_answer = get_ai_response(user_query)
    return {"answer": ai_answer}




@app.post("/chatbot")
async def chatbot_endpoint(request: ChatRequest):
    query = request.query.lower()
    

    if "भात" in query or "तांदूळ" in query or "paddy" in query:
        answer = "🌾 भात लागवडीसाठी खरीप हंगाम (जून-ऑक्टोबर) योग्य आहे. सखल, चिकणमाती जमीन चांगली."
    elif "कांदा" in query or "onion" in query:
        answer = "🧅 कांदा रब्बी हंगामात (ऑक्टोबर-मार्च) लागवड करावा. साठवणुकीसाठी कोरड्या, हवेशीर जागी ठेवा."
    elif "सेंद्रिय खत" in query or "जैविक खत" in query or "organic" in query:
        answer = "🌱 गांडूळ खत, शेणखत, कंपोस्ट, हिरवळीची खते उत्तम सेंद्रिय पर्याय आहेत."
    elif "कीटक" in query or "किडा" in query or "pest" in query:
        answer = "🐛 निंबोळी अर्क, लसूण-मिरची फवारणी, किंवा जैविक कीटकनाशकांचा (बिव्हेरिया बेसियाना) वापर करा."
    elif "पाणी" in query or "सिंचन" in query or "water" in query:
        answer = "💧 ठिबक सिंचन व फवारणी सिंचनाने पाणी वाचते. पिकानुसार पाण्याचे नियोजन करा."
    elif "माती" in query or "जमीन" in query or "soil" in query:
        answer = "🟫 माती परीक्षण करूनच खतांचा वापर करा. सेंद्रिय पदार्थ वाढविण्यासाठी हिरवळीची खतं वापरा."
    elif "हवामान" in query or "weather" in query:
        answer = "⛅ हवामान सल्ल्यासाठी 'हवामान सल्ला' पेजवर जा. तिथे तुम्ही शहराचे नाव देऊन लाईव्ह हवामान पाहू शकता."
    else:
        answer = "🤖 क्षमस्व, या प्रश्नाचे उत्तर माझ्याकडे नाही. कृपया दुसरा प्रश्न विचारा (भात, कांदा, सेंद्रिय खत, कीटक, पाणी, माती, हवामान)."
    
    return {"answer": answer}




import base64
from PIL import Image
import io





@app.post("/disease-detection")
async def detect_disease(file: UploadFile = File(...)):
   
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files allowed")
    
  
    contents = await file.read()
    
    
    try:
        import google.generativeai as genai
        import base64
        image_base64 = base64.b64encode(contents).decode('utf-8')
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([
            "तू कृषी तज्ञ आहेस. खालील पानाच्या फोटोमध्ये कोणता रोग आहे ते ओळख आणि उपचार सांग. मराठीत उत्तर दे.",
            {"mime_type": file.content_type, "data": image_base64}
        ])
        result = response.text
    except Exception as e:
        print(f"Disease detection error: {e}")
        result = "⚠️ सध्या AI सेवा उपलब्ध नाही. कृपया तुमच्या जवळच्या कृषी अधिकाऱ्याशी संपर्क साधा. (डेमो मोड)\n\nतुम्ही हे तपासू शकता:\n- पानावर डाग असल्यास बुरशीजन्य रोग असू शकतो.\n- पिवळी पाने – नत्राची कमतरता.\n- कोमेजलेली पाने – पाण्याची कमतरता किंवा अतिवृष्टी."
    
    return {"disease_info": result}




from pydantic import BaseModel
import random

class DynamicPricingRequest(BaseModel):
    category: str     
    base_price: float  
    season: str        
    demand: str        

@app.post("/dynamic-pricing")
def dynamic_pricing(request: DynamicPricingRequest):
  
    season_factor = {
        "खरीप": 1.1,
        "रब्बी": 1.0,
        "उन्हाळी": 0.9
    }.get(request.season, 1.0)
    
   
    demand_factor = {
        "high": 1.2,
        "medium": 1.0,
        "low": 0.85
    }.get(request.demand, 1.0)
    
  
    category_factor = {
        "भाजी": 1.0,
        "फळ": 1.15,
        "धान्य": 0.95
    }.get(request.category, 1.0)
    
    
    random_variation = random.uniform(0.9, 1.1)
    
    suggested_price = request.base_price * season_factor * demand_factor * category_factor * random_variation
    suggested_price = round(suggested_price, 2)
    
    return {"suggested_price": suggested_price, "confidence": random.randint(60, 95)}


from utils.otp import generate_otp
from utils.otp_store import otp_store as phone_otp_store

from schemas import MobileLoginRequest, MobileOtpRequest, MobileOtpVerifyRequest, MobileRegisterRequest




from pydantic import BaseModel

class MobileOtpRequest(BaseModel):
    phone: str

class MobileOtpVerifyRequest(BaseModel):
    phone: str
    otp: str

# Temporary OTP store
phone_otp_store = {}



from utils.sms import send_otp_sms

@app.post("/mobile/send-otp")
def send_mobile_otp(data: MobileOtpRequest):
    otp = generate_otp()
    phone_otp_store[data.phone] = otp
    sms_sent = send_otp_sms(data.phone, otp)
    print(f"📱 OTP for {data.phone}: {otp}")   
    if not sms_sent:
        print(f"⚠️ SMS failed, but OTP {otp} is valid for {data.phone}")
    return {"message": "OTP sent", "otp": otp if not sms_sent else None}

@app.post("/mobile/verify-otp")
def verify_mobile_otp(data: MobileOtpVerifyRequest, db: Session = Depends(get_db)):
    # Debug prints
    print(f"Verifying phone: {data.phone}, OTP: {data.otp}")
    print(f"Stored OTPs: {phone_otp_store}")
    
    stored = phone_otp_store.get(data.phone)
    if not stored:
        raise HTTPException(status_code=400, detail="No OTP sent or expired")
    if stored != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Find or create user
    user = db.query(models.User).filter(models.User.phone == data.phone).first()
    if not user:
        user = models.User(
            full_name=f"User_{data.phone[-4:]}",
            email=None,
            phone=data.phone,
            hashed_password=None,
            role="farmer"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    access_token = auth.create_access_token(data={"sub": str(user.id)})
    # Clean up OTP
    phone_otp_store.pop(data.phone, None)
    return {"access_token": access_token, "token_type": "bearer"}

# Mobile login with password
@app.post("/mobile/login")
def mobile_login(data: MobileLoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == data.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.hashed_password:
        raise HTTPException(status_code=400, detail="No password set. Use OTP login.")
    if not auth.verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    access_token = auth.create_access_token(data={"sub": str(user.id), "phone": user.phone})
    return {"access_token": access_token, "token_type": "bearer", "user": user}

# Register with mobile + password (optional)
@app.post("/mobile/register")
def mobile_register(data: MobileRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone already registered")
    hashed = auth.get_Password_hashed(data.password) if data.password else None
    new_user = models.User(
        full_name=data.full_name,
        email=None,
        phone=data.phone,
        hashed_password=hashed,
        role=data.role,
        location=data.location
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # If password not provided, user can login via OTP
    return {"message": "Registration successful", "user": new_user}





from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
import models, schemas, auth
from database import get_db

# ---------- Farm Expenses ----------
@app.post("/farm/expenses", response_model=schemas.FarmExpenseOut)
def add_expense(
    expense: schemas.FarmExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    db_expense = models.FarmExpense(
        farmer_id=current_user.id,
        land_name=expense.land_name,
        crop_name=expense.crop_name,
        category=expense.category,
        description=expense.description,
        quantity=expense.quantity,
        unit=expense.unit,
        amount=expense.amount,
        payment_method=expense.payment_method,
        receipt_url=expense.receipt_url,
        payment_status=expense.payment_status, 
        date=expense.date,
        is_recurring=expense.is_recurring,
        recurring_interval=expense.recurring_interval
    )
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

@app.get("/farm/expenses", response_model=List[schemas.FarmExpenseOut])
def get_expenses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    query = db.query(models.FarmExpense).filter(models.FarmExpense.farmer_id == current_user.id)
    if start_date:
        query = query.filter(models.FarmExpense.date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        query = query.filter(models.FarmExpense.date <= datetime.strptime(end_date, "%Y-%m-%d").date())
    return query.order_by(models.FarmExpense.date.desc()).all()

@app.delete("/farm/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    expense = db.query(models.FarmExpense).filter(
        models.FarmExpense.id == expense_id,
        models.FarmExpense.farmer_id == current_user.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted"}

@app.get("/farm/profit-loss", response_model=schemas.ProfitLossResponse)
def get_profit_loss(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
   
    products = db.query(models.Product).filter(models.Product.farmer_id == current_user.id).all()
    product_ids = [p.id for p in products]
    if not product_ids:
        total_revenue = 0.0
    else:
        revenue_query = db.query(func.sum(models.OrderItem.price * models.OrderItem.quantity)).join(
            models.Order, models.Order.id == models.OrderItem.order_id
        ).filter(
            models.OrderItem.product_id.in_(product_ids),
            models.Order.status == "delivered"
        )
        if start_date:
            revenue_query = revenue_query.filter(models.Order.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
        if end_date:
            revenue_query = revenue_query.filter(models.Order.created_at <= datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
        total_revenue = revenue_query.scalar() or 0.0

   
    expense_query = db.query(models.FarmExpense).filter(models.FarmExpense.farmer_id == current_user.id)
    if start_date:
        expense_query = expense_query.filter(models.FarmExpense.date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        expense_query = expense_query.filter(models.FarmExpense.date <= datetime.strptime(end_date, "%Y-%m-%d").date())
    expenses = expense_query.all()
    total_expenses = sum(e.amount for e in expenses)

   
    breakdown = {}
    land_breakdown = {}
    crop_breakdown = {}
    for e in expenses:
        breakdown[e.category] = breakdown.get(e.category, 0) + e.amount
        if e.land_name:
            land_breakdown[e.land_name] = land_breakdown.get(e.land_name, 0) + e.amount
        if e.crop_name:
            crop_breakdown[e.crop_name] = crop_breakdown.get(e.crop_name, 0) + e.amount

    profit = total_revenue - total_expenses

    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "profit": profit,
        "expense_breakdown": breakdown,
        "land_breakdown": land_breakdown,
        "crop_breakdown": crop_breakdown
    }





from datetime import datetime
import aiohttp
from urllib.parse import quote

# ---------------------------------- Soil Moisture Monitoring ----------------------------------
@app.get("/soil-moisture")
async def get_soil_moisture(lat: float = None, lon: float = None, city: str = None, pincode: str = None):
    """
    शेतकऱ्याच्या स्थानासाठी मातीतील ओलावा डेटा मिळवा.
    हे एंडपॉइंट Open-Meteo API वापरते.
    """
    
    if not lat or not lon:
        if not city and not pincode:
            raise HTTPException(status_code=400, detail="कृपया शहराचे नाव किंवा पिनकोड प्रविष्ट करा.")
        
        
        PINCODE_TO_CITY = {
            "423101": "chandwad",
            "423104": "nashik",
            "422007": "mumbai",
            "431001": "Aurangabad",
            "444001": "Akola"
        }
        if pincode:
            city = PINCODE_TO_CITY.get(pincode)
            if not city:
                raise HTTPException(status_code=400, detail="हा पिनकोड ओळखला गेला नाही. कृपया शहराचे नाव वापरा.")
        
       
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote(city)}&count=1&language=en"
        async with aiohttp.ClientSession() as session:
            async with session.get(geocode_url) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=404, detail=f"शहर '{city}' सापडले नाही.")
                data = await resp.json()
                if not data.get("results"):
                    raise HTTPException(status_code=404, detail=f"शहर '{city}' सापडले नाही.")
                lat = data["results"][0]["latitude"]
                lon = data["results"][0]["longitude"]


    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm",
        "forecast_days": 1,
        "current_weather": "true"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="मातीतील ओलावा डेटा मिळवताना त्रुटी आली.")
            data = await resp.json()
    
   
    hourly_data = data.get("hourly", {})
    soil_moisture_0_7 = hourly_data.get("soil_moisture_0_to_7cm", [])
    soil_moisture_7_28 = hourly_data.get("soil_moisture_7_to_28cm", [])
    time_array = hourly_data.get("time", [])
    
    current_hour = datetime.now().strftime("%Y-%m-%dT%H:00")
    try:
        index = time_array.index(current_hour)
    except ValueError:
    
        index = -1
    
    moisture_0_7 = soil_moisture_0_7[index] if soil_moisture_0_7 else None
    moisture_7_28 = soil_moisture_7_28[index] if soil_moisture_7_28 else None
    

    advice = []
    if moisture_0_7 is not None:
        if moisture_0_7 < 0.15:
            advice.append("⚠️ वरच्या थरातील माती कोरडी आहे. तातडीने पाणी द्या.")
        elif moisture_0_7 < 0.25:
            advice.append("💧 वरच्या थरातील माती मध्यम ओलसर आहे. लवकरच सिंचनाची आवश्यकता भासेल.")
        elif moisture_0_7 < 0.35:
            advice.append("✅ वरच्या थरातील माती चांगली ओलसर आहे. सध्या पाण्याची गरज नाही.")
        else:
            advice.append("⚠️ वरच्या थरातील माती खूप ओलसर आहे. पाणी कमी करा किंवा निचरा व्यवस्था तपासा.")
    
    if moisture_7_28 is not None:
        if moisture_7_28 < 0.2:
            advice.append("⚠️ खोल थरातील माती कोरडी आहे. पिकांच्या मुळांपर्यंत पाणी पोहोचवण्यासाठी सखोल सिंचन करा.")
        elif moisture_7_28 < 0.3:
            advice.append("💧 खोल थरातील माती मध्यम आहे. पिकांच्या वाढीसाठी पुरेसा ओलावा आहे.")
        elif moisture_7_28 < 0.4:
            advice.append("✅ खोल थरातील माती चांगली ओलसर आहे.")
        else:
            advice.append("⚠️ खोल थरातील माती खूप ओलसर आहे. पाणी साचण्याची शक्यता आहे.")
    
    if not advice:
        advice.append("🌱 मातीतील ओलावा सामान्य आहे. नियमित देखभाल करा.")
    

    return {
        "location": city or f"{lat}, {lon}",
        "timestamp": current_hour,
        "soil_moisture": {
            "surface": round(moisture_0_7 * 100, 1) if moisture_0_7 is not None else None,
            "deep": round(moisture_7_28 * 100, 1) if moisture_7_28 is not None else None
        },
        "advice": advice,
        "units": "% (volumetric water content)"
    }





from models import FarmTask
from schemas import FarmTaskCreate, FarmTaskUpdate, FarmTaskOut
from typing import List

# ---------- Farm Tasks ----------
@app.post("/farm/tasks", response_model=FarmTaskOut)
def create_task(
    task: FarmTaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    db_task = FarmTask(
        farmer_id=current_user.id,
        title=task.title,
        description=task.description,
        crop_name=task.crop_name,
        land_name=task.land_name,
        due_date=task.due_date,
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/farm/tasks", response_model=List[FarmTaskOut])
def get_tasks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer),
    status: Optional[str] = None
):
    query = db.query(FarmTask).filter(FarmTask.farmer_id == current_user.id)
    if status:
        query = query.filter(FarmTask.status == status)
    return query.order_by(FarmTask.due_date.asc()).all()

@app.put("/farm/tasks/{task_id}", response_model=FarmTaskOut)
def update_task(
    task_id: int,
    task_update: FarmTaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    task = db.query(FarmTask).filter(FarmTask.id == task_id, FarmTask.farmer_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in task_update.dict(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task

@app.delete("/farm/tasks/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    task = db.query(FarmTask).filter(FarmTask.id == task_id, FarmTask.farmer_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}



from schemas import ProfitReportFilter, ProfitReportResponse, MonthlyProfit
from collections import defaultdict
from sqlalchemy import func, extract

@app.post("/farm/profit-report", response_model=ProfitReportResponse)
def get_profit_report(
    filters: ProfitReportFilter,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
 
    products = db.query(models.Product).filter(models.Product.farmer_id == current_user.id).all()
    product_ids = [p.id for p in products]
    
    
    revenue_query = db.query(
        func.sum(models.OrderItem.price * models.OrderItem.quantity).label('total'),
        func.strftime('%Y-%m', models.Order.created_at).label('month')
    ).join(
        models.Order, models.Order.id == models.OrderItem.order_id
    ).filter(
        models.OrderItem.product_id.in_(product_ids),
        models.Order.status == "delivered"
    )
    if filters.start_date:
        revenue_query = revenue_query.filter(models.Order.created_at >= filters.start_date)
    if filters.end_date:
        revenue_query = revenue_query.filter(models.Order.created_at <= filters.end_date + timedelta(days=1))
    
    revenue_results = revenue_query.group_by('month').all()
    
   
    expense_query = db.query(
        models.FarmExpense.amount,
        models.FarmExpense.date,
        models.FarmExpense.category,
        models.FarmExpense.crop_name,
        models.FarmExpense.land_name
    ).filter(models.FarmExpense.farmer_id == current_user.id)
    if filters.start_date:
        expense_query = expense_query.filter(models.FarmExpense.date >= filters.start_date)
    if filters.end_date:
        expense_query = expense_query.filter(models.FarmExpense.date <= filters.end_date)
    if filters.crop_name:
        expense_query = expense_query.filter(models.FarmExpense.crop_name == filters.crop_name)
    if filters.land_name:
        expense_query = expense_query.filter(models.FarmExpense.land_name == filters.land_name)
    
    expenses = expense_query.all()
    
    
    revenue_by_month = {row.month: row.total for row in revenue_results}
    
  
    expenses_by_month = defaultdict(float)
    crop_expenses = defaultdict(float)
    land_expenses = defaultdict(float)
    category_expenses = defaultdict(float)
    
    for exp in expenses:
        month_str = exp.date.strftime("%Y-%m")
        expenses_by_month[month_str] += exp.amount
        if exp.crop_name:
            crop_expenses[exp.crop_name] += exp.amount
        if exp.land_name:
            land_expenses[exp.land_name] += exp.amount
        category_expenses[exp.category] += exp.amount
    
    
    all_months = set(revenue_by_month.keys()) | set(expenses_by_month.keys())
    monthly_breakdown = []
    for month in sorted(all_months):
        rev = revenue_by_month.get(month, 0.0)
        exp = expenses_by_month.get(month, 0.0)
        monthly_breakdown.append(MonthlyProfit(
            month=month,
            revenue=rev,
            expenses=exp,
            profit=rev - exp
        ))
    
    total_revenue = sum(revenue_by_month.values())
    total_expenses = sum(expenses_by_month.values())
    profit = total_revenue - total_expenses
    
    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "profit": profit,
        "monthly_breakdown": monthly_breakdown,
        "crop_breakdown": {crop: -amt for crop, amt in crop_expenses.items()},
        "land_breakdown": {land: -amt for land, amt in land_expenses.items()},
        "expense_breakdown": dict(category_expenses)
    }

from models import IrrigationSchedule
from schemas import IrrigationScheduleCreate, IrrigationScheduleUpdate, IrrigationScheduleOut

# ---------- Irrigation Scheduler ----------
@app.post("/farm/irrigation", response_model=IrrigationScheduleOut)
def create_irrigation_schedule(
    schedule: IrrigationScheduleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    db_schedule = IrrigationSchedule(
        farmer_id=current_user.id,
        land_name=schedule.land_name,
        crop_name=schedule.crop_name,
        irrigation_method=schedule.irrigation_method,
        last_irrigation_date=schedule.last_irrigation_date,
        next_irrigation_date=schedule.next_irrigation_date,
        interval_days=schedule.interval_days,
        is_active=schedule.is_active
    )
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@app.get("/farm/irrigation", response_model=List[IrrigationScheduleOut])
def get_irrigation_schedules(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    schedules = db.query(IrrigationSchedule).filter(IrrigationSchedule.farmer_id == current_user.id).all()
    return schedules

@app.put("/farm/irrigation/{schedule_id}", response_model=IrrigationScheduleOut)
def update_irrigation_schedule(
    schedule_id: int,
    schedule_update: IrrigationScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    schedule = db.query(IrrigationSchedule).filter(
        IrrigationSchedule.id == schedule_id,
        IrrigationSchedule.farmer_id == current_user.id
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for key, value in schedule_update.dict(exclude_unset=True).items():
        setattr(schedule, key, value)
    db.commit()
    db.refresh(schedule)
    return schedule

@app.delete("/farm/irrigation/{schedule_id}")
def delete_irrigation_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    schedule = db.query(IrrigationSchedule).filter(
        IrrigationSchedule.id == schedule_id,
        IrrigationSchedule.farmer_id == current_user.id
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    return {"message": "Schedule deleted"}


@app.get("/farm/irrigation/due")
def get_due_irrigations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    today = date.today()
    due_schedules = db.query(IrrigationSchedule).filter(
        IrrigationSchedule.farmer_id == current_user.id,
        IrrigationSchedule.is_active == True,
        IrrigationSchedule.next_irrigation_date <= today
    ).all()
    return due_schedules


from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
import atexit

def check_due_irrigations():
    db = next(get_db())
    today = date.today()

    due_schedules= db.query(models.IrrigationSchedule).filter(
        models.IrrigationSchedule.is_active == True,
        models.IrrigationSchedule.next_irrigation_date == today
    ).all()

    for schedule in due_schedules:
        farmer_id = schedule.farmer_id
        sid = user_sid_map.get(farmer_id)
        if sid:
            sio.emit('irrigation_due', {
                'schedule_id':schedule.id,
                'land_name': schedule.land_name or 'अज्ञात शेत',
                'crop_name': schedule.crop_name or 'अज्ञात पीक',
                'message': f"🌱 सिंचनाची वेळ आली आहे! {schedule.land_name or 'शेत'} मध्ये {schedule.crop_name or 'पीक'} ला पाणी द्या."
            },room=sid)

        else:
            print(f"Farmer {farmer_id} not connected to socket")

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=check_due_irrigations,
            trigger=CronTrigger(hour=8,minute=1),
            id="irrigation_reminder",
            replace_existing=True
        )
        scheduler.start()

        atexit.register(lambda:scheduler.shutdown())



from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os


def register_unicode_font():
    font_paths = [
        os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSans-Regular.ttf'),
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('UnicodeFont', path))
                print(f"✅ Unicode font loaded: {path}")
                return True
            except Exception as e:
                print(e)
                continue
    print("⚠️ No Unicode font found.")
    return False


UNICODE_FONT_AVAILABLE = register_unicode_font()
FONT_NAME = "UnicodeFont" if UNICODE_FONT_AVAILABLE else "Helvetica"

def draw_text(c, x, y, text, size=11, bold=False):
    """सर्व मजकूर (इंग्रजी/मराठी) एकाच फॉन्टने लिहा"""
    if bold and UNICODE_FONT_AVAILABLE:
        
        c.setFont(FONT_NAME, size)
    elif bold:
        c.setFont('Helvetica-Bold', size)
    else:
        c.setFont(FONT_NAME, size)
    c.drawString(x, y, text)

@app.get("/orders/{order_id}/invoice")
def generate_invoice(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    
    if current_user.role == "buyer" and order.buyer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    elif current_user.role == "farmer":
        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        product_ids = [i.product_id for i in items]
        farmer_product = db.query(models.Product).filter(
            models.Product.id.in_(product_ids),
            models.Product.farmer_id == current_user.id
        ).first()
        if not farmer_product:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

  
    buyer = db.query(models.User).filter(models.User.id == order.buyer_id).first()
    order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()

    items_data = []
    total = 0.0
    for item in order_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        product_name = product.name if product and product.name else f"Product ID {item.product_id}"
        line_total = item.quantity * item.price
        total += line_total
        items_data.append({
            "name": product_name,
            "qty": item.quantity,
            "price": item.price,
            "total": line_total
        })
      
        print(f"Product: {product_name}")

  
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

  
    draw_text(c, 50, y, "FARMER MARKET - INVOICE", size=16, bold=True)
    y -= 35

  
    draw_text(c, 50, y, f"Order ID: {order.id}", size=11)
    y -= 20
    draw_text(c, 50, y, f"Date: {order.created_at.strftime('%d/%m/%Y %H:%M')}", size=11)
    y -= 30

    
    draw_text(c, 50, y, "Buyer Details", size=12, bold=True)
    y -= 20
    draw_text(c, 50, y, f"Name: {buyer.full_name}", size=11)
    y -= 18
    draw_text(c, 50, y, f"Email: {buyer.email}", size=11)
    y -= 18
    if buyer.phone:
        draw_text(c, 50, y, f"Phone: {buyer.phone}", size=11)
        y -= 18
    if buyer.location:
        draw_text(c, 50, y, f"Location: {buyer.location}", size=11)
        y -= 25

  
    draw_text(c, 50, y, "Product", size=11, bold=True)
    draw_text(c, 200, y, "Qty", size=11, bold=True)
    draw_text(c, 250, y, "Price (₹)", size=11, bold=True)
    draw_text(c, 330, y, "Total (₹)", size=11, bold=True)
    y -= 15
    c.line(50, y+5, 550, y+5)
    y -= 10

  
    for item in items_data:
        if y < 100:
            c.showPage()
            y = height - 50
            draw_text(c, 50, y, "Product", size=11, bold=True)
            draw_text(c, 200, y, "Qty", size=11, bold=True)
            draw_text(c, 250, y, "Price (₹)", size=11, bold=True)
            draw_text(c, 330, y, "Total (₹)", size=11, bold=True)
            y -= 15
            c.line(50, y+5, 550, y+5)
            y -= 10

        draw_text(c, 50, y, item["name"][:40], size=10)
        draw_text(c, 200, y, str(item["qty"]), size=10)
        draw_text(c, 250, y, f"{item['price']:.2f}", size=10)
        draw_text(c, 330, y, f"{item['total']:.2f}", size=10)
        y -= 20

    y -= 10
    draw_text(c, 250, y, f"Total Amount: ₹{total:.2f}", size=12, bold=True)
    y -= 30

   
    draw_text(c, 50, y, "Payment Details", size=12, bold=True)
    y -= 20
    draw_text(c, 50, y, f"Method: {order.payment_method}", size=11)
    y -= 18
    draw_text(c, 50, y, f"Advance Paid: ₹{order.advance_paid:.2f}", size=11)
    y -= 18
    draw_text(c, 50, y, f"Pending Amount: ₹{order.pending_amount:.2f}", size=11)
    y -= 18
    if order.delivery_date:
        draw_text(c, 50, y, f"Delivery Date: {order.delivery_date.strftime('%d/%m/%Y')}", size=11)

    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{order_id}.pdf"}
    )






from models import YieldPrediction
from schemas import  YieldPredictionOut, YieldPredictionRequest,YieldPredictionResponse


# ---------- Crop Yield Prediction ----------
def calculate_yield_prediction(crop_name: str, soil_type: str, seed_type: str, irrigation_method: str, season: str) -> tuple:
    """
    हेयुरिस्टिक लॉजिक – प्रति एकर किलोमध्ये उत्पादन अंदाज
    """
  
    base_yield = {
        "टोमॅटो": 15000, "कांदा": 12000, "गहू": 2500, "भात": 2200,
        "कापूस": 800, "ज्वारी": 1200, "बाजरी": 1000, "हरभरा": 900
    }.get(crop_name, 5000)
    
   
    soil_factor = {
        "काळी": 1.2, "लाल": 0.9, "वालुकामय": 0.7, "चिकणमाती": 1.0
    }.get(soil_type, 1.0)
    
   
    seed_factor = 1.3 if seed_type == "hybrid" else 0.9 if seed_type == "local" else 1.0
    
  
    irrigation_factor = {
        "drip": 1.4, "sprinkler": 1.2, "flood": 0.8
    }.get(irrigation_method, 1.0)
   
    season_factor = {
        "kharif": 1.0, "rabi": 1.1, "summer": 0.7
    }.get(season, 1.0)
    

    predicted = base_yield * soil_factor * seed_factor * irrigation_factor * season_factor
    predicted = round(predicted, 2)
    
  
    confidence = min(95, int(60 + (soil_factor * 10) + (seed_factor * 10) + (irrigation_factor * 10)))
    
   
    factors = []
    if seed_type == "hybrid":
        factors.append("✅ हायब्रीड बियाणे – उत्पादनात 30% वाढ")
    if irrigation_method == "drip":
        factors.append("💧 ठिबक सिंचन – पाण्याची बचत आणि उत्पादनात 40% वाढ")
    elif irrigation_method == "sprinkler":
        factors.append("💧 फवारणी सिंचन – उत्पादनात 20% वाढ")
    if soil_type == "काळी":
        factors.append("🌱 काळी माती – उत्पादनासाठी उत्तम")
    
    return predicted, confidence, factors


@app.post("/crop/yield-predict",response_model=YieldPredictionResponse)
def predict_yield(
    request:YieldPredictionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    predicted, confidence, factors = calculate_yield_prediction(
        request.crop_name,
        request.soil_type,
        request.seed_type,
        request.irrigation_method,
        request.season
    )
   
    history = YieldPrediction(
        farmer_id=current_user.id,
        crop_name=request.crop_name,
        soil_type=request.soil_type,
        seed_type=request.seed_type,
        land_area=request.land_area,
        irrigation_method=request.irrigation_method,
        season=request.season,
        predicted_yield=predicted,
    )
    db.add(history)
    db.commit()

    total_yield = predicted * request.land_area 

    return {
        "predicted_yield":total_yield,
        "confidence": confidence,
        "factors": factors
    }

@app.get("/crop/yield-history", response_model=List[YieldPredictionOut])
def get_yield_history(
    db:Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    history = db.query(YieldPrediction).filter(YieldPrediction.farmer_id == current_user.id).order_by(YieldPrediction.created_at.desc()).all()
    return history


from models import Auction,AuctionBid
from schemas import AuctionCreate, AuctionOut

from datetime import datetime, timezone

@app.post("/auctions", response_model=AuctionOut)
def create_auction(
    auction_data: AuctionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    # Check product – only own products
    product = db.query(Product).filter(Product.id == auction_data.product_id, Product.farmer_id == current_user.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or not yours")
    if product.auction:
        raise HTTPException(status_code=400, detail="Product already has an active auction")
    
    # Convert end_time to naive UTC datetime for comparison and storage
    if auction_data.end_time.tzinfo is not None:
        end_time_naive = auction_data.end_time.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        end_time_naive = auction_data.end_time
    
    if end_time_naive <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="End time must be in future")
    
    new_auction = Auction(
        product_id=product.id,
        seller_id=current_user.id,
        starting_bid=auction_data.starting_bid,
        current_bid=auction_data.starting_bid,
        start_time=datetime.utcnow(),
        end_time=end_time_naive
    )
    db.add(new_auction)
    db.commit()
    db.refresh(new_auction)
    
    # Return as per AuctionOut schema
    seller = db.query(User).filter(User.id == new_auction.seller_id).first()
    bid_count = db.query(AuctionBid).filter(AuctionBid.auction_id == new_auction.id).count()
    
    return {
        "id": new_auction.id,
        "product_id": product.id,
        "product_name": product.name,
        "seller_id": seller.id,
        "seller_name": seller.full_name,
        "starting_bid": new_auction.starting_bid,
        "current_bid": new_auction.current_bid,
        "highest_bidder_id": None,
        "highest_bidder_name": None,
        "start_time": new_auction.start_time,
        "end_time": new_auction.end_time,
        "is_active": new_auction.is_active,
        "bid_count": bid_count,
        "status":"active",
        "winner_id":None,
        "winner_name":None
    }

@app.post("/auctions/{auction_id}/bid",response_model=AuctionOut)
def place_bid(
    auction_id:int,
    bid_data: AuctionBidCreate,
    db:Session = Depends(get_db),
    current_user:models.User=Depends(auth.get_current_user)
):
    auction = db.query(Auction).filter(Auction.id == auction_id,Auction.is_active==True).first()
    if not auction:
        raise HTTPException(status_code=404,detail="Auction not active")
    if auction.end_time < datetime.utcnow():
        auction.is_active = False
        db.commit()
        raise HTTPException(status_code=400,detail="Auction ended")
    if bid_data.amount <= auction.current_bid:
        raise HTTPException(status_code=400,detail=f"Bid must be higher than current bid ₹{auction.current_bid}")
    
    new_bid =  AuctionBid(
        auction_id = auction_id,
        bidder_id=current_user.id,
        amount=bid_data.amount
    )

    db.add(new_bid)
    auction.current_bid = bid_data.amount
    auction.highest_bidder_id=current_user.id
    db.commit()
    db.refresh(auction)

    product = db.query(Product).filter(Product.id == auction.product_id).first()
    seller = db.query(User).filter(User.id == auction.seller_id).first()
    highest_bidder = db.query(User).filter(User.id == auction.highest_bidder_id).first()
    bid_count = db.query(AuctionBid).filter(AuctionBid.auction_id == auction.id).count()

    return {
        "id":auction.id,
        "product_id":product.id,
        "product_name": product.name,
        "seller_id": seller.id,
        "seller_name": seller.full_name,
        "starting_bid": auction.starting_bid,
        "current_bid": auction.current_bid,
        "highest_bidder_id": highest_bidder.id if highest_bidder else None,
        "highest_bidder_name": highest_bidder.full_name if highest_bidder else None,
        "start_time": auction.start_time,
        "end_time": auction.end_time,
        "is_active": auction.is_active,
        "bid_count": bid_count ,
        "status": auction.status,
        "winner_id": auction.winner_id,
        "winner_name": db.query(User).filter(User.id == auction.winner_id).first().full_name if auction.winner_id else None       
    }

@app.get("/auctions/active",response_model=List[AuctionOut])
def get_active_auctions(db:Session = Depends(get_db)):
    now = datetime.utcnow()
    auctions = db.query(Auction).filter(Auction.is_active == True,Auction.end_time > now).all()
    result = []
    for a in auctions:
        product = db.query(Product).filter(Product.id == a.product_id).first()
        seller = db.query(User).filter(User.id == a.seller_id).first()
        highest_bidder = db.query(User).filter(User.id == a.highest_bidder_id).first() if a.highest_bidder_id else None

        bid_count = db.query(AuctionBid).filter(AuctionBid.auction_id == a.id).count()

        result.append({

            "id":a.id,
            "product_id": product.id,
            "product_name": product.name,
            "seller_id": seller.id,
            "seller_name": seller.full_name,
            "starting_bid": a.starting_bid,
            "current_bid": a.current_bid,
            "highest_bidder_id": highest_bidder.id if highest_bidder else None,
            "highest_bidder_name": highest_bidder.full_name if highest_bidder else None,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "is_active": a.is_active,
            "bid_count": bid_count   ,
            "status": a.status,
            "winner_id": a.winner_id,
            "winner_name": db.query(User).filter(User.id == a.winner_id).first().full_name if a.winner_id else None

        })

    return result

@app.post("/auctions/close-expired")
def close_expired_auctions(db:Session = Depends(get_db)):
    expired = db.query(Auction).filter(Auction.is_active == True, Auction.end_time <= datetime.utcnow()).all()

    for a in expired:
        a.is_active = False
        if a.highest_bidder_id:
            pass
        db.commit()

        return {"closed":len(expired)}




@app.get("/auctions/my", response_model=List[AuctionOut])
def get_my_auctions(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_farmer)):
    auctions = db.query(Auction).filter(Auction.seller_id == current_user.id).order_by(Auction.created_at.desc()).all()
    result = []
    for a in auctions:
        product = db.query(Product).get(a.product_id)
        seller = db.query(User).get(a.seller_id)
        highest_bidder = db.query(User).get(a.highest_bidder_id) if a.highest_bidder_id else None
        winner = db.query(User).get(a.winner_id) if a.winner_id else None
        bid_count = db.query(AuctionBid).filter(AuctionBid.auction_id == a.id).count()
        result.append({
            "id": a.id,
            "product_id": product.id,
            "product_name": product.name,
            "seller_id": seller.id,
            "seller_name": seller.full_name,
            "starting_bid": a.starting_bid,
            "current_bid": a.current_bid,
            "highest_bidder_id": a.highest_bidder_id,
            "highest_bidder_name": highest_bidder.full_name if highest_bidder else None,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "is_active": a.is_active,
            "status": a.status,
            "winner_id": a.winner_id,
            "winner_name": winner.full_name if winner else None,
            "bid_count": bid_count
        })
    return result


from schemas import AuctionBidOut

# Farmer: Get all bids for a specific auction
@app.get("/auctions/{auction_id}/bids", response_model=List[AuctionBidOut])
def get_auction_bids(auction_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    auction = db.query(Auction).get(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    # Allow farmer or buyer to see bids? Let farmer see all bids, buyer see only their own? For simplicity, allow farmer.
    if current_user.role == "farmer" and auction.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    bids = db.query(AuctionBid).filter(AuctionBid.auction_id == auction_id).order_by(AuctionBid.amount.desc()).all()
    result = []
    for b in bids:
        bidder = db.query(User).get(b.bidder_id)
        result.append({
            "id": b.id,
            "bidder_id": b.bidder_id,
            "bidder_name": bidder.full_name,
            "amount": b.amount,
            "created_at": b.created_at,
            "auction_id":auction.id

        })
    return result



from datetime import datetime
from models import Order, OrderItem

@app.post("/auctions/{auction_id}/end")
async def end_auction(
    auction_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_farmer)
):
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=404, detail="लिलाव सापडला नाही")
    if auction.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="अधिकृत नाही")
    if auction.status != "active":
        raise HTTPException(status_code=400, detail="लिलाव आधीच संपला आहे")
    
    highest_bidder_id = auction.highest_bidder_id
    product = db.query(Product).filter(Product.id == auction.product_id).first()
    
    if highest_bidder_id:
       
        auction.status = "sold"
        auction.is_active = False
        auction.winner_id = highest_bidder_id
    
        
        buyer = db.query(User).filter(User.id == highest_bidder_id).first()
        order_total = auction.current_bid 
        
        new_order = Order(
            buyer_id=highest_bidder_id,
            total_amount=order_total,
            status="confirmed",   
            payment_method="cod",
            advance_paid=0,
            pending_amount=order_total,
            delivery_date=None
        )
        db.add(new_order)
        db.flush()  
        
        
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=1,
            price=auction.current_bid
        )
        db.add(order_item)
        
        
        if product.quantity >= 1:
            product.quantity -= 1
            if product.quantity == 0:
                product.is_available = False
        
        db.commit()
        
    # (पर्यायी) विजेत्याला सॉकेट नोटिफिकेशन पाठवा
        sid = user_sid_map.get(highest_bidder_id)
        if sid:
            await sio.emit('order_created', {
                'order_id': new_order.id,
                'message': f'तुम्ही लिलाव जिंकला! ऑर्डर #{new_order.id} तयार झाली आहे.'
            }, room=sid)
        
        return {
            "message": f"लिलाव संपला. {buyer.full_name} साठी ऑर्डर #{new_order.id} तयार झाली.",
            "order_id": new_order.id
        }
    else:
       
        auction.status = "cancelled"
        auction.is_active = False
        db.commit()
        return {"message": "कोणतीही बोली नव्हती, लिलाव रद्द."}



@app.post("/auctions/{auction_id}/cancel")
def cancel_auction(auction_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_farmer)):
    auction = db.query(Auction).get(auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if auction.status != "active":
        raise HTTPException(status_code=400, detail="Auction already ended")
    auction.status = "cancelled"
    auction.is_active = False
    db.commit()
    return {"message": "Auction cancelled"}



import socketio

sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode="asgi")
socket_app = socketio.ASGIApp(sio, app)

user_sid_map = {}

# ---------- Socket.IO Event Handlers ----------
@sio.event
async def connect(sid, environ):
    print(f"Client Connected: {sid}")

@sio.event
async def disconnect(sid):
    for uid, s in list(user_sid_map.items()):
        if s == sid:
            del user_sid_map[uid]
            break

@sio.event
async def register_user(sid, data):
    user_id = data.get("user_id")
    if user_id:
        user_sid_map[user_id] = sid
        print(f"User {user_id} registered with sid {sid}")


@sio.event
async def call_user(sid, data):
    target_user_id = data['target_user_id']
    caller_id = data['caller_id']
    caller_name = data['caller_name']
    target_sid = user_sid_map.get(target_user_id)
    if target_sid:
        await sio.emit('incoming_call', {
            'caller_id': caller_id,
            'caller_name': caller_name,
            'caller_sid': sid
        }, room=target_sid)

@sio.event
async def accept_call(sid, data):
    caller_sid = data['caller_sid']
    receiver_sid = sid
    await sio.emit('call_accepted', {'receiver_sid': receiver_sid}, room=caller_sid)
    await sio.emit('call_accepted', {'caller_sid': caller_sid}, room=receiver_sid)

@sio.event
async def reject_call(sid, data):
    caller_sid = data['caller_sid']
    await sio.emit('call_rejected', {}, room=caller_sid)

@sio.event
async def offer(sid, data):
    target_sid = data['target_sid']
    await sio.emit('offer', {'offer': data['offer'], 'caller_sid': sid}, room=target_sid)

@sio.event
async def answer(sid, data):
    target_sid = data['target_sid']
    await sio.emit('answer', {'answer': data['answer']}, room=target_sid)

@sio.event
async def ice_candidate(sid, data):
    target_sid = data['target_sid']
    await sio.emit('ice_candidate', {'candidate': data['candidate']}, room=target_sid)




@app.post("/call/experts")
def get_available_experts(db:Session = Depends(get_db)):

    experts = db.query(models.User).filter(models.User.role.in_(['buyer','expert'])).all()
    return [{"id":e.id,"name":e.full_name,"profile_picture":e.profile_picture} for e in experts]





# ---------- Video Call: Get available experts ----------
@app.get("/call/experts")
def get_available_experts(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    experts = db.query(models.User).filter(models.User.role.in_(['buyer'])).all()
   
    return [
        {
            "id": e.id,
            "full_name": e.full_name,
            "profile_picture": e.profile_picture,
            "role": e.role
        }
        for e in experts
    ]







from models import GovScheme
from schemas import GovSchemeOut,SchemeFinderInput


@app.post("/schemes/recommend", response_model=List[GovSchemeOut])
def recommend_schemes(
    input_data: SchemeFinderInput,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
   
    query = db.query(GovScheme)
    
    
    query = query.filter(
        (GovScheme.crop_type == None) | 
        (GovScheme.crop_type == "सर्व") | 
        (GovScheme.crop_type == input_data.crop_name)
    )
    
    
    query = query.filter(
        (GovScheme.min_land_area == None) | 
        (GovScheme.min_land_area <= input_data.land_area)
    )
    
    schemes = query.all()
    return schemes

@app.post("/admin/schemes")
def add_scheme(
    scheme:GovSchemeOut,
    db:Session = Depends(get_db),
    current_user:models.User = Depends(auth.get_current_admin)
):
    db_scheme = GovScheme(**scheme.dict())
    db.add(db_scheme)
    db.commit()
    return {"message":"Scheme added successfully", "scheme_id": db_scheme.id}








# ------------------- Run -------------------
if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)



