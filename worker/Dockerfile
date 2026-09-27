FROM python:3.12-slim

RUN useradd --create-home --uid 10001 worker
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt /opt/hds/requirements.txt
RUN pip install --no-cache-dir -r /opt/hds/requirements.txt
COPY worker/runner.py /opt/hds/runner.py
USER worker
ENTRYPOINT ["python","/opt/hds/runner.py"]
