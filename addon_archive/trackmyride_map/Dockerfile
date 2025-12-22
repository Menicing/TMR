ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

ENV LANG C.UTF-8

RUN apk add --no-cache \
    python3 \
    py3-pip

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh

COPY app /app

EXPOSE 8099

CMD ["/run.sh"]
