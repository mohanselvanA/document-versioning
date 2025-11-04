# Use official Python image
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Load environment variables from .env (Docker Compose handles it)
EXPOSE 8000

# Start the app
CMD ["python", "app.py"]
