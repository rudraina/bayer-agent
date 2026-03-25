FROM python:3.10-slim

WORKDIR /app

# Accept API key firmly during docker build
ARG GROQ_API_KEY
ENV GROQ_API_KEY=$GROQ_API_KEY

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
