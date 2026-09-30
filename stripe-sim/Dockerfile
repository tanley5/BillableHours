FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

ENV STRIPE_SIM_PUBLIC_BASE=http://localhost:12111
EXPOSE 12111
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12111"]
