# set base image (host OS)
FROM arm32v7/python:3.7-buster

# set the working directory in the container
WORKDIR /app

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip3 install -r requirements.txt

# Intall the rpi.gpio python module
RUN pip3 install --no-cache-dir rpi.gpio

# copy the content of the local src directory to the working directory
COPY . /app

# command to run on container start
CMD [ "python", "./server.py" ]

#Expose port 5151
EXPOSE 5151/tcp
