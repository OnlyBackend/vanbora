from sqlalchemy import Column, Integer, String, Boolean, Date, Time, ForeignKey, DateTime, Enum, Numeric
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from enum import Enum as PyEnum

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_driver = Column(Boolean, default=False)
    pix_key = Column(String, nullable=True)  # chave Pix do motorista
    balance = Column(Numeric(10, 2), default=0)  # saldo acumulado do motorista
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trips = relationship("Trip", back_populates="driver")
    reservations = relationship("Reservation", back_populates="user")

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"))
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    available_seats = Column(Integer, nullable=False)
    price = Column(Numeric(10,2), nullable=False)# preço da passagem usada
    cancelable = Column(Boolean, default=True)  # permite cancelamento?
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    driver = relationship("User", back_populates="trips")
    reservations = relationship("Reservation", back_populates="trip")

class ReservationStatusEnum(PyEnum):
    CONFIRMED = "CONFIRMED" 
    CANCELLED = "CANCELLED"  

class PaymentStatusEnum(PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    #AUTHORIZED = "authorized"
    #IN_PROCESS = "in_process"
    #IN_MEDIATION = "in_mediation"
    #REJECTED = "rejected"
    #CANCELLED = "cancelled"
    #REFUNDED = "refunded"
    #CHARGED_BACK = "charged_back"

class PaymentMethodEnum(PyEnum):
    CASH = "CASH"
    PIX = "PIX"
    #CREDIT_CARD = "CREDIT_CARD"

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    trip_id = Column(Integer, ForeignKey("trips.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(ReservationStatusEnum, name="reservationstatusenum", create_type=False), default=ReservationStatusEnum.CONFIRMED)

    payment_method = Column(Enum(PaymentMethodEnum, name="paymentmethodenum", create_type=False), nullable=False)
    payment_status = Column(Enum(PaymentStatusEnum, name="paymentstatusenum", create_type=False), default=PaymentStatusEnum.PENDING)

    payment_id = Column(String, nullable=True)
    price_at_reservation = Column(Numeric(10, 2), nullable=False)

    user = relationship("User", back_populates="reservations")
    trip = relationship("Trip", back_populates="reservations")