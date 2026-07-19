"""
BLE advertisement decoders: iBeacon, Eddystone, IRK resolution, and helpers.
"""

import struct
from typing import Optional

# Apple company ID (little-endian)
APPLE_CO_ID = "004c"

# Eddystone Service UUID
EDDYSTONE_SVC_UUID = "feaa"

# Known service UUID names
SERVICE_NAMES = {
    "1800": "Generic Access",
    "1801": "Generic Attribute",
    "1802": "Immediate Alert",
    "1803": "Link Loss",
    "1804": "Tx Power",
    "1805": "Current Time",
    "1806": "Reference Time Update",
    "1807": "Next DST Change",
    "1808": "Glucose",
    "1809": "Health Thermometer",
    "180a": "Device Information",
    "180d": "Heart Rate",
    "180f": "Battery Service",
    "1810": "Blood Pressure",
    "1811": "Alert Notification",
    "1812": "Human Interface Device",
    "1813": "Scan Parameters",
    "1814": "Running Speed and Cadence",
    "1815": "Automation IO",
    "1816": "Cycling Speed and Cadence",
    "181a": "Environmental Sensing",
    "181c": "User Data",
}

GRAPH_COLORS = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
    "#e6beff", "#9a6324", "#fffac8", "#800000", "#aaffc3",
    "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#ff4777",
]


def decode_ibeacon(manufacturer_data: dict) -> Optional[dict]:
    """Decode Apple iBeacon from manufacturer data.

    iBeacon format (within Apple MFG data, company 0x004C):
      Byte 0: AD type (0x02 = iBeacon)
      Byte 1: AD length (0x15 = 21)
      Bytes 2-17: Proximity UUID (16 bytes)
      Bytes 18-19: Major (2 bytes, big-endian)
      Bytes 20-21: Minor (2 bytes, big-endian)
      Byte 22: TX Power (signed, dBm at 1m)
    """
    raw = manufacturer_data.get(APPLE_CO_ID)
    if not raw:
        return None
    data = bytes.fromhex(raw)
    if len(data) < 23 or data[0] != 0x02 or data[1] != 0x15:
        return None

    uuid_bytes = data[2:18]
    uuid_str = "-".join([
        uuid_bytes[0:4].hex(),
        uuid_bytes[4:6].hex(),
        uuid_bytes[6:8].hex(),
        uuid_bytes[8:10].hex(),
        uuid_bytes[10:16].hex(),
    ])
    major = struct.unpack(">H", data[18:20])[0]
    minor = struct.unpack(">H", data[20:22])[0]
    tx_power = struct.unpack("b", data[22:23])[0]

    return {
        "type": "ibeacon",
        "uuid": uuid_str,
        "major": major,
        "minor": minor,
        "tx_power": tx_power,
    }


def decode_eddystone(service_data: dict) -> Optional[dict]:
    """Decode Google Eddystone from service data (UUID 0xFEAA).

    Eddystone frame types:
      UID:  0x00 + 10B namespace + 6B instance
      URL:  0x10 + URL scheme + encoded URL
      TLM:  0x20 + battery(2B) + temp(2B) + pkt cnt(4B) + uptime(4B)
    """
    raw = service_data.get(EDDYSTONE_SVC_UUID)
    if not raw:
        return None
    data = bytes.fromhex(raw)
    if not data:
        return None

    frame_type = data[0]

    if frame_type == 0x00 and len(data) >= 17:
        namespace = data[1:11].hex()
        instance = data[11:17].hex()
        return {"type": "eddystone_uid", "namespace": namespace, "instance": instance}

    if frame_type == 0x10 and len(data) >= 2:
        url_schemes = ["http://www.", "https://www.", "http://", "https://"]
        url_prefix = url_schemes[data[1]] if data[1] < len(url_schemes) else ""
        url_suffix = {
            0x00: ".com/", 0x01: ".org/", 0x02: ".edu/", 0x03: ".net/",
            0x04: ".info/", 0x05: ".biz/", 0x06: ".gov/", 0x07: ".com",
            0x08: ".org",  0x09: ".edu",  0x0a: ".net",  0x0b: ".info",
            0x0c: ".biz",  0x0d: ".gov",
        }
        url = url_prefix
        for b in data[2:]:
            url += url_suffix.get(b, chr(b))
        return {"type": "eddystone_url", "url": url}

    if frame_type == 0x20 and len(data) >= 14:
        batt, temp_raw, pkt_cnt, uptime = struct.unpack(">HhII", data[1:13])
        temp = temp_raw / 256.0
        return {
            "type": "eddystone_tlm",
            "battery_mv": batt,
            "temp_c": temp,
            "pkt_count": pkt_cnt,
            "uptime_s": uptime,
        }

    if frame_type == 0x30 and len(data) >= 5:
        # EID (Ephemeral ID)
        eid = data[1:9].hex() if len(data) >= 9 else data[1:].hex()
        return {"type": "eddystone_eid", "eid": eid}

    return {"type": f"eddystone_unknown_{frame_type:02x}", "raw": raw}


def resolve_irk(address: str, irk_hex: str) -> Optional[str]:
    """Resolve a BLE resolvable private address using an IRK.

    RPBA = irk_resolve(prand << 192 | hash) where:
      - prand = address[0:3] (random part)
      - hash  = address[3:6] (hash part)
    Uses the AES-CMAC prand resolution per Core Spec Vol 3 Part C 10.8.2.4.
    """
    try:
        from Crypto.Cipher import AES
    except ImportError:
        return None

    try:
        irk = bytes.fromhex(irk_hex)
    except ValueError:
        return None
    if len(irk) != 16:
        return None

    addr_bytes = bytes.fromhex(address.replace(":", ""))
    if len(addr_bytes) != 6:
        return None
    if (addr_bytes[5] & 0xC0) != 0x40:
        return None  # not a resolvable private address

    prand = addr_bytes[3:6][::-1]  # little-endian prand
    hash_actual = addr_bytes[0:3]

    from Crypto.Cipher import AES
    cipher = AES.new(irk, AES.MODE_ECB)
    # Core Spec: reverse prand, pad to 16 bytes, encrypt with IRK
    m = prand + b"\x00" * 13
    encrypted = cipher.encrypt(m)
    hash_computed = encrypted[0:3]

    if hash_computed == hash_actual:
        identity = addr_bytes
        identity = bytes([identity[i] for i in [5, 4, 3, 2, 1, 0]])
        return ":".join(f"{b:02x}" for b in identity)

    return None
