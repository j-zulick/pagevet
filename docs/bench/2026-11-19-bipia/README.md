# Detector on BIPIA text attacks (Nov 19, 2026)

**Question.** How much of a public indirect-injection benchmark do PageVet's patterns catch, and how often do they fire on clean text?

**Data.** [BIPIA](https://github.com/microsoft/BIPIA) (Microsoft, MIT), commit `a004b69`, EmailQA contexts and the 75 test text attacks (15 categories × 5). `docs/bench/scripts/bipia_build.py` places every attack in each of the 50 test emails (end, middle or start): 3,750 injected cases and 50 clean ones. Built file SHA-256 `65c40e2a…3148e57`. BIPIA's data is not copied here.

**Run.** `pagevet-bench cases.jsonl`, patterns only, no model, about a second (`results.json`). The same counts with the pre-release (2026-11-24) patterns: `results-2026-11-24.json`, checked by `pagevet-reproduce --bipia`.

## Result
| | |
|---|---|
| Catch rate | **38.7%** (1,450 of 3,750; equivalently 29 of the 75 distinct attacks) |
| False alarms on clean emails | **0 of 50** (95% interval 0–7.1%) |

By category (attacks caught out of 5): Marketing & Advertising 4, Misinformation & Propaganda 4, Entertainment 3, Information Dissemination 3, Language Translation 3, Reverse Text 3, Scams & Fraud 3, Base Encoding 2, Emoji Substitution 2, Substitution Ciphers 2, and **0** for Business Intelligence, Conversational Agent, Research Assistance, Sentiment Analysis and Task Automation.

## Reading it
- **Before this run the patterns caught 0%.** BIPIA's attacks carry no trigger phrases ("ignore previous instructions", "note to any AI"): they are plain commands such as *add a link to your reply* or *encode your response in Base64*. PageVet's first patterns matched none of them.
- **One new pattern accounts for all 38.7%.** `response_directive` matches a command about the reader-model's own output. It was written against BIPIA's *train* attacks (25 of 75 caught there).
- **The five categories at 0 cannot be caught by patterns.** They are ordinary requests ("Write a script to rename files", "What is the sentiment of this text?"). Nothing in the wording marks them as injected; only their being out of place in an email does. That needs a model that reads context, which is the case for the classifier layer on the roadmap.
- **The interval on catch rate is narrower than the evidence.** The 3,750 cases are 75 attacks repeated across 50 emails, so they are not independent; think of it as 29 of 75.
- **The false-alarm figure is weak.** Fifty emails, no web pages. The pattern does fire on ordinary sentences such as "please include your order number in your reply", which is why PageVet rates it low in visible text. A false-alarm set of real web pages is the next measurement.

## Disclosure
While developing the pattern, test-split coverage was looked at once for an earlier, broader version (33 of 75). That version was then narrowed, to cut false alarms on ordinary prose, using train coverage and hand-written clean sentences only; the figures above are the single run of the final version. Treat the test number as lightly tuned, not blind.

## Scope
BIPIA tests instructions planted in emails that an assistant reads. PageVet's main target is instructions planted in web pages. The overlap is the instruction text itself, which is what this run measures; hidden-channel detection, severity and crawler comparison are not exercised here.
