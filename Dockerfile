FROM almalinux:9.2-minimal

LABEL maintainer="appthreat" \
      org.opencontainers.image.authors="Team AppThreat <cloud@appthreat.com>" \
      org.opencontainers.image.source="https://github.com/appthreat/cpggen" \
      org.opencontainers.image.url="https://github.com/appthreat/cpggen" \
      org.opencontainers.image.version="1.7.1" \
      org.opencontainers.image.vendor="AppThreat" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.title="cpggen" \
      org.opencontainers.image.description="Generate CPG for multiple languages for use with joern" \
      org.opencontainers.docker.cmd="docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw -w /app -t ghcr.io/appthreat/cpggen cpggen --build"

ARG TARGETPLATFORM
ARG JAVA_VERSION=22.3.r19-grl
ARG SBT_VERSION=1.9.0
ARG MAVEN_VERSION=3.9.2
ARG GRADLE_VERSION=8.1.1

ENV ATOM_VERSION=1.0.0 \
    ATOM_HOME=/opt/atom-1.0.0 \
    ATOM_BIN_DIR=/opt/atom-1.0.0/bin/ \
    JOERN_HOME=/opt/joern-cli \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    JAVA_VERSION=$JAVA_VERSION \
    SBT_VERSION=$SBT_VERSION \
    MAVEN_VERSION=$MAVEN_VERSION \
    GRADLE_VERSION=$GRADLE_VERSION \
    GRADLE_OPTS="-Dorg.gradle.daemon=false" \
    JAVA_HOME="/opt/java/${JAVA_VERSION}" \
    MAVEN_HOME="/opt/maven/${MAVEN_VERSION}" \
    GRADLE_HOME="/opt/gradle/${GRADLE_VERSION}" \
    SBT_HOME="/opt/sbt/${SBT_VERSION}" \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING="utf-8" \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    JOERN_DATAFLOW_TRACKED_WIDTH=128 \
    ANDROID_HOME=/opt/android-sdk-linux
ENV PATH=${PATH}:/opt/atom-1.0.0/bin/:${JAVA_HOME}/bin:${MAVEN_HOME}/bin:${GRADLE_HOME}/bin:${SBT_HOME}/bin:/opt/joern-cli:/opt/joern-cli/bin:/usr/local/bin:/root/.local/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/tools:${ANDROID_HOME}/tools/bin:${ANDROID_HOME}/platform-tools:

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
    && microdnf module enable php -y \
    && microdnf install -y gcc gcc-c++ libstdc++-devel git-core php php-cli python3.11 python3.11-devel python3.11-pip pcre2 which tar zip unzip sudo \
        ncurses jq krb5-libs libicu openssl-libs compat-openssl11 zlib findutils \
        nodejs graphviz graphviz-gd graphviz-python3 glibc-common glibc-all-langpacks xorg-x11-fonts-75dpi xorg-x11-fonts-Type1 \
    && alternatives --install /usr/bin/python3 python /usr/bin/python3.11 1 \
    && python3 --version \
    && python3 -m pip install --upgrade pip \
    && curl -s "https://get.sdkman.io" | bash \
    && source "$HOME/.sdkman/bin/sdkman-init.sh" \
    && echo -e "sdkman_auto_answer=true\nsdkman_selfupdate_feature=false\nsdkman_auto_env=true" >> $HOME/.sdkman/etc/config \
    && sdk install java $JAVA_VERSION \
    && sdk install maven $MAVEN_VERSION \
    && sdk install gradle $GRADLE_VERSION \
    && sdk install sbt $SBT_VERSION \
    && sdk offline enable \
    && mv /root/.sdkman/candidates/* /opt/ \
    && rm -rf /root/.sdkman \
    && curl -LO https://github.com/AppThreat/atom/releases/latest/download/atom.zip \
    && curl -LO https://github.com/AppThreat/atom/releases/latest/download/atom.zip.sha512 \
    && echo "$(cat atom.zip.sha512 | cut -d ' ' -f1) atom.zip" | sha512sum -c \
    && unzip -q atom.zip -d /opt/ \
    && rm atom.zip atom.zip.sha512 \
    && ln -s /opt/atom-${ATOM_VERSION}/bin/atom /usr/local/bin/atom \
    && curl -LO https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/wkhtmltox-0.12.6.1-2.almalinux9.${ARCH_NAME}.rpm \
    && rpm -ivh wkhtmltox-0.12.6.1-2.almalinux9.${ARCH_NAME}.rpm \
    && rm wkhtmltox-0.12.6.1-2.almalinux9.${ARCH_NAME}.rpm \
    && curl -LO https://github.com/AppThreat/cpggen/releases/latest/download/joern-cli.zip \
    && unzip -q joern-cli.zip -d /opt/ \
    && rm joern-cli.zip \
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
    && mkdir -p /opt/joern/custom_scripts \
    && useradd -ms /bin/bash joern \
    && chown -R joern:joern /opt/joern \
    && npm install -g @cyclonedx/cdxgen --omit=optional \
    && python3 -m pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && cd /usr/local/src/ && poetry install --no-cache --without dev \
    && chmod a-w -R /opt \
    && rm -rf /var/cache/yum \
    && microdnf clean all

WORKDIR /app

CMD [ "cpggen" ]
