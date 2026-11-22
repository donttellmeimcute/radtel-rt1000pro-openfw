from rt1000pro import cli
from rt1000pro.protocol import FlashResult


def test_airband_flash_requires_all_safety_confirmations(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_read_image", lambda path: b"image")
    monkeypatch.setattr(cli, "_preflight", lambda image: ("digest", "airband-tx"))
    called = []
    monkeypatch.setattr(cli, "flash", lambda *args, **kwargs: called.append((args, kwargs)))

    result = cli.main([
        "flash", "image.bin", "--port", "FAKE",
        "--confirm-model", "RT-1000PRO", "--yes",
    ])
    assert result == 2
    assert not called
    assert "recovery-confirmed" in capsys.readouterr().err


def test_airband_flash_runs_only_with_explicit_confirmations(monkeypatch):
    monkeypatch.setattr(cli, "_read_image", lambda path: b"image")
    monkeypatch.setattr(cli, "_preflight", lambda image: ("digest", "airband-tx"))
    called = []

    def fake_flash(*args, **kwargs):
        called.append((args, kwargs))
        return FlashResult(246, 251904, False)

    monkeypatch.setattr(cli, "flash", fake_flash)
    result = cli.main([
        "flash", "image.bin", "--port", "FAKE",
        "--confirm-model", "RT-1000PRO", "--yes",
        "--recovery-confirmed", "--power-confirmed", "--authorized-airband",
    ])
    assert result == 0
    assert len(called) == 1
    assert called[0][0] == (b"image", "FAKE")
