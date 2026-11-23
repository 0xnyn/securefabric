# syntax=docker/dockerfile:1.7
# absurdctl (Absurd's admin CLI) with psql, so you don't need either installed locally.
#   make absurdctl ARGS="list-queues"
FROM python:3.13-slim
ARG ABSURD_VERSION=0.5.1
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "absurdctl==${ABSURD_VERSION}"
USER nobody
ENTRYPOINT ["absurdctl"]
CMD ["help"]
