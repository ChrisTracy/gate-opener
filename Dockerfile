FROM arm32v7/python:3.11
WORKDIR /app
COPY . /app
RUN pip3 install -r requirements.txt

CMD ["python", "server.py"]
