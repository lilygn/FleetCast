FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
COPY . .  
RUN pip install --no-cache-dir -r requirements.txt




EXPOSE 5000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5000"]
