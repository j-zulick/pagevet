# Synthetic traffic samples

Made up by [`make_samples.py`](make_samples.py): example.com hosts, client addresses from the documentation ranges (RFC 5737), seeded random hit counts, 1 October to 15 November 2026, with more AI-crawler visits to `/pricing` after its update on 20 October. No real log is in this folder. Each file carries a client address on purpose; PageVet never reads it.

| File | Format |
|---|---|
| `hits.csv` | `date,url,user_agent,hits` (plus a client address column, ignored; URLs with a query string, dropped) |
| `bots.csv` | `date,url,bot,hits` |
| `access.log` | combined access-log format |
| `opensearch-search.json` | OpenSearch search-API response (`hits.hits[]._source`, default field names) |
| `opensearch.ndjson` | NDJSON with flat field names: `--ts-field timestamp --url-field request.path --ua-field agent` |
| `search-bots.csv` | an extra bots file for `--bots` (`token,operator,group,user_agent`): ten search-engine crawlers (Googlebot, Googlebot-Image, Storebot-Google, bingbot, Applebot, DuckDuckBot, YandexBot, YandexImages, Baiduspider, Sogou web spider), group `search engine` |
| `updates.csv` | `url,date` of content updates |

```bash
python -m pagevet.traffic examples/traffic/access.log --updates examples/traffic/updates.csv
python -m pagevet.traffic examples/traffic/access.log --bots examples/traffic/search-bots.csv   # search engines next to AI crawlers
pagevet-access https://shop.example.com/pricing --report visibility.html --traffic examples/traffic/opensearch-search.json --updates examples/traffic/updates.csv
```
