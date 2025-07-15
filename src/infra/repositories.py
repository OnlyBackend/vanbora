from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload 
from sqlalchemy.future import select
from sqlalchemy import update, delete 
# from sqlalchemy import delete as sqla_delete 
from src.domain.models import User, Trip, Reservation
from typing import List, Optional

class UserRepository:
    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, user: User) -> User:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

class TripRepository:
    @staticmethod
    async def list_all(db: AsyncSession) -> List[Trip]:
        result = await db.execute(select(Trip))
        return result.scalars().all()

    @staticmethod
    async def get_by_id(db: AsyncSession, trip_id: int) -> Optional[Trip]:
        result = await db.execute(select(Trip).where(Trip.id == trip_id))
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, trip: Trip) -> Trip:
        db.add(trip)
        await db.commit()
        await db.refresh(trip)
        return trip

    @staticmethod
    async def update(db: AsyncSession, trip_id: int, data: dict) -> Optional[Trip]:
        await db.execute(update(Trip).where(Trip.id == trip_id).values(**data))
        await db.commit()
        return await TripRepository.get_by_id(db, trip_id)

    @staticmethod
    async def delete(db: AsyncSession, trip_id: int) -> None:
        # Deleta as reservas associadas primeiro
        await db.execute(
            sqla_delete(Reservation).where(Reservation.trip_id == trip_id)
        )
        # Deleta a viagem
        await db.execute(
            sqla_delete(Trip).where(Trip.id == trip_id)
        )
        await db.commit()

class ReservationRepository:
    @staticmethod
    async def create(db: AsyncSession, reservation: Reservation) -> Reservation:
        db.add(reservation)
        await db.commit()
        await db.refresh(reservation, attribute_names=['user', 'trip'])
        return reservation

    @staticmethod
    async def list_by_user(db: AsyncSession, user_id: int) -> List[Reservation]:

        result = await db.execute(
            select(Reservation)
            .where(Reservation.user_id == user_id)
            .options(selectinload(Reservation.user), selectinload(Reservation.trip)) 
        )
        return result.scalars().all()

    @staticmethod
    async def list_by_trip(db: AsyncSession, trip_id: int) -> List[Reservation]:

        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.user), selectinload(Reservation.trip))
            .where(Reservation.trip_id == trip_id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def update(db: AsyncSession, reservation_id: int, data: dict) -> Optional[Reservation]:
        await db.execute(update(Reservation).where(Reservation.id == reservation_id).values(**data))
        await db.commit()

        result = await db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(selectinload(Reservation.user), selectinload(Reservation.trip)) # CARREGAMENTO ANSIOSO
        )
        return result.scalars().first()

    @staticmethod
    async def get_by_id(db: AsyncSession, reservation_id: int) -> Optional[Reservation]:

        result = await db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .options(selectinload(Reservation.user), selectinload(Reservation.trip)) # CARREGAMENTO ANSIOSO
        )
        return result.scalars().first()