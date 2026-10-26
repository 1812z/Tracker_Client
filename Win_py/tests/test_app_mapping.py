import json

import pytest

from app.app_mapping import AppMapping


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_user_file_is_seeded_from_bundled_template(tmp_path):
    bundled = tmp_path / "bundled.json"
    user = tmp_path / "apps.json"
    _write(bundled, {"Foo.exe": "Foo"})

    mapping = AppMapping(user, bundled).load()

    assert user.exists()
    assert mapping.lookup("foo.EXE") == "Foo"


def test_add_update_remove_persist(tmp_path):
    bundled = tmp_path / "bundled.json"
    user = tmp_path / "apps.json"
    _write(bundled, {"Foo.exe": "Foo"})

    mapping = AppMapping(user, bundled).load()
    assert mapping.add("Bar.exe", "Bar")
    assert mapping.lookup("bar.exe") == "Bar"
    assert mapping.update("Bar.exe", "Baz.exe", "Baz")
    assert not mapping.has_key("bar.exe")
    assert AppMapping(user, bundled).load().lookup("baz.exe") == "Baz"
    assert mapping.remove("Baz.exe")
    assert mapping.lookup("Baz.exe") == "Baz.exe"


def test_broken_user_file_falls_back_to_bundle(tmp_path):
    bundled = tmp_path / "bundled.json"
    user = tmp_path / "apps.json"
    _write(bundled, {"Foo.exe": "Foo"})
    user.write_text("{bad", encoding="utf-8")

    mapping = AppMapping(user, bundled).load()

    assert mapping.lookup("Foo.exe") == "Foo"
    assert (tmp_path / "apps.json.bad").exists()


def test_empty_values_are_rejected(tmp_path):
    bundled = tmp_path / "bundled.json"
    _write(bundled, {})
    mapping = AppMapping(tmp_path / "apps.json", bundled).load()

    with pytest.raises(ValueError):
        mapping.add("", "Name")
    with pytest.raises(ValueError):
        mapping.add("app.exe", " ")
