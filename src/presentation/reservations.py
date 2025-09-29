from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from src.domain.schemas import ReservationOut, ReservationStatus, ReservationUpdate, ReservationCreate, PaymentMethod, PaymentStatus, ReservationResponse
from src.domain.models import Reservation, Trip, User, ReservationStatusEnum
from src.infra.database import get_db
from src.infra.auth import get_current_active_user
from src.infra.repositories import ReservationRepository, TripRepository
from datetime import datetime, timedelta, timezone
import mercadopago

router = APIRouter()

# credenciais do Mercado Pago
MERCADOPAGO_ACCESS_TOKEN = "TEST-7009980541868121-091619-9f68f29a35eab3133ad2c92386e7824b-2697364246"  # substitui pelo seu
NOTIFICATION_URL = "https://seu-dominio.com/webhook/mercadopago"

# inicializa o SDK
sdk = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)

CANCELLATION_WINDOW_HOURS = 2
ENABLE_ALTERATION_DEADLINE = True

@router.post("/trips/{trip_id}/reserve/", response_model=ReservationResponse)
async def reserve_trip(
    trip_id: int,
    payload: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # 1. Busca viagem
    trip = await TripRepository.get_by_id(db, trip_id)
    if not trip or trip.available_seats <= 0:
        raise HTTPException(status_code=400, detail="Trip not available or full")

    # 2. Verifica se usuário já reservou
    reservations = await ReservationRepository.list_by_trip(db, trip_id)
    if any(r.user_id == current_user.id for r in reservations):
        raise HTTPException(status_code=400, detail="You already have a reservation for this trip")

    # 3. Cria reserva
    reservation = Reservation(
        user_id=current_user.id,
        trip_id=trip_id,
        payment_method=payload.payment_method,
        price_at_reservation=trip.price,
        status=ReservationStatus.CONFIRMED,  # padrão inicial
    )

    # Dinheiro = aprovado direto, senão pendente
    reservation.payment_status = (
        PaymentStatus.APPROVED
        if payload.payment_method == PaymentMethod.CASH
        else PaymentStatus.PENDING
    )

    reservation = await ReservationRepository.create(db, reservation)

    # 4. Caso PIX → cria pagamento no Mercado Pago
    if payload.payment_method == PaymentMethod.PIX:
        payment_data = {
            "transaction_amount": float(trip.price),
            "description": f"Reserva VanBora - Trip {trip_id}",
            "payment_method_id": "pix",
            "payer": {"email": current_user.email},
            "binary_mode": True,
            "notification_url": NOTIFICATION_URL,
        }
        mp_response = sdk.payment().create(payment_data)
        mp_payment = mp_response["response"]

        # Atualiza reserva com dados do pagamento
        reservation = await ReservationRepository.update(
            db,
            reservation.id,
            {
                "payment_id": str(mp_payment.get("id")),
                "payment_status": PaymentStatus.PENDING,
            }
        )

        return ReservationResponse(
            reservation=ReservationOut.from_orm(reservation),
            pix_qr_code=mp_payment["point_of_interaction"]["transaction_data"]["qr_code_base64"],
            pix_copia_cola=mp_payment["point_of_interaction"]["transaction_data"]["qr_code"],
        )
    # só reduz assento se pagamento NÃO for PIX
    if payload.payment_method == PaymentMethod.CASH:
        await TripRepository.update(db, trip_id, {"available_seats": trip.available_seats - 1})


    return ReservationResponse(reservation=reservation)

@router.post("/webhook/mercadopago")
async def webhook_mercadopago(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook do Mercado Pago.
    Consulta o status real do pagamento no Mercado Pago.
    """

    payment_id = payload.get("data", {}).get("id")
    if not payment_id:
        return {"status": "ignored", "reason": "no payment_id"}

    # Consulta real no Mercado Pago
    mp_payment = sdk.payment().get(payment_id)["response"]
    status = mp_payment.get("status")

    # Busca a reserva
    result = await db.execute(
        select(Reservation)
        .options(
            selectinload(Reservation.trip).selectinload(Trip.driver)  # carrega trip + driver
        )
        .where(Reservation.payment_id == str(payment_id))
    )
    reservation = result.scalars().first()

    if not reservation:
        return {"status": "ignored", "reason": "reservation not found"}

    trip = reservation.trip
    driver = trip.driver

    if status == "approved":
        reservation.payment_status = PaymentStatus.APPROVED
        reservation.status = ReservationStatus.CONFIRMED

        valor_pago = reservation.price_at_reservation

        if trip.cancelable:
            driver.balance = driver.balance + valor_pago
        else:
            try:
                payout_payload = {
                    "amount": float(valor_pago),
                    "currency_id": "BRL",
                    "payment_method_id": "pix",
                    "recipient": {
                        "pix_key": driver.pix_key
                    },
                    "external_reference": f"reservation_{reservation.id}",
                    "description": f"Payout reserva {reservation.id} - viagem {trip.id}"
                }

                mp_payout_response = sdk.post("/v1/payouts", payout_payload)
                mp_payout = mp_payout_response.get("response", {})

                if hasattr(reservation, "payout_id") and mp_payout.get("id"):
                    reservation.payout_id = str(mp_payout.get("id"))
                if hasattr(reservation, "payout_status") and mp_payout.get("status"):
                    reservation.payout_status = mp_payout.get("status")

            except Exception as exc:
                # fallback: creditar saldo localmente se o payout falhar
                driver.balance = driver.balance + valor_pago
                print(f"Erro ao enviar PIX via Mercado Pago para {driver.pix_key}: {exc}")

        trip.available_seats = trip.available_seats - 1

    elif status in ["cancelled", "rejected", "refunded"]:
        reservation.payment_status = PaymentStatus.REJECTED
        reservation.status = ReservationStatus.CANCELLED

    await db.commit()
    return {"status": "ok"}

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
    
    if not trip.cancelable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta viagem não permite cancelamento."
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

# @router.delete("/reservations/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_reservation(
#     reservation_id: int,
#     db: AsyncSession = Depends(get_db),
#     current_user: User = Depends(get_current_active_user)
# ):
#     # Busca reserva
#     reservation = await ReservationRepository.get_by_id(db, reservation_id)
#     if not reservation:
#         raise HTTPException(status_code=404, detail="Reservation not found")

#     # Busca viagem relacionada
#     trip = await TripRepository.get_by_id(db, reservation.trip_id)

#     # Autorização: dono da reserva ou motorista da viagem
#     if reservation.user_id != current_user.id and trip.driver_id != current_user.id:
#         raise HTTPException(status_code=403, detail="Not authorized to delete this reservation")

#     # Devolve assento
#     await TripRepository.update(
#         db,
#         trip.id,
#         {"available_seats": trip.available_seats + 1}
#     )

#     # Remove reserva
#     await ReservationRepository.delete(db, reservation.id)

#     return {"detail": "Reservation deleted successfully"}