FROM arm32v7/python:3.12.0-bullseye
WORKDIR /app
COPY . /app
RUN pip3 install -r requirements.txt

CMD ["python", "server.py"]
