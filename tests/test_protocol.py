import struct

import pytest

from rt1000pro import FLASH_BASE, FLASH_SIZE
from rt1000pro.firmware import FirmwareError
from rt1000pro.protocol import (
    BLOCK_COUNT,
    BLOCK_SIZE,
    CONNECT,
    UPDATE,
    build_data_packet,
    dry_run,
    flash,
    packet_checksum,
)


def image() -> bytes:
    result = bytearray((index * 37) & 0xFF for index in range(FLASH_SIZE))
    struct.pack_into("<II", result, 0, 0x2000AEC8, FLASH_BASE | 1)
    return bytes(result)


def test_constants_match_recovered_protocol():
    assert CONNECT == bytes.fromhex("3933051028")
    assert UPDATE == bytes.fromhex("393305556d")
    assert BLOCK_COUNT == 246
    assert BLOCK_SIZE == 1024


def test_packet_layout_and_checksum():
    source = image()
    packet = build_data_packet(source, 1024)
    assert len(packet) == 1028
    assert packet[:3] == bytes.fromhex("570400")
    assert packet[3:-1] == source[1024:2048]
    assert packet[-1] == packet_checksum(packet[:-1])
    with pytest.raises(ValueError, match="Offset"):
        build_data_packet(source, 1)


def test_dry_run_validates_every_packet_without_serial():
    result = dry_run(image())
    assert result.simulated
    assert result.blocks == 246
    assert result.bytes_sent == FLASH_SIZE



def test_flash_state_machine_with_fake_serial(monkeypatch):
    import sys
    import types

    class FakeSerial:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.writes = []
            self.responses = bytearray()
            self.dtr = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def reset_input_buffer(self):
            self.responses.clear()

        def reset_output_buffer(self):
            pass

        def write(self, data):
            self.writes.append(bytes(data))
            self.responses.append(0x06)
            return len(data)

        def flush(self):
            pass

        def read(self, size):
            if not self.responses:
                return b""
            value = bytes(self.responses[:size])
            del self.responses[:size]
            return value

    fake = FakeSerial()

    def create_serial(**kwargs):
        fake.__init__(**kwargs)
        return fake

    module = types.SimpleNamespace(
        Serial=create_serial,
        SerialException=RuntimeError,
        EIGHTBITS=8,
        PARITY_NONE="N",
        STOPBITS_ONE=1,
    )
    monkeypatch.setitem(sys.modules, "serial", module)
    sleeps = []
    monkeypatch.setattr("rt1000pro.protocol.time.sleep", sleeps.append)
    progress = []
    result = flash(image(), "FAKE", progress=lambda done, total: progress.append((done, total)))
    assert not result.simulated
    assert fake.kwargs["baudrate"] == 115200
    assert fake.dtr is True
    assert fake.writes[:4] == [CONNECT, CONNECT, CONNECT, UPDATE]
    assert len(fake.writes) == 4 + BLOCK_COUNT
    assert progress[-1] == (BLOCK_COUNT, BLOCK_COUNT)
    assert len(sleeps) == 2 + 1 + BLOCK_COUNT - 1
    assert sleeps.count(0.05) == 2
    assert sleeps.count(0.01) == len(sleeps) - 2



def test_flash_never_retries_after_bootloader_error(monkeypatch):
    import sys
    import types

    class RejectingSerial:
        def __init__(self, **kwargs):
            self.writes = []
            self.dtr = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def write(self, data):
            self.writes.append(bytes(data))
            return len(data)

        def flush(self):
            pass

        def read(self, size):
            return b"\xff"

    fake = RejectingSerial()
    module = types.SimpleNamespace(
        Serial=lambda **kwargs: fake,
        SerialException=RuntimeError,
        EIGHTBITS=8,
        PARITY_NONE="N",
        STOPBITS_ONE=1,
    )
    monkeypatch.setitem(sys.modules, "serial", module)
    with pytest.raises(FirmwareError, match="rechazó CONNECT 1/3"):
        flash(image(), "FAKE")
    assert fake.writes == [CONNECT]
