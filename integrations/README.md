# Integrations

Each folder lets another tool call PageVet's fixed rules. None of them calls a model or generates text; they score
text that a model wrote or that an agent is about to read.

| Folder | Tool | What it adds | Checked against |
|---|---|---|---|
| [`promptfoo/`](promptfoo/) | [promptfoo](https://www.promptfoo.dev/) | a Python assertion (`pagevet_assert.py`) that fails a test when the output contains text aimed at AI models, and an example config | promptfoo 0.126.0 (`npx promptfoo eval`) |
| [`garak/`](garak/) | [garak](https://github.com/NVIDIA/garak) | a detector, `pagevet.PageVetInjection`: 1.0 per output with a finding at or above medium | garak 0.17.1 (loaded through garak's plugin loader) |
| [`pyrit/`](pyrit/) | [PyRIT](https://github.com/Azure/PyRIT) | a true/false scorer, `PageVetScorer`, usable as an objective or output scorer | PyRIT 1.2.1 (in-memory database) |
| [`supabase/`](supabase/) | [Supabase](https://supabase.com/) (Postgres) | `schema.sql` and `load.py`: traffic, findings, crawler access and scores as tables, upserted through the REST API | offline tests with a stand-in HTTP client |
| [`hindsight/`](hindsight/) | [Hindsight](https://hindsight.vectorize.io/) (agent memory) | `remember.py`: dated observations from PageVet reports into a memory bank; `--ask` recalls and reflects | offline tests of the observations; written against `hindsight-client`'s retain, recall and reflect |
| [`n8n/`](n8n/) | [n8n](https://n8n.io/) | a workflow that calls `pagevet-serve`'s `POST /guard` between fetching a page and a model step | n8n workflow import |

The promptfoo, garak and PyRIT adapters are tested in `tests/test_docx_resume_mcp_tools.py`; the garak and PyRIT tests run when those
packages are installed (`uv run --with garak pytest tests/test_docx_resume_mcp_tools.py -k garak`). They live in this repository
only; nothing has been proposed to those projects.

Typical use: a red-team run asks a model to write pages, emails or documents, or an agent passes tool results along,
and PageVet checks whether the text now carries instructions for the next AI that reads it.
