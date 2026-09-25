ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm

FROM ${PYTHON_IMAGE} AS verilator-build
ARG VERILATOR_VERSION=5.040
ARG VERILATOR_TAG=v5.040
ARG VERILATOR_COMMIT=51cdf52d0f3a3e59b51fd87762646a851e9f4aff
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        autoconf \
        bison \
        flex \
        g++ \
        git \
        help2man \
        libfl-dev \
        make \
        perl \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/verilator
RUN git clone --filter=blob:none --no-checkout https://github.com/verilator/verilator.git . \
    && git checkout --detach "$VERILATOR_COMMIT" \
    && test "$(git rev-parse HEAD)" = "$VERILATOR_COMMIT" \
    && test "$(git describe --exact-match --tags HEAD)" = "$VERILATOR_TAG" \
    && autoconf \
    && ./configure --prefix=/opt/verilator \
    && make -j"$(nproc)" \
    && make install \
    && test "$(/opt/verilator/bin/verilator --version)" = "Verilator 5.040 2025-08-30 rev v5.040"

FROM ${PYTHON_IMAGE} AS package-build
ARG UV_VERSION=0.12.7
WORKDIR /opt/rtl-lens
COPY README.md pyproject.toml uv.lock ./
COPY src ./src
RUN python -m pip install --no-cache-dir "uv==$UV_VERSION" \
    && uv build --no-sources --out-dir /dist \
    && uv sync --locked --no-dev --no-install-project \
    && uv pip install --python /opt/rtl-lens/.venv/bin/python --no-deps /dist/*.whl

FROM ${PYTHON_IMAGE} AS runtime
ARG IMAGE_SOURCE=""
ARG IMAGE_VERSION=0.1.0.dev0
ARG VERILATOR_VERSION=5.040
ARG VERILATOR_COMMIT=51cdf52d0f3a3e59b51fd87762646a851e9f4aff
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libfl2 perl zlib1g \
    && rm -rf /var/lib/apt/lists/*
COPY --from=verilator-build /opt/verilator /opt/verilator
COPY --from=package-build /opt/rtl-lens/.venv /opt/rtl-lens/.venv
RUN groupadd --gid 10001 rtl-lens \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/rtl-lens rtl-lens \
    && mkdir /workspace \
    && chown 10001:10001 /workspace
LABEL org.opencontainers.image.title="RTL Lens" \
      org.opencontainers.image.version="$IMAGE_VERSION" \
      org.opencontainers.image.source="$IMAGE_SOURCE" \
      io.rtl-lens.verilator.version="$VERILATOR_VERSION" \
      io.rtl-lens.verilator.commit="$VERILATOR_COMMIT"
ENV HOME=/home/rtl-lens
ENV PATH="/opt/rtl-lens/.venv/bin:/opt/verilator/bin:$PATH"
WORKDIR /workspace
USER 10001:10001
ENTRYPOINT ["rtl-lens"]
CMD ["--help"]

FROM runtime AS test
USER root
RUN python -m pip install --no-cache-dir "pytest>=8.4,<9"
WORKDIR /app
COPY tests/knowledge ./tests/knowledge
COPY tests/fixtures/rules ./tests/fixtures/rules
USER 10001:10001

FROM runtime AS release
