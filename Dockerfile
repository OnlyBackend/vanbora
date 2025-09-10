FROM python:3.10-slim

# Define o fuso horário para o contêiner
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Doppler CLI
RUN apt-get update && apt-get install -y apt-transport-https gcc ca-certificates curl gnupg build-essential  libssl-dev libffi-dev openssl ca-certificates && \
curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
apt-get update && \
apt-get -y install doppler poppler-utils libpango-1.0-0 libgdk-pixbuf-xlib-2.0-0 libffi-dev libcairo2 &&\
rm -rf /var/lib/apt/lists/*

# Instala Poetry
RUN pip install --upgrade pip && pip install poetry

# Copia arquivos do projeto
COPY pyproject.toml poetry.lock* /app/

# Instala dependências do projeto
RUN poetry config virtualenvs.create false && poetry install --no-root --no-interaction --no-ansi

COPY . /app

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"] 