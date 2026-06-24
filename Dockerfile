FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend.py frontend.py assistant_logic.py gigachat.py db.py cities.db ./

EXPOSE 8000 8501

CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
