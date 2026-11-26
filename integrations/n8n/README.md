# PageVet in n8n

`pagevet-serve` runs PageVet as a small local HTTP API; n8n calls it with an ordinary HTTP Request node. No custom node to install.

1. Where n8n can reach it, run `pagevet-serve` (default `http://127.0.0.1:8790`; `--host 0.0.0.0 --port 8790` inside a private Docker network, never on a public address). With Docker: `docker run --rm -p 127.0.0.1:8790:8790 --entrypoint pagevet-serve ghcr.io/j-zulick/pagevet --host 0.0.0.0`.
2. In n8n: Workflows → Import from file → `pagevet-guard.workflow.json`. Set the environment variable `PAGEVET_SERVE_URL` for n8n if the API is not at `http://127.0.0.1:8790`.
3. Put your AI step after **Text for the AI step**. Pages with a finding at or above the policy (`high` by default) go to **Blocked: review findings** instead.

The API: `POST /scan` and `POST /guard` take `{"url": "…"}` or `{"html": "…", "source": "name"}` (`/guard` also `"policy": "high" | "medium" | "never"`); `GET /health`. URLs that resolve to private addresses are refused, as in the MCP server.

Not tested against a running n8n from this repository: the workflow file is checked for structure by `tests/test_guard_serve_receipts.py`.
