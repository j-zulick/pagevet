# Security policy

## Reporting a vulnerability
Please report security problems in PageVet itself privately, through GitHub's **Report a vulnerability** button on the [Security tab](https://github.com/j-zulick/pagevet/security/advisories/new). Don't open a public issue for them. You'll get an acknowledgement within a few days, and a fix or a plan within two weeks for anything confirmed.

In scope: anything that lets a scanned page, sitemap, stylesheet, PDF or MCP request make PageVet do something it shouldn't, for example reaching private network addresses through `fetch(..., allow_private=False)` or the MCP tool, reading local files through a sitemap or URL list, running code, exhausting memory or CPU past the documented caps, or leaking a configured token.

## Not a vulnerability
- **A prompt injection PageVet misses, or a false alarm.** Detection is pattern matching and its limits are documented in the README and [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md). Please report these with the **Missed injection or false alarm** issue form, so they become test cases.
- The CLI fetching private addresses: the operator chooses the URL there, by design. The library and the MCP tool refuse them.

## Supported versions
Only the latest release gets fixes.
