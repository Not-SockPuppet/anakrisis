# Use Python slim image
FROM python:3.14-slim

# Ownership marker for the official MCP registry, plus standard image metadata.
LABEL io.modelcontextprotocol.server.name="io.github.Not-SockPuppet/anakrisis" \
      org.opencontainers.image.title="anakrisis" \
      org.opencontainers.image.description="Ethics-aware OSINT investigation planning and risk evaluation, delivered as an MCP server." \
      org.opencontainers.image.source="https://github.com/Not-SockPuppet/anakrisis" \
      org.opencontainers.image.licenses="MIT"

# Set working directory
WORKDIR /app

# Set Python unbuffered mode
ENV PYTHONUNBUFFERED=1

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code and doctrine files
COPY anakrisis.py .
COPY doctrine/ ./doctrine/
COPY playbooks/ ./playbooks/
COPY report_templates/ ./report_templates/

# Create non-root user
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Run the server
CMD ["python", "anakrisis.py"]
