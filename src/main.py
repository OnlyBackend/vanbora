from fastapi import FastAPI
from src.presentation import routes

app = FastAPI(title="Vanbora - Sistema de Reserva de Vans")

app.include_router(routes.router) 