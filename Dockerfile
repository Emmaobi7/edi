# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Copy project
COPY . /app/
COPY .env /app/
# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]