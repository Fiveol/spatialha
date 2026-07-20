import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "spatialble"))

from spatialble_decoders import decode_ibeacon, decode_eddystone


def test_decode_ibeacon():
    # iBeacon: AD type 0x02, AD len 0x15, UUID, major=1, minor=12, tx=-56
    raw = "0215e2c56db5dffb48d2b060d0f5a71096e00001000cc8"
    result = decode_ibeacon({"004c": raw})
    assert result is not None
    assert result["type"] == "ibeacon"
    assert result["uuid"] == "e2c56db5-dffb-48d2-b060-d0f5a71096e0"
    assert result["major"] == 1
    assert result["minor"] == 12
    assert result["tx_power"] == -56


def test_decode_ibeacon_invalid():
    assert decode_ibeacon({}) is None
    assert decode_ibeacon({"004c": "ff"}) is None


def test_decode_eddystone_url():
    # Eddystone URL: frame type 0x10, scheme 2 (http://), "test", 0x00 (.com/)
    raw = "10027465737400"
    result = decode_eddystone({"feaa": raw})
    assert result is not None
    assert result["type"] == "eddystone_url"
    assert "test" in result["url"]


def test_decode_eddystone_uid():
    # Eddystone UID: frame type 0x00, 10B namespace, 6B instance
    raw = "00" + "aa" * 10 + "bb" * 6
    result = decode_eddystone({"feaa": raw})
    assert result is not None
    assert result["type"] == "eddystone_uid"
    assert result["namespace"] == "a" * 20
    assert result["instance"] == "b" * 12
