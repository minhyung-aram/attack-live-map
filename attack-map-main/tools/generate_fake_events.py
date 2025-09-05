import json, random, time, uuid, pathlib, datetime as dt

OUT = pathlib.Path("data/events.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

SPOTS = {
    "CN": [(31.23, 121.47), (39.90, 116.40), (22.54, 114.06)],
    "RU": [(55.75, 37.62), (59.94, 30.31)],
    "US": [(40.71, -74.00), (34.05, -118.24), (47.61, -122.33)],
    "KR": [(37.57, 126.98), (35.18, 129.07)],
    "BR": [(-23.55, -46.63), (-22.91, -43.17)],
    "IN": [(28.61, 77.21), (19.08, 72.88)],
}
PORTS = [22, 23, 80, 443, 3306, 6379]
LABELS = ["bruteforce", "malware-drop", "scanner", "miner", "worm"]

RING_LIMIT = 5000
buf = []

print("[generator] writing to:", OUT)
while True:
    src_country = random.choice(list(SPOTS))
    dst_country = random.choice(list(SPOTS))

    src_lat, src_lon = random.choice(SPOTS[src_country])
    dst_lat, dst_lon = random.choice(SPOTS[dst_country])

    item = {
        "id": str(uuid.uuid4()),
        "ts": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "src_ip": f"198.51.100.{random.randint(1,254)}",
        "dst_ip": f"192.0.2.{random.randint(1,254)}",
        "src_country": src_country,
        "dst_country": dst_country,
        "src_lat": src_lat,
        "src_lon": src_lon,
        "dst_lat": dst_lat,
        "dst_lon": dst_lon,
        "port": random.choice(PORTS),
        "proto": "tcp",
        "label": random.choice(LABELS),
        "severity": random.choice([1, 2, 2, 3, 3, 4])
    }

    buf.append(item)
    if len(buf) > RING_LIMIT:
        buf = buf[-RING_LIMIT:]

    OUT.write_text(json.dumps(buf, indent=2), encoding="utf-8")
    time.sleep(0.7)
