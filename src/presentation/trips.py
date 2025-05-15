from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from src.domain.schemas import TripCreate, TripOut, UserOut
from src.domain.models import Trip, Reservation, User
from src.infra.database import get_db
from src.infra.auth import get_current_active_user, get_current_driver
from src.infra.repositories import TripRepository, ReservationRepository

router = APIRouter()

@router.get("/trips/", response_model=List[TripOut])
async def list_trips(db: AsyncSession = Depends(get_db)):
    trips = await TripRepository.list_all(db)
    return trips

@router.post("/trips/", response_model=TripOut)
async def create_trip(trip_in: TripCreate, db: AsyncSession = Depends(get_db), current_driver: User = Depends(get_current_driver)):
    trip = Trip(
        driver_id=current_driver.id,
        **trip_in.dict()
    )
    trip = await TripRepository.create(db, trip)
    return trip

@router.get("/trips/{trip_id}/", response_model=TripOut)
async def get_trip(trip_id: int, db: AsyncSession = Depends(get_db)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

@router.put("/trips/{trip_id}/", response_model=TripOut)
async def update_trip(trip_id: int, trip_in: TripCreate, db: AsyncSession = Depends(get_db), current_driver: User = Depends(get_current_driver)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.driver_id != current_driver.id:
        raise HTTPException(status_code=404, detail="Trip not found or not allowed")
    updated = await TripRepository.update(db, trip_id, trip_in.dict())
    return updated

@router.delete("/trips/{trip_id}/", status_code=204)
async def delete_trip(trip_id: int, db: AsyncSession = Depends(get_db), current_driver: User = Depends(get_current_driver)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.driver_id != current_driver.id:
        raise HTTPException(status_code=404, detail="Trip not found or not allowed")
    await TripRepository.delete(db, trip_id)
    return

@router.get("/trips/{trip_id}/passengers/", response_model=List[UserOut])
async def list_passengers(trip_id: int, db: AsyncSession = Depends(get_db), current_driver: User = Depends(get_current_driver)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.driver_id != current_driver.id:
        raise HTTPException(status_code=404, detail="Trip not found or not allowed")
    reservations = await ReservationRepository.list_by_trip(db, trip_id)
    passengers = [r.user for r in reservations]
    return passengers 