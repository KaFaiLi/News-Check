from __future__ import annotations

from src.extraction.markdown import (
    cache_path,
    html_to_markdown,
    read_cache,
    url_hash,
    write_cache,
)


def test_html_to_markdown_extracts_main_content():
    html = """
    <html><body>
      <header>Site nav and ads</header>
      <article>
        <h1>The Big AI Story</h1>
        <p>OpenAI announced something material today that affects banks.</p>
        <p>Analysts say the deal will reshape competitive dynamics.</p>
      </article>
      <footer>Cookie banner stuff</footer>
    </body></html>
    """
    md = html_to_markdown(html)
    assert "Big AI Story" in md or "OpenAI announced" in md
    assert "Cookie banner stuff" not in md


def test_html_to_markdown_truncates_at_max_chars():
    body = "<article><p>" + ("hello world. " * 20_000) + "</p></article>"
    md = html_to_markdown(body, max_chars=500)
    assert len(md) <= 600
    assert "truncated" in md.lower()


def test_empty_html_returns_empty():
    assert html_to_markdown("") == ""
    assert html_to_markdown("   ") == ""


def test_url_hash_deterministic_and_compact():
    a = url_hash("http://example.com/abc")
    b = url_hash("http://example.com/abc")
    c = url_hash("http://example.com/different")
    assert a == b
    assert a != c
    assert len(a) == 16


def test_cache_round_trip(tmp_path):
    url = "http://example.com/article"
    p = cache_path(tmp_path, url)
    assert p.parent == tmp_path
    assert read_cache(tmp_path, url) is None

    write_cache(tmp_path, url, "# hello\n\nbody")
    again = read_cache(tmp_path, url)
    assert again == "# hello\n\nbody"
