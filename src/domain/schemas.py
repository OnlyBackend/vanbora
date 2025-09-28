from enum import Enum
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Optional
from datetime import date, time, datetime
from decimal import Decimal

class ReservationStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

class PaymentMethod(str, Enum):
    CASH = "CASH"
    PIX = "PIX"
    CREDIT_CARD = "CREDIT_CARD"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_driver: bool = False
    pix_key: Optional[str] = None
    balance: Decimal = Decimal("0.00")

class UserCreate(UserBase):
    password: str
    pix_key: Optional[str] = None  #apenas motorista

class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class TripBase(BaseModel):
    origin: str
    destination: str
    date: date
    time: time
    available_seats: int
    price: Decimal
    cancelable: bool = True

class TripCreate(TripBase):
    cancelable: bool = True  # sempre se inicia como cancelavel
    pass

class TripOut(TripBase):
    id: int
    driver_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ReservationBase(BaseModel):
    pass


class ReservationCreate(ReservationBase):
    payment_method: PaymentMethod

class ReservationOut(ReservationBase):
    id: int
    user_id: int
    trip_id: int
    created_at: datetime
    status: ReservationStatus

    payment_method: PaymentMethod
    payment_status: PaymentStatus
    payment_id: Optional[str]
    price_at_reservation: Decimal

    user: UserOut
    trip: TripOut 

    class Config:
        from_attributes = True

class ReservationUpdate(BaseModel):
    new_trip_id: int

class ReservationResponse(BaseModel):
    reservation: ReservationOut
    pix_qr_code: Optional[str] = None
    pix_copia_cola: Optional[str] = None

    class Config:
        from_attributes = True