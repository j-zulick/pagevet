# The guard as a defense on AgentDojo (2026-11-25)

[AgentDojo](https://github.com/ethz-spylab/agentdojo) (MIT licence, version v1.2.2 of its tasks) is a public benchmark
for prompt injection against tool-using agents: 97 user tasks in four suites (workspace, travel, banking, slack), 35
injection tasks, and published attacks that put text into the data an agent's tools return (an email, a review, a
bill, a web page). This measures `pagevet.guard`, which removes lines of text that match PageVet's instruction
patterns, as a filter on every tool output. Only AgentDojo's own tasks and attacks are used; PageVet's patterns were
not changed for this, and nothing here was tuned on these cases.

Script: [`docs/bench/agentdojo_guard.py`](../agentdojo_guard.py). PageVet 1.1.0 rules (unchanged in 1.2.0).

## 1. Without a model: every tool output a correct agent reads
`python docs/bench/agentdojo_guard.py offline results-offline.json` runs each user task's ground-truth tool calls,
once on the clean data and once per (user task, injection task, attack) with the attack's text where that task reads
it, and passes every tool output through the guard. Result: [`results-offline.json`](results-offline.json). It is
reproduced by `uv run --with agentdojo pagevet-reproduce --agentdojo` (about 25 minutes; timing is not compared).

| Attack (AgentDojo's) | Pairs (user task × injection task) | Every injected output flagged | Goal removed by the guard |
|---|---:|---:|---:|
| `important_instructions` | 921 | 0 | 0 of 907 |
| `tool_knowledge` | 893 | 0 | 0 of 737 |
| `direct` ("TODO: …") | 935 | 0 | 0 of 935 |
| `ignore_previous` | 935 | 0 | 0 of 935 |
| `system_message` ("###(system_message) …") | 935 | 0 | 0 of 935 |
| `injecagent` ("IMPORTANT!!! Ignore all previous instructions …") | 935 | **753** | **231** of 935 |

"Goal removed" counts pairs where the injection task's goal reaches the agent word for word in the raw tool output and
is gone from every guarded output; pairs where AgentDojo's data formatting breaks the goal up are left out of that
column's total.

**False alarms:** 0 of the 339 clean tool outputs (all four suites) got a finding, and the guard changed none of them.

**Speed:** median guard time per tool output 5–32 ms by suite; 95th percentile 25–575 ms (workspace's long
outputs), single process.

**What this says.** PageVet's patterns are written for text on web pages that addresses an AI system or tells it to
ignore its instructions. Most of AgentDojo's attacks are written as a message from the user inside the data ("This is
an important message from me, Emma Johnson, to you…", "TODO: …"), and the patterns do not recognize them: the guard
catches only InjecAgent's "Ignore all previous instructions" text, and removes the goal itself in a quarter of those
pairs, where it sits on the same line. (AgentDojo's `ignore_previous` attack spells "iunstructions", so the override
pattern does not match it either.) As a defense against these attacks the guard does little; it costs nothing in
false alarms. A rule developed from these attacks would be tuned on the test set, so none was added.

**Tasks still completed.** The guard changed none of the 339 clean tool outputs that the correct tool calls return,
so on AgentDojo's tasks without an attack, an agent making those calls behind the guard reads exactly the data it
would read without it. (An agent that calls other tools reads other outputs, which this does not cover; the model run
below measures that end to end.) Under attack the guard changed only outputs carrying InjecAgent's text.

## 2. Next: the same run with a local model
`python docs/bench/agentdojo_guard.py agent OUT.json --suite banking --model <ollama model>` runs AgentDojo's own
benchmark with a model served by Ollama, with and without the guard on every tool output, and records utility,
utility under attack and targeted attack success as AgentDojo scores them. A run on one suite with a small local
model is in progress; its results, with the model, attack and run-to-run variation, go in a later 1.2.x release.
