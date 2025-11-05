# Use official Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy dependency file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Expose the port your app runs on
EXPOSE 8090

# Start the app
CMD ["python", "app.py"]
