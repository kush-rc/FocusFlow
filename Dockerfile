# Use Python 3.10 slim as base for a smaller image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies for OpenCV, MediaPipe, and C++ compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Compile the C++ engagement module
RUN python setup.py build_ext --inplace

# Expose the port used by Hugging Face Spaces
EXPOSE 7860

# Run the application with uvicorn
# We use 0.0.0.0 to allow external access and 7860 as the port
CMD ["python", "src/main.py"]
