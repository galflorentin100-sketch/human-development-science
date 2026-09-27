FROM python:3.12-slim

RUN useradd --create-home --uid 10001 worker
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY worker/runner.py /opt/hds/runner.py
USER worker
ENTRYPOINT ["python","/opt/hds/runner.py"]
