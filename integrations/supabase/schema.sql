-- PageVet tables for Supabase (Postgres). Run once in the SQL editor or with `supabase db push`.
-- Every table has row level security on and no policies, so only the service role (server-side) can read or
-- write; add read policies or views for dashboards as you need them. No client IP addresses are stored.

create table if not exists pagevet_bots (
  token       text primary key,          -- robots.txt token, e.g. GPTBot, Googlebot
  operator    text not null,
  bot_group   text not null,             -- training | search | fetch | search engine | ...
  kind        text not null,             -- ai | listed
  user_agent  text not null default ''
);

create table if not exists pagevet_bot_hits (
  period_start date not null,
  period_end   date not null,
  url          text not null,            -- path or URL as the traffic report gives it (query strings dropped)
  bot          text not null references pagevet_bots (token),
  hits         integer not null check (hits >= 0),
  first_seen   date,
  last_seen    date,
  primary key (period_start, period_end, url, bot)
);

create table if not exists pagevet_findings (
  id          text primary key,          -- sha256 of url, channel, kinds and excerpt: re-loading the same report is idempotent
  url         text not null,
  scanned_at  timestamptz,
  channel     text not null,
  kinds       text[] not null,
  severity    text not null check (severity in ('low', 'medium', 'high')),
  intent      text not null default '',
  excerpt     text not null,
  owasp       text[] not null default '{}',
  atlas       text[] not null default '{}'
);

create table if not exists pagevet_crawler_access (
  url         text not null,
  token       text not null,
  checked_on  date not null,
  bot_group   text not null,
  verdict     text not null,             -- allowed | refused by robots.txt | refused by server | allowed (unverified)
  robots      text not null,
  probe       text not null,
  status      integer,
  primary key (url, token, checked_on)
);

create table if not exists pagevet_scores (
  site          text not null,
  scored_on     date not null,
  score_version text not null,
  visibility    integer,
  risk_max      integer not null,
  opportunity   integer,
  gaps          jsonb not null default '[]',
  primary key (site, scored_on, score_version)
);

alter table pagevet_bots enable row level security;
alter table pagevet_bot_hits enable row level security;
alter table pagevet_findings enable row level security;
alter table pagevet_crawler_access enable row level security;
alter table pagevet_scores enable row level security;

create index if not exists pagevet_bot_hits_bot on pagevet_bot_hits (bot, period_end);
create index if not exists pagevet_findings_url on pagevet_findings (url);

-- Hits per bot group and period, for dashboards (Tableau, Amazon Quick, Metabase read views like any table).
create or replace view pagevet_hits_by_group with (security_invoker = true) as
select h.period_start, h.period_end, b.bot_group, b.kind, b.token, sum(h.hits) as hits, count(distinct h.url) as pages
from pagevet_bot_hits h join pagevet_bots b on b.token = h.bot
group by 1, 2, 3, 4, 5;

-- The newest score per site.
create or replace view pagevet_latest_scores with (security_invoker = true) as
select distinct on (site) site, scored_on, score_version, visibility, risk_max, opportunity, gaps
from pagevet_scores
order by site, scored_on desc;
