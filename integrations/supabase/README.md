# PageVet reports in Supabase

1. Run [`schema.sql`](schema.sql) once (SQL editor or `supabase db push`). Every table has row level security on and no policies, so only the service role can read or write; add views or read policies for dashboards.
2. Write the reports: `pagevet --format json`, `pagevet-access --format json`, `python -m pagevet.traffic`, `python -m pagevet.scores`.
3. Load them, from a server-side job (Windmill, n8n, cron) with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` set:
   ```bash
   python integrations/supabase/load.py --traffic traffic.json --scan scan.json --access access.json --scores scores.json --dry-run
   python integrations/supabase/load.py --traffic traffic.json --scan scan.json --access access.json --scores scores.json
   ```
   Rows are upserts on each table's primary key, so a re-run changes nothing. Finding ids are a SHA-256 of URL, channel, kinds and excerpt.

The views `pagevet_hits_by_group` and `pagevet_latest_scores` are ready for Tableau, Amazon Quick or Metabase, which read Postgres views like tables. Raw logs stay in your log store; this holds the per-period totals the traffic report gives. No client addresses are stored.
