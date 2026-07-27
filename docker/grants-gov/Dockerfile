FROM python:3.12-slim

WORKDIR /app
COPY mcp-servers/grants-gov/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers/grants-gov/server.py /app/server.py

EXPOSE 8001
CMD ["python", "/app/server.py"]
