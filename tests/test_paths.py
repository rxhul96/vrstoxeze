from pathlib import Path

from backend.paths import APP_NAME, env_files, frontend_dir, install_root, user_data_dir


def test_frontend_ships_index():
    assert (frontend_dir() / "index.html").exists()


def test_user_data_dir_created():
    d = user_data_dir()
    assert d.is_dir()
    assert APP_NAME in str(d)


def test_install_root_is_repo():
    assert (install_root() / "desktop.py").exists()


def test_env_files_are_existing_paths():
    for p in env_files():
        assert Path(p).exists()


def test_default_settings_sqlite_under_data_dir(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from backend import config
    config.get_settings.cache_clear()
    s = config.get_settings()
    assert "nifty_desk.sqlite" in s.database_url
    config.get_settings.cache_clear()
