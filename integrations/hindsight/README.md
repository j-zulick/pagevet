# PageVet observations in Hindsight

[Hindsight](https://hindsight.vectorize.io/) is agent memory: it retains facts, recalls them, and reflects on them. Supabase holds the numbers; Hindsight holds what an agent should remember about a site.

```bash
pip install hindsight-client
python integrations/hindsight/remember.py --scores scores.json --traffic traffic.json --date 2026-11-15 --dry-run   # see the observations
HINDSIGHT_URL=http://localhost:8888 python integrations/hindsight/remember.py --scores scores.json --traffic traffic.json --bank my-site
HINDSIGHT_URL=http://localhost:8888 python integrations/hindsight/remember.py --bank my-site --ask "Why did AI-crawler hits change on /pricing?"
```

Observations come from fixed templates over the reports (scores, gaps, hits per crawler, hits before and after each content update), so they say only what PageVet measured; changes around an update are labelled a signal, not proof. `HINDSIGHT_API_KEY` is needed only for Hindsight Cloud. Reflection uses the model your Hindsight server is configured with.
