FROM python:3.12-slim

WORKDIR /app
COPY mcp-servers/irs-990/requirements.txt /app/mcp-servers/irs-990/requirements.txt
COPY mcp-servers/grants-gov/requirements.txt /app/mcp-servers/grants-gov/requirements.txt
RUN pip install --no-cache-dir \
    -r /app/mcp-servers/irs-990/requirements.txt \
    -r /app/mcp-servers/grants-gov/requirements.txt

COPY mcp-servers/ /app/mcp-servers/

EXPOSE 8000
CMD ["python", "/app/mcp-servers/combined_server.py"]
