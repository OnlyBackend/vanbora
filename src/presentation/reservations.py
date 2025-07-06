from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from src.domain.schemas import ReservationOut, ReservationStatus
from src.domain.models import Reservation, Trip, User, ReservationStatusEnum
from src.infra.database import get_db
from src.infra.auth import get_current_active_user
from src.infra.repositories import ReservationRepository, TripRepository
from datetime import datetime, timedelta

router = APIRouter()

CANCELLATION_WINDOW_HOURS = 2

@router.post("/trips/{trip_id}/reserve/", response_model=ReservationOut)
async def reserve_trip(trip_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.available_seats <= 0:
        raise HTTPException(status_code=400, detail="Trip not available or full")
    
    # Verifica se já existe reserva (list_by_trip agora carrega user e trip, o que é bom)
    reservations = await ReservationRepository.list_by_trip(db, trip_id)
    if any(r.user_id == current_user.id for r in reservations):
        raise HTTPException(status_code=400, detail="You already have a reservation for this trip")
    
    reservation = Reservation(user_id=current_user.id, trip_id=trip_id)
    # create agora retorna o objeto com user e trip carregados
    reservation = await ReservationRepository.create(db, reservation) 
    
    # Atualiza vagas disponíveis
    await TripRepository.update(db, trip_id, {"available_seats": trip.available_seats - 1})
    
    return reservation

@router.get("/reservations/", response_model=List[ReservationOut])
async def list_reservations(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # list_by_user agora carrega user e trip, resolvendo o MissingGreenlet
    reservations = await ReservationRepository.list_by_user(db, current_user.id)
    return reservations

@router.put("/reservations/{reservation_id}/cancel/", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # <--- Usar o get_current_active_user
):
    # 1. Obter a reserva
    reservation = await ReservationRepository.get_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reserva não encontrada."
        )

    # --- VERIFICAÇÃO DE AUTORIZAÇÃO: Usuário logado deve ser o dono da reserva ---
    if reservation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para cancelar esta reserva."
        )

    # --- VERIFICAÇÃO DE STATUS: Impedir cancelamento de reserva já cancelada ---
    if reservation.status == ReservationStatusEnum.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # Ou 409 Conflict, como discutido. 400 é válido para "requisição inválida por causa do estado"
            detail="Esta reserva já está cancelada."
        )

    # Obter a viagem associada para verificar a data/hora
    trip = await TripRepository.get_by_id(db, reservation.trip_id)
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno: Viagem associada à reserva não encontrada."
        )

    # Verificação de prazo de cancelamento
    trip_datetime = datetime.combine(trip.date, trip.time)
    now = datetime.now()
    
    # 3. Impedir alteração de reservas expiradas (viagens que já aconteceram)
    if now >= trip_datetime:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Não é possível cancelar uma reserva expirada (a viagem já começou ou passou). {now}")


    cancellation_deadline = trip_datetime - timedelta(hours=CANCELLATION_WINDOW_HOURS)

    if now > cancellation_deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível cancelar a reserva: o prazo de cancelamento ({CANCELLATION_WINDOW_HOURS} horas antes da viagem) já passou."
        )

    # Atualizar o status da reserva para CANCELLED
    updated_reservation = await ReservationRepository.update(
        db, reservation_id, {"status": ReservationStatusEnum.CANCELLED}
    )

    # Incrementar assentos disponíveis na viagem
    await TripRepository.update(
        db, trip.id, {"available_seats": trip.available_seats + 1}
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)