"""The stylesheet parser and fetch deadline: robustness against hostile or malformed input."""

import http.server
import threading
import time

import pytest

from pagevet.scan import css_rules, fetch, hiding_selectors


def test_rules_and_nested_at_blocks():
    css = """/* c */ .a{display:none} @media (min-width:1px){ .b{display:none} @supports (x){ .c{display:none} } }
    @container (min-width: 1px) { .cq{display:none} }
    @keyframes k { 0% { opacity:0 } 100% { opacity:1 } } .d { color: red } @import url(x.css); .e{visibility:hidden}"""
    assert [sel for sel, _ in css_rules(css)] == [".a", ".d", ".e"]
    assert [sel[-1][1].classes for sel in hiding_selectors(css)] == [{"a"}, {"e"}]


def test_layer_and_supports_blocks_are_read():
    css = "@layer base { .sr-only{clip:rect(0 0 0 0)} @media print { .p{display:none} } } @supports (display:grid) { .g{display:none} }"
    assert [sel for sel, _ in css_rules(css)] == [".sr-only", ".g"]


def test_unbalanced_braces_do_not_derail_later_rules():
    assert [s for s, _ in css_rules("} } .x{display:none} @media{ .y{ } .z{display:none")] == [".x"]
    assert [s for s, _ in css_rules(".p{a:b}} .q{display:none}")] == [".p", ".q"]


def test_pathological_stylesheet_parses_quickly():
    # Long brace-free runs between unbalanced braces made the earlier regex version quadratic.
    css = ("@keyframes k { 0% { opacity:0 } " + "a" * 2000 + " { " + "b" * 2000 + " ") * 100
    start = time.monotonic()
    css_rules(css)
    hiding_selectors(css + " .h{display:none}")
    assert time.monotonic() - start < 2.0


class _Drip(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/css")
        self.end_headers()
        try:
            for _ in range(100):
                self.wfile.write(b"a")
                self.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass

    def log_message(self, *args):
        pass


def test_fetch_gives_up_on_a_slow_drip_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Drip)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            fetch(f"http://127.0.0.1:{server.server_port}/s.css", timeout=0.3)
        assert time.monotonic() - start < 3
    finally:
        server.shutdown()


def test_deeply_nested_blocks_do_not_recurse_without_limit():
    css = "@supports (a) { " * 5000 + ".x{display:none}" + " }" * 5000 + " .y{display:none}"
    assert [sel for sel, _ in css_rules(css)] == [".y"]


def test_braces_inside_strings_are_ignored():
    css = '.icon:before{content:"{"} .q:after{content:"\\"}"} .w{content:\'}\'} .sr-only{clip:rect(0 0 0 0)}'
    assert [sel for sel, _ in css_rules(css)] == [".icon:before", ".q:after", ".w", ".sr-only"]


def test_escaped_quotes_and_braces_in_selectors():
    css = r".\[font\:\'A\'\]{font-family:A} .\{x\}{color:red} .h{display:none}"
    assert [sel for sel, _ in css_rules(css)] == [r".\[font\:\'A\'\]", r".\{x\}", ".h"]


# 0.24.0: complex selectors.
def _hidden(page: str) -> list[str]:
    from pagevet.scan import split_html
    return split_html(page).hidden_by_css


@pytest.mark.parametrize("css,body,hidden", [
    (".promo .note{display:none}", '<div class="promo"><p class="note">X</p></div><p class="note">Y</p>', ["X"]),
    (".promo > p{display:none}", '<div class="promo"><p>X</p><div><p>Y</p></div></div>', ["X"]),
    ('[data-role="ai"]{display:none}', '<p data-role="ai">X</p><p data-role="user">Y</p>', ["X"]),
    ('div[class^="sr-"]{position:absolute;left:-9999px}', '<div class="sr-only">X</div><div class="srx">Y</div>', ["X"]),
    ("article p.n{visibility:hidden}", "<article><section><p class=n>X</p></section></article><p class=n>Y</p>", ["X"]),
    ("main *{display:none}", "<main><span>X</span></main><span>Y</span>", ["X"]),
])
def test_complex_selectors(css, body, hidden):
    assert _hidden(f"<html><head><style>{css}</style></head><body>{body}</body></html>") == hidden


@pytest.mark.parametrize("sel", ["a:hover", "p::before", "h1 + p", "h1 ~ p", "[title='a b']", "a > > b", "> a"])
def test_unreadable_selectors_are_skipped(sel):
    from pagevet.scan import parse_selector
    assert parse_selector(sel) is None


def test_body_level_hiding_is_ignored():
    assert hiding_selectors(".js body{display:none} html.loading{visibility:hidden}") == []
