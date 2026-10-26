from pathlib import Path
from urllib.parse import urlparse

from app.notifications import _build_xml, _toast_logo


def test_build_xml_without_logo():
    xml = _build_xml(None, "已最小化到托盘")
    assert "<image" not in xml
    assert "<text>已最小化到托盘</text>" in xml


def test_build_xml_with_logo():
    xml = _build_xml("标题", "正文", "file:///C:/temp/logo.png")
    assert 'placement="appLogoOverride"' in xml
    assert 'src="file:///C:/temp/logo.png"' in xml
    assert "<text>标题</text>" in xml


def test_toast_logo_missing_or_unsupported(tmp_path: Path):
    assert _toast_logo(None) == ""
    assert _toast_logo(tmp_path / "missing.png") == ""

    ico = tmp_path / "图标.ico"
    ico.write_bytes(b"ico")
    assert _toast_logo(ico) == ""


def test_toast_logo_copies_to_ascii_path(tmp_path: Path):
    # 中文路径在 Toast 的 <image src> 中无法加载，必须复制到纯 ASCII 路径。
    source = tmp_path / "图标.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)

    url = _toast_logo(source)
    assert url.startswith("file:///")

    target = Path(urlparse(url).path.lstrip("/"))
    assert str(target).isascii()
    assert target.exists()
    assert target.read_bytes() == source.read_bytes()
