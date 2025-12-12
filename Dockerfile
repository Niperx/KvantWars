FROM python:3.11-slim
EXPOSE 5000
WORKDIR /app

COPY requirements.txt ./

RUN python -m venv .venv
RUN .venv/bin/pip install --upgrade pip
RUN .venv/bin/pip install -r requirements.txt

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

RUN python init_db.py

CMD ["python", "app.py"]