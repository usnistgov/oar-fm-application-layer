# Official Python runtime as a parent image
FROM python:3.9.7-slim-buster

# Create 'fm' directory
RUN mkdir /fm

# Copy API into the image within 'fm' directory
COPY ./ /fm/

# Move to fm directory to install dependencies
WORKDIR /fm/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Adjust permissions
RUN chown -R www-data:www-data /fm

# Run app.py when the container launches
CMD ["python", "run.py"]