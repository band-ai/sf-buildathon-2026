FROM python:3.12-alpine
WORKDIR /app
# Browser sessions run Chromium; the page server answers them over HTTPS with a self-signed
# certificate, which Chromium is told to accept.
# Chromium runs as its own user, which cannot open /data, where the corpus and its key are
# mounted. tini reaps the processes a closed browser leaves behind.
RUN apk add --no-cache chromium openssl tini \
 && adduser -D -H chromium && mkdir -m 700 /data \
 && openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=test" \
      -addext "subjectAltName=DNS:*.test" -keyout /app/key.pem -out /app/cert.pem
COPY mockweb/ mockweb/
EXPOSE 8080
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "-u", "-m", "mockweb"]
