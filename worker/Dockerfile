FROM python:3.12-slim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm -f /tmp/requirements.txt
RUN useradd --create-home --uid 10001 worker
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY worker/runner.py /opt/hds/runner.py
USER worker
ENTRYPOINT ["python","/opt/hds/runner.py"]
