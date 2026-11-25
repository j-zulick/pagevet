# deepset/prompt-injections, test split (2026-11-25)

**Data.** [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) (Apache-2.0), test split: 116 prompts, 60 labelled injection, 56 ordinary. Built with `docs/bench/deepset_build.py` from the Hugging Face datasets server at run time (not copied here); built file SHA-256 `5d20eee5a21c8253…`.

**Run.** `uv run pagevet-bench cases.jsonl --out results-patterns.json` with PageVet 0.4.0 patterns.

| Detector | Injections caught | Ordinary prompts flagged |
|---|---|---|
| PageVet patterns | **2 of 60** (3.3%, 95% CI 0.9–11.4%) | 0 of 56 (0–6.4%) |

**What this says.** This set is prompts typed into a chatbot, about a third of the injections in German (a simple word check), most asking the model to take a new role or drop its task in ordinary words ("I want you to act as an interviewer…", "But now come new tasks. Forget everything we've talked about…"). PageVet looks for text planted in web pages and addressed to AI systems that read them; it has no rule for most of these phrasings, and none is tuned on this set. It is a second, independent measure of the gap the evasion report shows for reworded instructions, not a measure of page scanning. The open-weights classifier comparison on the same cases is published with the head-to-head results.
