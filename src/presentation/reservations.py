from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from src.domain.schemas import ReservationOut, ReservationStatus, ReservationUpdate
from src.domain.models import Reservation, Trip, User, ReservationStatusEnum
from src.infra.database import get_db
from src.infra.auth import get_current_active_user
from src.infra.repositories import ReservationRepository, TripRepository
from datetime import datetime, timedelta, timezone

router = APIRouter()

CANCELLATION_WINDOW_HOURS = 2
ENABLE_ALTERATION_DEADLINE = True

@router.post("/trips/{trip_id}/reserve/", response_model=ReservationOut)
async def reserve_trip(trip_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.available_seats <= 0:
        raise HTTPException(status_code=400, detail="Trip not available or full")
    
    reservations = await ReservationRepository.list_by_trip(db, trip_id)
    if any(r.user_id == current_user.id for r in reservations):
        raise HTTPException(status_code=400, detail="You already have a reservation for this trip")
    
    reservation = Reservation(user_id=current_user.id, trip_id=trip_id)
    reservation = await ReservationRepository.create(db, reservation) 
    

    await TripRepository.update(db, trip_id, {"available_seats": trip.available_seats - 1})
    
    return reservation

@router.get("/reservations/", response_model=List[ReservationOut])
async def list_reservations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):

    reservations = await ReservationRepository.list_by_user(db, current_user.id)
    return reservations

@router.put("/reservations/{reservation_id}/cancel/", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user) 
):

    reservation = await ReservationRepository.get_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva não encontrada."
        )


    if reservation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para cancelar esta reserva."
        )


    if reservation.status == ReservationStatusEnum.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta reserva já está cancelada."
        )


    trip = await TripRepository.get_by_id(db, reservation.trip_id)
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno: Viagem associada à reserva não encontrada."
        )


    trip_datetime = datetime.combine(trip.date, trip.time)
    now = datetime.now()
    

    if now >= trip_datetime:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Não é possível cancelar uma reserva expirada (a viagem já começou ou passou). {now}")


    cancellation_deadline = trip_datetime - timedelta(hours=CANCELLATION_WINDOW_HOURS)

    if now > cancellation_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não foi possível cancelar a reserva: o prazo de cancelamento (até {CANCELLATION_WINDOW_HOURS} horas antes da viagem) já expirou."
        )

    updated_reservation = await ReservationRepository.update(
        db, reservation_id, {"status": ReservationStatusEnum.CANCELLED}
    )

    await TripRepository.update(
        db, trip.id, {"available_seats": trip.available_seats + 1}
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.put("/reservations/{reservation_id}/edit/", response_model=ReservationOut)
async def edit_reservation(
        reservation_id: int,
        update_payload: ReservationUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):

    reservation = await ReservationRepository.get_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva não encontrada."
        )

    if reservation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para editar esta reserva."
        )


    if reservation.status != ReservationStatusEnum.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível editar: reserva não está no status 'CONFIRMED'."
        )
    
    old_trip = await TripRepository.get_by_id(db, reservation.trip_id)
    if not old_trip:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno: Viagem original da reserva não encontrada (integridade de dados comprometida)."
        )

    old_trip_datetime_utc = datetime.combine(old_trip.date, old_trip.time, tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)

    if now_utc >= old_trip_datetime_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível editar reserva de viagem já iniciada ou passada. Viagem: {old_trip_datetime_utc}, Agora: {now_utc}"
        )
    

    if ENABLE_ALTERATION_DEADLINE:
        alteration_deadline_utc = old_trip_datetime_utc - timedelta(hours=CANCELLATION_WINDOW_HOURS)
        if now_utc > alteration_deadline_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prazo para editar a reserva original expirou. edições permitidas até {CANCELLATION_WINDOW_HOURS} horas antes da viagem. Prazo: {alteration_deadline_utc}, Agora: {now_utc}"
            )

    new_trip = await TripRepository.get_by_id(db, update_payload.new_trip_id)
    if not new_trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nova viagem especificada não encontrada."
        )
    
    if old_trip.id == new_trip.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível editar a reserva para a mesma viagem."
        )


    if old_trip.driver_id != new_trip.driver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova viagem deve ser do mesmo responsável da viagem original."
        )


    if new_trip.available_seats <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A viagem escolhida não tem mais vagas disponíveis."
        )
    
    new_trip_datetime_utc = datetime.combine(new_trip.date, new_trip.time, tzinfo=timezone.utc)
    
    if now_utc >= new_trip_datetime_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível editar para uma viagem que já iniciou ou passou. Nova Viagem: {new_trip_datetime_utc}, Agora: {now_utc}"
        )
    
    await TripRepository.update(db, old_trip.id, {"available_seats": old_trip.available_seats + 1})
    updated_reservation = await ReservationRepository.update(
        db, reservation_id, {"trip_id": new_trip.id}
    )
    await TripRepository.update(db, new_trip.id, {"available_seats": new_trip.available_seats - 1})
    
    return updated_reservation 