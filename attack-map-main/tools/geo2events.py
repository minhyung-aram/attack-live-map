#  테스팅용 코드

# tools/geo2events.py
import json, time, ipaddress, os
from geoip2.database import Reader

DB = r"data/GeoLite2-City.mmdb"
OUT = r"web/events.json"

SAMPLE = ["1.1.1.1", "8.8.8.8", "9.9.9.9", "1.0.0.1"]  # 필요시 실제 IP로 교체

def is_public(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    reader = Reader(DB)
    events = []
    for ip in SAMPLE:
        if not is_public(ip):
            continue
        try:
            r = reader.city(ip)
            events.append({
                "ip": ip,
                "ts": int(time.time()),
                "lat": r.location.latitude,
                "lon": r.location.longitude,
                "country": r.country.iso_code,
                "city": r.city.name or "",
                "label": f'{r.country.iso_code}/{r.city.name or ""}'
            })
        except Exception:
            pass

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False)
    print(f"Wrote {len(events)} events -> {os.path.abspath(OUT)}")

if __name__ == "__main__":
    main()
