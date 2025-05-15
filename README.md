# Vanbora App

Sistema de reserva digital para transporte alternativo (van)

## Funcionalidades do MVP
- Cadastro e login de clientes e motoristas
- Cadastro e visualização de viagens
- Reserva de vagas em viagens
- Visualização de passageiros confirmados (motorista)

## Tecnologias
- FastAPI
- PostgreSQL
- SQLAlchemy (async)
- Docker & Docker Compose
- Poetry

## Como rodar o projeto

1. Clone o repositório
2. Copie o arquivo `.env.example` para `.env` e ajuste as variáveis se necessário
3. Rode:

```bash
docker-compose up --build
```

A API estará disponível em http://localhost:8000/docs

## Endpoints principais
Veja a documentação automática em `/docs` após subir o projeto. 