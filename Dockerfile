# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.11

# Set the working directory to /
WORKDIR /src/

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy engine into the container
COPY /src /src