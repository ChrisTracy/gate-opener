# set base image (host OS)
FROM arm32v7/python:3.7-alpine

# set the working directory in the container
WORKDIR /app

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip3 install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY . /app

# command to run on container start
CMD [ "python", "./GateV3.py" ]

#Expose port 5151
EXPOSE 5151/tcp
