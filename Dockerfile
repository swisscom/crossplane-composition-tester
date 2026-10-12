ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION}

# Crossplane CLI v2.3+ runs the render engine in a Docker container, which is not available inside
# this image: keep the CLI below v2.3 here unless the Docker daemon is made available to the container.
ARG CROSSPLANE_VERSION=v2.0.8

RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/* && \
    curl -sL "https://raw.githubusercontent.com/crossplane/crossplane/main/install.sh" | env XP_VERSION="$CROSSPLANE_VERSION" sh && \
    mv crossplane /usr/local/bin

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    USER=appuser

RUN adduser --disabled-password --gecos "" ${USER}

USER ${USER}
ENV PATH="/home/${USER}/.local/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .

COPY environment.py .

COPY cucumber_json.py .

COPY parallel_runner.py .

COPY tests_runner.sh .

COPY steps/ ./steps

RUN pip install -r requirements.txt

ENTRYPOINT ["python3", "-m", "behave"]
