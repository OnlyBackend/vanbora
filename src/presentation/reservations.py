from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from src.domain.schemas import ReservationOut
from src.domain.models import Reservation, Trip, User
from src.infra.database import get_db
from src.infra.auth import get_current_active_user
from src.infra.repositories import ReservationRepository, TripRepository

router = APIRouter()

@router.post("/trips/{trip_id}/reserve/", response_model=ReservationOut)
async def reserve_trip(trip_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.available_seats <= 0:
        raise HTTPException(status_code=400, detail="Trip not available or full")
    # Verifica se já existe reserva
    reservations = await ReservationRepository.list_by_trip(db, trip_id)
    if any(r.user_id == current_user.id for r in reservations):
        raise HTTPException(status_code=400, detail="You already have a reservation for this trip")
    reservation = Reservation(user_id=current_user.id, trip_id=trip_id)
    reservation = await ReservationRepository.create(db, reservation)
    # Atualiza vagas disponíveis
    await TripRepository.update(db, trip_id, {"available_seats": trip.available_seats - 1})
    return reservation

@router.get("/reservations/", response_model=List[ReservationOut])
async def list_reservations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    reservations = await ReservationRepository.list_by_user(db, current_user.id)
    return reservations 