from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import models, database

from database import get_db

SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# def verify_password(plain_password,hashed_password):
#     return pwd_context.verify(plain_password,hashed_password)
def verify_password(plain_password, hashed_password):
    plain_password = plain_password[:72]  # 🔥 fix
    return pwd_context.verify(plain_password, hashed_password)


# def get_Password_hashed(password):
#     return pwd_context.hash(password)
def get_password_hash(password):
    password = password[:72]
    return pwd_context.hash(password)


def create_access_token(data:dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp":expire})
    encoded_jwt = jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user



# def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Invalid credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         email: str = payload.get("sub")
#         if email is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
#     user = get_user_by_email(db, email)
#     if user is None:
#         raise credentials_exception
#     return user



def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_identifier = payload.get("sub")
        if user_identifier is None:
            raise credentials_exceptions
    except JWTError:
        raise credentials_exception
    
    # Try to find user by email (if contains @) else by id
    user = None
    if "@" in str(user_identifier):
        user = db.query(models.User).filter(models.User.email == user_identifier).first()
    else:
        try:
            user_id = int(user_identifier)
            user = db.query(models.User).filter(models.User.id == user_id).first()
        except ValueError:
            pass
    
    if user is None:
        raise credentials_exception
    return user


def get_current_farmer(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.farmer:
        raise HTTPException(status_code=403, detail="Only farmers allowed")
    return current_user

def get_current_buyer(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.buyer:
        raise HTTPException(status_code=403, detail="Only buyers allowed")
    return current_user



def get_current_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user