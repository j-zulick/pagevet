"""Build a fresh list of Spanish, French, German and Portuguese pages, for a false-alarm check of
the multilingual patterns.

    uv run python docs/bench/fresh_pages_intl.py urls.txt            # Spanish, French, German, Portuguese
    uv run python docs/bench/fresh_pages_intl.py urls.txt it-nl      # Italian and Dutch (0.19.0)

Random Wikipedia articles in each language plus the current entries of one major news feed per
language, taken from public, keyless sources so the list is not chosen by hand. Run it once and
keep the output.
"""
import json
import sys

import httpx
from defusedxml import ElementTree

UA = "pagevet (page audit for text aimed at AI models)"
client = httpx.Client(timeout=20, headers={"User-Agent": UA}, follow_redirects=True)


def wikipedia(lang: str, n: int = 25) -> list[str]:
    r = client.get(f"https://{lang}.wikipedia.org/w/api.php?action=query&list=random&rnnamespace=0&rnlimit={n}&format=json")
    r.raise_for_status()
    return [f"https://{lang}.wikipedia.org/wiki/" + p["title"].replace(" ", "_") for p in r.json()["query"]["random"]]


def rss(url: str, n: int = 20) -> list[str]:
    r = client.get(url)
    r.raise_for_status()
    root = ElementTree.fromstring(r.content)
    return [el.text.strip() for el in root.iter("link") if el.text and el.text.strip().startswith("http")][1:n + 1]


SOURCES_IT_NL = {
    "it.wikipedia": lambda: wikipedia("it", 30),
    "nl.wikipedia": lambda: wikipedia("nl", 30),
    "corriere (rss)": lambda: rss("https://xml2.corriereobjects.it/rss/homepage.xml"),
    "nos (rss)": lambda: rss("https://feeds.nos.nl/nosnieuwsalgemeen"),
}
SOURCES = {
    "es.wikipedia": lambda: wikipedia("es"),
    "fr.wikipedia": lambda: wikipedia("fr"),
    "de.wikipedia": lambda: wikipedia("de"),
    "pt.wikipedia": lambda: wikipedia("pt"),
    "el país (rss)": lambda: rss("https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
    "le monde (rss)": lambda: rss("https://www.lemonde.fr/rss/une.xml"),
    "tagesschau (rss)": lambda: rss("https://www.tagesschau.de/index~rss2.xml"),
    "folha (rss)": lambda: rss("https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"),
}

if __name__ == "__main__":
    urls: list[str] = []
    counts = {}
    chosen = SOURCES_IT_NL if sys.argv[2:3] == ["it-nl"] else SOURCES
    for name, fn in chosen.items():
        try:
            got = fn()
        except Exception as exc:  # one source failing must not lose the others
            sys.stderr.write(f"{name}: skipped: {type(exc).__name__}: {exc}\n")
            got = []
        counts[name] = len(got)
        urls.extend(got)
    urls = list(dict.fromkeys(urls))
    with open(sys.argv[1], "w") as fh:
        fh.write("\n".join(urls) + "\n")
    sys.stdout.write(json.dumps(counts, indent=1) + f"\n{len(urls)} URLs written to {sys.argv[1]}\n")
