FROM python:3.13-slim
RUN pip install --no-cache-dir pytest==8.4.2 httpx==0.28.1 && useradd -u 10001 -M t
WORKDIR /tests
COPY functional ./functional
USER 10001
ENTRYPOINT ["pytest", "-q", "-p", "no:cacheprovider", "functional"]
