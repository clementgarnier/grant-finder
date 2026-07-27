FROM python:3.12-slim

WORKDIR /app
COPY irs-990/requirements.txt /app/mcp-servers/irs-990/requirements.txt
COPY grants-gov/requirements.txt /app/mcp-servers/grants-gov/requirements.txt
RUN pip install --no-cache-dir \
    -r /app/mcp-servers/irs-990/requirements.txt \
    -r /app/mcp-servers/grants-gov/requirements.txt

COPY . /app/mcp-servers/

EXPOSE 8000
CMD ["python", "/app/mcp-servers/combined_server.py"]
