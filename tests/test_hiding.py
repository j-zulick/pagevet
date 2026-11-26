"""Offline tests for hiding methods, and the visible look-alikes that must not count."""

import pytest

from pagevet.scan import hides, split_html

HIDDEN = [
    "color:transparent", "color: transparent;", "transform:scale(0)", "transform: scale(0, 0)",
    "position:absolute;clip-path:inset(100%)", "clip-path: inset(50%)", "clip-path:circle(0)",
    "max-height:0;overflow:hidden", "width:0;overflow:hidden", "overflow:hidden;height:0",
    "font-size:1px", "font-size:0.5px", "font-size:0.1em", "font-size:.2rem", "opacity:0.01", "opacity:.05",
    "position:absolute;right:-9999px", "top:-500em", "text-indent:-99em",
]
VISIBLE = [
    "background-clip:text;-webkit-background-clip:text;color:transparent",  # gradient text
    "min-width:0;overflow:hidden", "min-height:0;overflow:hidden", "line-height:0;overflow:hidden",
    "border-color:transparent", "background-color:transparent", "outline-color: transparent",
    "transform:scale(0.5)", "transform:scale(1)", "clip-path:inset(10%)", "clip-path:circle(50%)",
    "font-size:10px", "font-size:12px", "font-size:0.9em", "font-size:0.875rem", "opacity:0.5", "opacity:0.1",
    "left:-10px", "margin-left:-9999px", "top:-2em", "width:0.5rem;overflow:hidden",
]


@pytest.mark.parametrize("style", HIDDEN)
def test_hiding_styles(style):
    assert hides(style)


@pytest.mark.parametrize("style", VISIBLE)
def test_visible_look_alikes(style):
    assert not hides(style)


def test_template_text_is_hidden():
    ch = split_html("<p>Hi</p><template><div>tucked away</div></template>")
    assert ch.hidden == ["tucked away"] and ch.visible == ["Hi"]


def test_script_inside_template_is_still_skipped():
    ch = split_html("<template><script>var x = 'code';</script><style>.a{}</style></template>")
    assert ch.hidden == [] and ch.visible == []


def test_hidden_input_value_is_an_attribute():
    ch = split_html('<form><input type="hidden" name="n" value="tucked away"><input type="text" value="shown"></form>')
    assert ch.attributes == ["input[type=hidden][value]: tucked away"]


def test_svg_title_and_desc_are_hidden_but_html_title_is_not_affected():
    ch = split_html("<svg><title>tip</title><desc>never drawn</desc><text>drawn</text></svg><h1>Page</h1>")
    assert ch.hidden == ["tip", "never drawn"]
    assert ch.visible == ["drawn", "Page"]


def test_stylesheet_transparent_with_text_clip_is_visible():
    ch = split_html("<style>.g{background-clip:text;color:transparent}</style><h1 class='g'>Gradient</h1>")
    assert ch.visible == ["Gradient"]
