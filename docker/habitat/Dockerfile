# syntax=docker/dockerfile:1.7
# Habitat: Absurd's read-only web dashboard (queues, tasks, runs, checkpoints, events).
# It has NO built-in auth -- for local development only, never expose publicly.
FROM debian:bookworm-slim
ARG ABSURD_VERSION=0.5.1
ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && case "${TARGETARCH}" in \
         amd64) asset=habitat-linux-x86_64 ;; \
         arm64) asset=habitat-linux-arm64 ;; \
         *) echo "unsupported arch: ${TARGETARCH}" >&2; exit 1 ;; \
       esac \
    && curl -fsSL -o /usr/local/bin/habitat \
         "https://github.com/earendil-works/absurd/releases/download/${ABSURD_VERSION}/${asset}" \
    && chmod +x /usr/local/bin/habitat \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
USER nobody
EXPOSE 7890
ENTRYPOINT ["habitat", "run"]
