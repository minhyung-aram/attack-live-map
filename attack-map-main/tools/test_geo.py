#  테스팅용 코드


# tools/test_geo.py
from geoip2.database import Reader

DB = r"data/GeoLite2-City.mmdb"
reader = Reader(DB)

for ip in ["1.1.1.1", "8.8.8.8"]:
    r = reader.city(ip)
    print(ip, r.country.iso_code, r.city.name, r.location.latitude, r.location.longitude)
