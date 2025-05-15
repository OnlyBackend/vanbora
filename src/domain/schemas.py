from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, time, datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_driver: bool = False

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class TripBase(BaseModel):
    origin: str
    destination: str
    date: date
    time: time
    available_seats: int

class TripCreate(TripBase):
    pass

class TripOut(TripBase):
    id: int
    driver_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class ReservationBase(BaseModel):
    pass

class ReservationCreate(ReservationBase):
    pass

class ReservationOut(ReservationBase):
    id: int
    user_id: int
    trip_id: int
    created_at: datetime

    class Config:
        orm_mode = True 