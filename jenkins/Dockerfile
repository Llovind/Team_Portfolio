# Reproducible extension of the existing custom Jenkins image.
FROM docker:28.3.2-cli AS docker_cli

FROM jenkins-docker:lts
USER root
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
RUN docker compose version
