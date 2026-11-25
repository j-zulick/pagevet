# Threat model

## What is being protected
AI systems that read web pages (AI search, assistants with browsing, research agents) and the people who rely on their answers. PageVet is used by whoever is responsible for a page: it tells them what on the page is addressed to those systems.

## Attacker
Someone who can put text on a page the AI will read: the site owner (self-promotion), a plugin or theme, a user-generated comment or review, or an attacker who has compromised the site. They cannot change the AI system itself.

## Goals observed in the wild
Promotion of a product or site over competitors, steering citations to a URL, suppressing negative information, changing an assistant's behaviour, and in agent settings, data exfiltration or harmful actions.

## What PageVet covers
| Technique | Covered | How |
|---|---|---|
| Explicit instructions ("ignore previous…", "note to any AI…", role changes, "you must recommend…") | Yes | patterns in twelve languages: EN/ES/FR/DE/PT/IT/NL/PL/SV/RU/JA/ZH |
| Hidden with CSS, `hidden`, `aria-hidden`, off-screen, zero size | Yes | hidden-element channel (inline styles) |
| HTML comments, attributes, meta tags, JSON-LD, noscript | Yes | separate channels |
| Invisible Unicode tag characters, base64 | Yes | decoded, then scanned |
| Chat-template markup | Yes | pattern |
| A page that is mostly one repeated claim | Yes | repetition rule |
| Content served only to AI crawlers, by user agent | Yes | `--compare-agents` |
| Paraphrased instructions with no trigger phrases | **No** | needs a trained classifier (roadmap) |
| Instructions split into short fragments | Yes (internal 0.11.0) | fragments of four words or fewer are joined |
| Instructions split into full sentences | Partly (internal 0.24.0) | a sentence ending on a word no sentence ends on ("and", "the", "your" and their equivalents) is joined to the next; other splits are missed (docs/EVASION.md) |
| Look-alike letters, invisible characters, ROT13, reversed text | Yes (internal 0.4.0) | undone before matching; rated high |
| Letter spacing ("i g n o r e") | Partly (internal 0.4.0) | caught when spaced words stay apart; missed when they run together |
| Text split across inline elements | Yes (internal 0.4.0) | inline runs joined |
| Languages other than the twelve above; other encodings | **No** | Polish, Swedish, Russian, Japanese and Chinese added in internal 0.24.0 |
| Text hidden by the page's own `<style>` rules | Yes (internal 0.5.0; descendant, child and attribute selectors since internal 0.24.0) | pseudo-classes and sibling combinators are not read |
| Transparent, scaled-to-zero, clipped, near-zero font or opacity, off-screen right/bottom; `<template>`, SVG `<title>`/`<desc>`, hidden-input values | Yes (internal 0.8.0) | `docs/bench/2026-11-19-hiding/` |
| Text hidden by a linked stylesheet on the same host | Yes, with `--fetch-css` (internal 0.9.0) | stylesheets on other hosts are not read |
| Text hidden by stylesheets on other hosts (CDNs) | Yes, with `--fetch-css --css-any-host` (internal 0.18.0) | |
| Text hidden by media queries, pseudo-classes, sibling selectors or JavaScript | **No** | text added by JavaScript is seen through a rendering source (`--via firecrawl`, `--crawl`); visibility is still judged from markup and stylesheets, not computed styles |
| Stylesheets built to stall the scanner | Handled (internal 0.18.0) | linear parser, bounded nesting, whole-fetch time limit |
| Cloaking by IP address or request fingerprint | **No** | |
| Instructions in PDF text, metadata and annotations | Yes (internal 0.17.0) | text drawn invisibly on the page is rated as visible |
| Instructions in images and audio | **No** | |
| A site refusing AI crawlers by firewall while robots.txt allows them | Reported (internal 0.24.0) | `pagevet-access` probes each crawler's user agent; IP-based checks are not imitated |

## Known false alarms
Pages that discuss or quote prompt injection match the patterns; they are rated low when the text names the topic. Listing pages with a repeated boilerplate sentence can trip the repetition rule.

## An adversary who knows PageVet
The patterns are public, so a determined attacker can avoid them by rewording. PageVet raises the cost of the cheap, common forms and gives site owners evidence; it is not a guarantee. This is why detection rates will be published with evasion tests, not as a single headline number.

## Severity rationale
Severity follows concealment: an instruction the reader cannot see is rated high, because hiding it from people while showing it to machines is the mark of intent. This mirrors how indirect-injection research scores a successful attack: the influence is both effective and concealed from the user.

## The tool's own attack surface
- **SSRF:** `fetch(allow_private=False)` refuses non-public addresses on every redirect. The CLI allows private addresses because the operator chooses the URL.
- **Sitemaps:** parsed with `defusedxml`, DTDs refused, 5 MB cap, page locations must be http(s).
- **Reports:** HTML output escapes all page-derived text and contains no scripts; CSV cells that look like formulas are neutralised.
- **Hostile HTML:** a property-based test feeds arbitrary text through every channel and renderer.
