from __future__ import annotations

from app.scraper.ad_library import ScanParams, build_search_url


def test_keyword_url():
    url = build_search_url(ScanParams(query="Brew Lab", country="gb", media_type="video"))
    assert url.startswith("https://www.facebook.com/ads/library/?")
    assert "q=Brew+Lab" in url
    assert "country=GB" in url
    assert "media_type=video" in url
    assert "search_type=keyword_unordered" in url


def test_page_id_url_with_platforms():
    url = build_search_url(
        ScanParams(
            query="129669023798560", search_type="page_id", platforms=["Instagram", "facebook", "bogus"]
        )
    )
    assert "view_all_page_id=129669023798560" in url
    assert "search_type=page" in url
    assert url.endswith("publisher_platforms[0]=instagram&publisher_platforms[1]=facebook")


def test_carousel_filter_falls_back_to_all():
    url = build_search_url(ScanParams(query="x", media_type="carousel"))
    assert "media_type=all" in url
