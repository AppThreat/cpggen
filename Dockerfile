FROM almalinux:9.2-minimal

LABEL maintainer="appthreat" \
      org.opencontainers.image.authors="Team AppThreat <cloud@appthreat.com>" \
      org.opencontainers.image.source="https://github.com/appthreat/cpggen" \
      org.opencontainers.image.url="https://github.com/appthreat/cpggen" \
      org.opencontainers.image.version="1.4.0" \
      org.opencontainers.image.vendor="AppThreat" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.title="cpggen" \
      org.opencontainers.image.description="Generate CPG for multiple languages for use with joern" \
      org.opencontainers.docker.cmd="docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw -w /app -t ghcr.io/appthreat/cpggen cpggen --build"

ARG TARGETPLATFORM

ENV JOERN_HOME=/usr/local/bin \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    GOROOT=/usr/local/go \
    GO_VERSION=1.19.9 \
    SBT_VERSION=1.9.0 \
    GRADLE_VERSION=8.1.1 \
    GRADLE_HOME=/opt/gradle-8.1.1 \
    GRADLE_OPTS="-Dorg.gradle.daemon=false" \
    JAVA_HOME="/etc/alternatives/jre_17" \
    JAVA_17_HOME="/etc/alternatives/jre_17" \
    JAVA_8_HOME="/usr/lib/jvm/jre-1.8.0" \
    CGO_ENABLED=1 \
    GO111MODULE="" \
    GOOS="linux" \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING="utf-8" \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    JOERN_DATAFLOW_TRACKED_WIDTH=128 \
    ANDROID_HOME=/opt/android-sdk-linux \
    PATH=${PATH}:/opt/joern/joern-cli:/opt/joern/joern-cli/bin:/usr/local/go/bin:/usr/local/bin:/root/.local/bin:/opt/sbt/bin:/usr/local/go/pkg/tool/linux_amd64:${JAVA_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/tools:${ANDROID_HOME}/tools/bin:${ANDROID_HOME}/platform-tools:

COPY . /usr/local/src/

RUN set -e; \
    ARCH_NAME="$(rpm --eval '%{_arch}')"; \
    case "${ARCH_NAME##*-}" in \
        'x86_64') \
            OS_ARCH_SUFFIX='amd64'; \
            GOBIN_SUFFIX='x64'; \
            ;; \
        'aarch64') \
            OS_ARCH_SUFFIX='arm64'; \
            GOBIN_SUFFIX='arm64'; \
            ;; \
        *) echo >&2 "error: unsupported architecture: '$ARCH_NAME'"; exit 1 ;; \
    esac; \
    echo -e "[nodejs]\nname=nodejs\nstream=20\nprofiles=\nstate=enabled\n" > /etc/dnf/modules.d/nodejs.module \
    && microdnf module enable maven php -y \
    && microdnf install -y gcc gcc-c++ libstdc++-devel git-core php php-cli python3.11 python3.11-devel python3.11-pip pcre2 which tar zip unzip sudo \
        java-17-openjdk-headless java-1.8.0-openjdk-headless maven ncurses jq krb5-libs libicu openssl-libs compat-openssl11 zlib \
        dotnet-sdk-7.0 dotnet-targeting-pack-7.0 dotnet-templates-7.0 dotnet-hostfxr-7.0 nodejs graphviz graphviz-gd graphviz-python3 glibc-common glibc-all-langpacks xorg-x11-fonts-75dpi \
    && alternatives --install /usr/bin/python3 python /usr/bin/python3.11 1 \
    && python3 --version \
    && python3 -m pip install --upgrade pip \
    && curl -LO https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox-0.12.6.1-2.almalinux9.${ARCH_NAME}.rpm \
    && rpm -ivh wkhtmltox-0.12.6.1-2.almalinux9.${ARCH_NAME}.rpm \
    && rm wkhtmltox-0.12.6.1-2.almalinux9.${ARCH_NAME}.rpm \
    && curl -LO "https://dl.google.com/go/go${GO_VERSION}.linux-${OS_ARCH_SUFFIX}.tar.gz" \
    && tar -C /usr/local -xzf go${GO_VERSION}.linux-${OS_ARCH_SUFFIX}.tar.gz \
    && rm go${GO_VERSION}.linux-${OS_ARCH_SUFFIX}.tar.gz \
    && go install github.com/magefile/mage@latest \
    && curl -LO https://github.com/appthreat/joern/releases/latest/download/joern-install.sh \
    && chmod +x ./joern-install.sh \
    && ./joern-install.sh --without-plugins \
    && curl -LO "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
    && unzip -q gradle-${GRADLE_VERSION}-bin.zip -d /opt/ \
    && chmod +x /opt/gradle-${GRADLE_VERSION}/bin/gradle \
    && rm gradle-${GRADLE_VERSION}-bin.zip \
    && ln -s /opt/gradle-${GRADLE_VERSION}/bin/gradle /usr/local/bin/gradle \
    && curl -LO "https://github.com/sbt/sbt/releases/download/v${SBT_VERSION}/sbt-${SBT_VERSION}.zip" \
    && unzip -q sbt-${SBT_VERSION}.zip -d /opt/ \
    && chmod +x /opt/sbt/bin/sbt \
    && rm sbt-${SBT_VERSION}.zip \
    && mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && curl -L https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip -o ${ANDROID_HOME}/cmdline-tools/android_tools.zip \
    && unzip ${ANDROID_HOME}/cmdline-tools/android_tools.zip -d ${ANDROID_HOME}/cmdline-tools/ \
    && rm ${ANDROID_HOME}/cmdline-tools/android_tools.zip \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && yes | /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager --licenses --sdk_root=/opt/android-sdk-linux \
    && /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager 'platform-tools' --sdk_root=/opt/android-sdk-linux \
    && /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager 'platforms;android-33' --sdk_root=/opt/android-sdk-linux \
    && /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager 'build-tools;33.0.0' --sdk_root=/opt/android-sdk-linux \
    && curl -L $(curl -L https://www.shiftleft.io/download/java2cpg.json | jq -r ".downloadURL") -o /usr/local/bin/java2cpg.jar \
    && echo -e "#!/usr/bin/env bash\njava -jar /usr/local/bin/java2cpg.jar $*" > /usr/local/bin/java2cpg.sh \
    && chmod +x /usr/local/bin/java2cpg.sh \
    && curl -L $(curl -L https://www.shiftleft.io/download/go2cpgmanifest-linux-${GOBIN_SUFFIX}.json | jq -r ".downloadURL") -o /opt/joern/joern-cli/bin/go2cpg \
    && chmod +x /opt/joern/joern-cli/bin/go2cpg && go2cpg version \
    && ln -s /opt/joern/joern-cli/bin/go2cpg /usr/local/bin/go2cpg \
    && curl -L $(curl -L https://www.shiftleft.io/download/csharp2cpg-linux-${GOBIN_SUFFIX}.json | jq -r ".downloadURL") -o /opt/joern/joern-cli/csharp2cpg.zip \
    && cd /opt/joern/joern-cli/ && unzip csharp2cpg.zip && rm /opt/joern/joern-cli/csharp2cpg.zip \
    && chmod +x /opt/joern/joern-cli/bin/csharp2cpg \
    && ln -s /opt/joern/joern-cli/bin/csharp2cpg /usr/local/bin/csharp2cpg \
    && curl "https://cdn.shiftleft.io/download/sl" > /usr/local/bin/sl \
    && chmod a+rx /usr/local/bin/sl \
    && mkdir -p /opt/joern/custom_scripts \
    && useradd -ms /bin/bash joern \
    && chown -R joern:joern /opt/joern \
    && npm install -g @cyclonedx/cdxgen --omit=optional \
    && python3 -m pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && cd /usr/local/src/ && poetry install --no-cache --without dev \
    && rm /joern-cli.zip /joern-install.sh \
    && rm -rf /var/cache/yum \
    && microdnf clean all

WORKDIR /app

CMD [ "cpggen" ]
