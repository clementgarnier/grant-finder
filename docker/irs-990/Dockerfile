FROM python:3.12-slim

WORKDIR /app
COPY mcp-servers/irs-990/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers/irs-990/server.py /app/server.py

EXPOSE 8000
CMD ["python", "/app/server.py"]
