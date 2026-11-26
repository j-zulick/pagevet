# PageVet as a container: the scanner, pagevet-access and the MCP server, running as a non-root user.
#   docker run --rm ghcr.io/j-zulick/pagevet https://example.com/
#   docker run --rm --entrypoint pagevet-access ghcr.io/j-zulick/pagevet https://example.com/
#   docker run --rm -i --entrypoint pagevet-mcp ghcr.io/j-zulick/pagevet      # MCP over stdio
FROM python:3.13-slim AS build
WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

FROM python:3.13-slim
LABEL org.opencontainers.image.source="https://github.com/j-zulick/pagevet" \
      org.opencontainers.image.description="Find text in web pages aimed at AI models, and check which AI crawlers may read them." \
      org.opencontainers.image.licenses="MIT"
COPY --from=build /dist /dist
RUN pip install --no-cache-dir "$(ls /dist/*.whl)[mcp,pdf]" && rm -rf /dist \
 && useradd --create-home --uid 10001 pagevet
USER pagevet
WORKDIR /work
ENTRYPOINT ["pagevet"]
CMD ["--help"]
