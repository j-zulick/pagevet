# Roadmap

What each release added is in the [CHANGELOG](../CHANGELOG.md). Next, in order:

- **AgentDojo with a local model:** attack success and task completion end to end, with and without the guard, on the attack the patterns recognize; published only with a measured run-to-run noise floor ([`docs/bench/2026-11-25-agentdojo-guard/`](bench/2026-11-25-agentdojo-guard/)).
- **Live checks of the optional services** ([`docs/bench/2026-11-25-live/`](bench/2026-11-25-live/)): the Firecrawl source passed (2026-11-25). Still to run: the crawlee-server source, Langfuse records, and the Jev and `llm` second opinions on BIPIA and clean pages with costs recorded.
- **Second opinions measured:** each optional model gets a dated run on the same sets as the patterns before any accuracy is claimed for it (ProtectAI's classifier has one: [`docs/bench/2026-11-25-head-to-head/`](bench/2026-11-25-head-to-head/)).

Not planned: generating injections, or any feature aimed at defeating other detectors.
