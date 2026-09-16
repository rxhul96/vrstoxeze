from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_windows_install_scripts_exist():
    for name in (
        "install.ps1",
        "uninstall.ps1",
        "INSTALL.bat",
        "Launch-NiftyAnalyzer.vbs",
        "Create-DesktopShortcut.ps1",
        "run.ps1",
        "build_exe.ps1",
        "build_installer.ps1",
        "build_windows.ps1",
        "Nifty Analyzer.bat",
        "Build-Setup.bat",
        "NiftyAnalyzer.spec",
        "WINDOWS_SETUP.md",
        "assets/.env.default",
        "assets/nifty.ico",
        "installer/NiftyAnalyzer.iss",
        "installer/LICENSE.txt",
        "installer/INFO.txt",
        "installer/file_version_info.txt",
    ):
        assert (ROOT / name).exists(), name


def test_installer_is_signal_only():
    iss = (ROOT / "installer" / "NiftyAnalyzer.iss").read_text(encoding="utf-8")
    assert "SIGNAL-ONLY" in iss
    assert "SetupIconFile" in iss
    assert "LicenseFile" in iss
    assert "NiftyAnalyzer-Setup-2.0.0" in iss


def test_inplace_install_creates_desktop_app_shortcut():
    install = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "$PSScriptRoot" in install
    assert "LOCALAPPDATA" not in install
    assert "Nifty Analyzer" in install
    assert "Launch-NiftyAnalyzer.vbs" in install
    assert "nifty.ico" in install
    assert "GetFolderPath(\"Desktop\")" in install
    assert "$NoDesktopShortcut" in install
    assert "inPlace" in install
    assert "signalOnly" in install

    launcher = (ROOT / "Launch-NiftyAnalyzer.vbs").read_text(encoding="utf-8")
    assert "pythonw.exe" in launcher
    assert "desktop.py" in launcher
    assert "install.ps1" in launcher
    assert "place_order" not in launcher.lower()

    bat = (ROOT / "INSTALL.bat").read_text(encoding="utf-8")
    assert "install.ps1" in bat
    assert "-Launch" in bat

    uninstall = (ROOT / "uninstall.ps1").read_text(encoding="utf-8")
    assert "Does not delete this source folder" in uninstall or "Kept this folder" in uninstall
    assert ".venv" in uninstall
