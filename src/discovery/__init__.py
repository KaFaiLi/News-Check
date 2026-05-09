"""News discovery: Google News query → candidate Article URLs."""

from src.discovery.google_news import GoogleNewsDiscoverer
from src.discovery.publishers import classify_tier

__all__ = ["GoogleNewsDiscoverer", "classify_tier"]
