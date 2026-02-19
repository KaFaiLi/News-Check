"""Unit tests for URL normalization utilities."""

from src.url_utils import normalize_url


def test_normalize_url_strips_tracking_params():
    url = "https://example.com/article?utm_source=google&gclid=123&ref=foo&id=1"
    normalized = normalize_url(url)
    assert normalized == "https://example.com/article?id=1"


def test_normalize_url_unwraps_google_redirect():
    url = "https://www.google.com/url?q=https%3A%2F%2Fexample.com%2Fstory%3Fa%3D1&sa=U"
    normalized = normalize_url(url)
    assert normalized == "https://example.com/story?a=1"
