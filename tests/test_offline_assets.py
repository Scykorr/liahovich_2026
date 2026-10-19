from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_graphics_are_vendored_locally() -> None:
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    settings = (ROOT / "config" / "settings" / "base.py").read_text(encoding="utf-8")
    assert "cdn.jsdelivr.net" not in base
    assert "cdn.jsdelivr.net" not in settings
    for name in ("bootstrap.min.css", "bootstrap.bundle.min.js", "htmx.min.js", "plotly.min.js"):
        path = ROOT / "static" / "vendor" / name
        assert path.is_file()
        assert path.stat().st_size > 1000
    assert "vendor/plotly.min.js" in base
    assert "vendor/bootstrap.min.css" in base
