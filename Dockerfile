FROM python:3.8-slim-buster as production

EXPOSE 80
WORKDIR /app

COPY requirements.txt .
COPY .env .

RUN pip install -r requirements.txt
ADD . /app/
RUN chmod +x scripts/*

