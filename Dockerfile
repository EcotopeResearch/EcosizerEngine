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
COPY /engine /src/engine

# Copy data folder into the container
COPY /data /src/data

# Copy constants folder into the container
COPY /constants /src/constants

# Copy objects folder into the container
COPY /objects /src/objects

# Copy objects folder into the container
COPY /tests /src/tests