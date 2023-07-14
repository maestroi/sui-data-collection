# Use an Alpine base image
FROM python:3.11-alpine

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN apk --no-cache add gcc musl-dev libffi-dev openssl-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del gcc musl-dev libffi-dev openssl-dev

# Copy the source code into the container
COPY main.py config.json ./

# Run your program when the container starts
CMD ["python", "main.py"]
