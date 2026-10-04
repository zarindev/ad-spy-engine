from app.scraper.landing import is_capturable, url_key


def test_url_key_strips_tracking():
    a = url_key("https://www.Huel.com/products/black/?utm_source=fb&utm_campaign=x&fbclid=abc&variant=2")
    b = url_key("http://huel.com/products/black?variant=2")
    assert a == b == "https://huel.com/products/black?variant=2"


def test_capturable():
    assert is_capturable("https://brand.com/shop")
    assert not is_capturable("https://facebook.com/marketplace/item/1")
    assert not is_capturable("https://m.me/brand")
    assert not is_capturable("https://apps.apple.com/app/id1")
    assert not is_capturable(None)
    assert not is_capturable("mailto:hi@x.com")
