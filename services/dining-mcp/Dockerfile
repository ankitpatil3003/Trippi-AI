FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8011
EXPOSE 8011
CMD ["python", "server.py"]
