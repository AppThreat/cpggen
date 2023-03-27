FROM almalinux/9-minimal:latest

LABEL maintainer="appthreat" \
      org.opencontainers.image.authors="Team AppThreat <cloud@appthreat.com>" \
      org.opencontainers.image.source="https://github.com/appthreat/cpggen" \
      org.opencontainers.image.url="https://github.com/appthreat/cpggen" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.vendor="AppThreat" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.title="cpggen" \
      org.opencontainers.image.description="Generate CPG for multiple languages for use with joern" \
      org.opencontainers.docker.cmd="docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw --cpus=4 --memory=16g -t ghcr.io/appthreat/cpggen cpggen -i /app -o /app/cpg_out"

ENV JOERN_HOME=/opt/joern/joern-cli \
    GOPATH=/opt/app-root/go \
    GO_VERSION=1.20.2 \
    CGO_ENABLED=0 \
    PYTHONUNBUFFERED=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    JOERN_DATAFLOW_TRACKED_WIDTH=128 \
    PATH=${PATH}:/opt/joern/joern-cli:/opt/joern/joern-cli/bin:${GOPATH}/bin:/usr/local/go/bin:/usr/local/bin/:/root/.local/bin:

COPY . /usr/local/src/

RUN microdnf install -y gcc git-core php php-cli python3 python3-devel pcre2 which tar zip unzip sudo java-1.8.0-openjdk-headless \
        java-17-openjdk-headless ncurses jq krb5-libs libicu openssl-libs compat-openssl11 zlib \
        dotnet-sdk-7.0 dotnet-targeting-pack-7.0 dotnet-templates-7.0 dotnet-hostfxr-7.0 \
    && curl -LO https://github.com/joernio/joern/releases/latest/download/joern-install.sh \
    && chmod +x ./joern-install.sh \
    && ./joern-install.sh \
    && curl -LO "https://dl.google.com/go/go${GO_VERSION}.linux-amd64.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz \
    && rm go${GO_VERSION}.linux-amd64.tar.gz \
    && curl -L $(curl -L https://www.shiftleft.io/download/java2cpg.json | jq -r ".downloadURL") -o /opt/joern/joern-cli/java2cpg.jar \
    && curl -L $(curl -L https://www.shiftleft.io/download/go2cpgmanifest-linux-x64.json | jq -r ".downloadURL") -o /opt/joern/joern-cli/go2cpg \
    && chmod +x /opt/joern/joern-cli/go2cpg && go2cpg version \
    && curl -L $(curl -L https://www.shiftleft.io/download/csharp2cpg-linux-x64.json | jq -r ".downloadURL") -o /opt/joern/joern-cli/csharp2cpg.zip \
    && cd /opt/joern/joern-cli/ && unzip csharp2cpg.zip && rm /opt/joern/joern-cli/csharp2cpg.zip \
    && chmod +x /opt/joern/joern-cli/bin/csharp2cpg \
    && mkdir -p /opt/joern/custom_scripts \
    && useradd -ms /bin/bash joern \
    && chown -R joern:joern /opt/joern \
    && python -m pip install --no-cache-dir poetry==1.3.2 \
    && poetry config virtualenvs.create false \
    && cd /usr/local/src/ && poetry install --no-cache --without dev \
    && rm /joern-cli.zip /joern-install.sh \
    && rm -rf /var/cache/yum \
    && microdnf clean all

WORKDIR /app

CMD [ "cpggen" ]
