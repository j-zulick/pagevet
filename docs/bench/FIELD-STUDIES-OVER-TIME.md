# Field studies over time (first runs and the 2026-11-25 repeats)

Each row is one study; details and limits are in its folder.

| Study | Date | Scanned | Read | Pages with text aimed at AI (high / medium / low) | Refuse ≥1 AI crawler | Refuse all three | Different content |
|---|---|---:|---:|---|---|---:|---:|
| [front brake rotor shopping pages](2026-11-19-field-brake-rotors/) | 2026-11-19 | 102 | 67 | 0 / 0 / 0 | 27 of 67 (40%) | 22 | 2 |
| [front brake rotor shopping pages](2026-11-25-repeat-brake-rotors/) | 2026-11-25 | 102 | 66 | 1 / 0 / 0 | 27 of 66 (41%) | 20 | 7 |
| [small-business CRM software pages](2026-11-23-field-crm/) | 2026-11-23 | 48 | 42 | 0 / 0 / 0 | 18 of 42 (43%) | 16 | 3 |
| [small-business CRM software pages](2026-11-25-repeat-crm/) | 2026-11-25 | 48 | 39 | 0 / 0 / 0 | 10 of 39 (26%) | 2 | 9 |
| [home solar panel pages](2026-11-23-field-home-solar/) | 2026-11-23 | 43 | 32 | 0 / 0 / 0 | 13 of 32 (41%) | 8 | 3 |
| [home solar panel pages](2026-11-25-repeat-home-solar/) | 2026-11-25 | 43 | 31 | 0 / 0 / 0 | 12 of 31 (39%) | 6 | 3 |
| [running shoe shopping pages](2026-11-23-field-running-shoes/) | 2026-11-23 | 96 | 72 | 0 / 0 / 0 | 25 of 72 (35%) | 22 | 3 |
| [running shoe shopping pages](2026-11-25-repeat-running-shoes/) | 2026-11-25 | 96 | 70 | 0 / 0 / 0 | 22 of 70 (31%) | 11 | 6 |

## What changed, and how far to trust it
- **Same URLs, same method:** each repeat used its study's committed `search-results.json`, PageVet pre-release (2026-11-25), a browser and three AI crawler user agents, linked stylesheets read, robots.txt respected (`pagevet-study run … --from-json`).
- **Different network:** the first runs were fetched from a home connection, the repeats from a cloud host. Bot-management rules decide on the network as well as the user agent, so a change in refusals can come from either. Example: on the CRM list, Capterra's pages refused all three AI crawlers on 2026-11-23 and none on 2026-11-25; Salesforce now serves ClaudeBot. Treat refusal changes as indicative, not as policy changes.
- **One high finding is a false alarm:** on a brake-rotor listing page, a customer review inside the page's structured data ("…this is your answer") matched the reply-command rule, and structured data is rated as hidden text. The rule was not changed from this page. A review is text a visitor wrote, so this is a known limit: reviews in JSON-LD are not yet treated as user-submitted content.
- **Still no hidden instructions** aimed at AI on any page read in the four repeats (206 pages read).
