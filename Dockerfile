# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11-slim

EXPOSE 8002

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

COPY . /usr/src/app
WORKDIR /usr/src/app

# Install pip requirements
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["./manage.py", "runserver", "0.0.0.0:8001"]  # as before
