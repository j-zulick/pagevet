"""Hiding-method test: does PageVet see text that a page hides from people, and rate it as concealed?

    uv run python docs/bench/scripts/hiding_run.py docs/bench/2026-11-19-hiding/results-<date>.json

Each of the evasion test's seed instructions (both the development and the held-out set, three
invented brands each) is placed in a small page with one hiding method: inline CSS, a page
stylesheet, a markup element a browser does not render, or an attribute. For every method the run
counts pages where PageVet reports a finding, and pages where that finding is rated high, which is
PageVet's rating for concealed text. A finding rated medium means PageVet treated hidden text as
visible.

Every method here is a standard technique documented in web accessibility and SEO-spam guidance;
nothing here is shipped in the package or aimed at another product.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evasion_run import BRANDS, HELD_OUT, SEEDS  # noqa: E402

from pagevet import __version__  # noqa: E402
from pagevet.scan import scan_text  # noqa: E402

PAGE = "<html><body><h1>Spring catalogue</h1><p>Our new range is in store now.</p>{x}<p>Visit us soon.</p></body></html>"
STYLE = "<style>.promo-note{{{{{css}}}}}</style>"  # braces stay doubled for the second format()

METHODS = {
    # Inline CSS PageVet already treated as hidden before this test (controls).
    "display:none (control)": '<div style="display:none">{t}</div>',
    "visibility:hidden (control)": '<div style="visibility:hidden">{t}</div>',
    "off-screen left (control)": '<div style="position:absolute;left:-9999px">{t}</div>',
    # Inline CSS.
    "color:transparent": '<p style="color:transparent">{t}</p>',
    "transform:scale(0)": '<div style="transform:scale(0)">{t}</div>',
    "clip-path:inset(100%)": '<div style="position:absolute;clip-path:inset(100%)">{t}</div>',
    "clip-path:circle(0)": '<div style="clip-path:circle(0)">{t}</div>',
    "max-height:0 + overflow:hidden": '<div style="max-height:0;overflow:hidden">{t}</div>',
    "width:0 + overflow:hidden": '<div style="width:0;overflow:hidden">{t}</div>',
    "font-size:1px": '<span style="font-size:1px">{t}</span>',
    "font-size:0.1em": '<span style="font-size:0.1em">{t}</span>',
    "opacity:0.01": '<div style="opacity:0.01">{t}</div>',
    "off-screen right": '<div style="position:absolute;right:-9999px">{t}</div>',
    "off-screen top (em)": '<div style="position:absolute;top:-500em">{t}</div>',
    # Page stylesheet with the same declarations.
    "stylesheet color:transparent": STYLE.format(css="color:transparent") + '<p class="promo-note">{t}</p>',
    "stylesheet transform:scale(0)": STYLE.format(css="transform:scale(0)") + '<div class="promo-note">{t}</div>',
    # Markup a browser does not render.
    "<template>": "<template><p>{t}</p></template>",
    "<input type=hidden value>": '<form><input type="hidden" name="note" value="{t}"></form>',
    "SVG <desc>": '<svg width="10" height="10"><desc>{t}</desc><rect width="10" height="10"/></svg>',
    "SVG <title>": '<svg width="10" height="10"><title>{t}</title><rect width="10" height="10"/></svg>',
    "<textarea hidden>": "<textarea hidden>{t}</textarea>",
}


def run() -> dict:
    out: dict = {"version": __version__, "methods": {}}
    for name, wrap in METHODS.items():
        row = {}
        for label, seeds in (("dev", SEEDS), ("held_out", HELD_OUT)):
            found = high = 0
            for seed in seeds.values():
                for b in BRANDS:
                    text = seed.format(b=b, u=f"https://{b.lower()}.example/guide")
                    page = PAGE.format(x=wrap.format(t=text.replace('"', "&quot;")))
                    findings = scan_text("page.html", page).findings
                    found += bool(findings)
                    high += any(f.severity == "high" for f in findings)
            row[label] = {"found": found, "high": high, "of": len(seeds) * len(BRANDS)}
        out["methods"][name] = row
    return out


if __name__ == "__main__":
    result = run()
    Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[1]).write_text(json.dumps(result, indent=1) + "\n")
    for name, row in result["methods"].items():
        d, h = row["dev"], row["held_out"]
        sys.stdout.write(f"{name:34} dev found {d['found']:2}/{d['of']} high {d['high']:2}   "
                         f"held-out found {h['found']:2}/{h['of']} high {h['high']:2}\n")
