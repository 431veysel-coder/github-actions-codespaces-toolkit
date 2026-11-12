# Standardized Android Build Environment (App Factory Builder)
FROM eclipse-temurin:17-jdk-jammy

# Environment variables
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

# Install essential build tools
RUN apt-get update && apt-get install -y \
    curl \
    git \
    unzip \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Android Command Line Tools
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdtools.zip && \
    unzip -q /tmp/cmdtools.zip -d ${ANDROID_HOME}/cmdline-tools && \
    mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest && \
    rm /tmp/cmdtools.zip

# Accept SDK licenses and install standard packages
RUN yes | sdkmanager --licenses && \
    sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

WORKDIR /workspace
