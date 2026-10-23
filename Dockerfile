FROM python:3.12-slim

# openssl CLI lets the scanner read the negotiated key-exchange group (e.g. X25519MLKEM768)
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home app
WORKDIR /app
COPY pyproject.toml README.md constraints.txt ./
COPY qday ./qday
RUN pip install --no-cache-dir -c constraints.txt ".[app]"
COPY app.py serve.py ./
COPY landing ./landing
COPY .streamlit ./.streamlit
COPY results ./results
COPY samples ./samples

USER app
EXPOSE 8501
# landing page at /, dashboard at /app/ (Streamlit runs internally on 8502)
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/app/_stcore/health')"
CMD ["python", "serve.py", "--host", "0.0.0.0", "--port", "8501"]
