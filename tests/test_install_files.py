from pathlib import Path


def test_windows_install_scripts_exist():
    root = Path(__file__).resolve().parent.parent
    for name in (
        "install.ps1",
        "uninstall.ps1",
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
        assert (root / name).exists(), name


def test_installer_is_signal_only():
    iss = (Path(__file__).resolve().parent.parent / "installer" / "NiftyAnalyzer.iss").read_text(encoding="utf-8")
    assert "SIGNAL-ONLY" in iss
    assert "SetupIconFile" in iss
    assert "LicenseFile" in iss
    assert "NiftyAnalyzer-Setup-2.0.0" in iss
