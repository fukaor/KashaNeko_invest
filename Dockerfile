# Python base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Create logs directory
RUN mkdir -p data/logs

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set the python path to the app root to allow imports from src
ENV PYTHONPATH=/app

# Copy the application code
# This is useful for caching, but will be overlaid by the volume mount in dev
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the FastAPI application with reload
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]