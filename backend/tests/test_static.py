"""Serwowanie frontu + wstrzykiwanie <base href> z X-Ingress-Path."""

from app.static import _base_href, _inject_base


class _Req:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def test_base_href_bez_ingress() -> None:
    assert _base_href(_Req({})) == "/"


def test_base_href_z_ingress_dokleja_slash() -> None:
    assert _base_href(_Req({"X-Ingress-Path": "/api/hassio_ingress/TOKEN"})) == "/api/hassio_ingress/TOKEN/"


def test_base_href_nie_dubluje_slasha() -> None:
    assert _base_href(_Req({"X-Ingress-Path": "/api/hassio_ingress/TOKEN/"})) == "/api/hassio_ingress/TOKEN/"


def test_inject_base_wstawia_po_head() -> None:
    out = _inject_base("<html><head><meta/></head><body/></html>", "/p/")
    assert out == '<html><head><base href="/p/"><meta/></head><body/></html>'


def test_inject_base_bez_head_nie_rusza() -> None:
    src = "<html><body>nope</body></html>"
    assert _inject_base(src, "/p/") == src


def test_inject_base_escape() -> None:
    out = _inject_base("<head></head>", '/a"b/')
    assert '<base href="/a&quot;b/">' in out
