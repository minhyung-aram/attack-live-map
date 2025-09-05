# web/utils.py

def get_flag_emoji(country_code: str) -> str:
    """ISO 3166-1 alpha-2 코드를 국기 이모지로 변환합니다."""
    if not isinstance(country_code, str) or len(country_code) != 2:
        return "🏳️"  # 알 수 없는 국가

    # 유니코드 지역 인디케이터 심볼 (RIS) 기반
    # 'US' -> 'U' + 'S' -> U+1F1FA U+1F1F8 -> 🇺🇸
    base = 0x1F1E6
    first = ord(country_code[0].upper())
    second = ord(country_code[1].upper())

    if not ('A' <= chr(first) <= 'Z' and 'A' <= chr(second) <= 'Z'):
        return "🏳️"

    return chr(base + first - ord('A')) + chr(base + second - ord('A'))

def interp(lon1, lat1, lon2, lat2, a: float):
    """두 좌표 사이를 선형 보간합니다."""
    return [float(lon1 + (lon2 - lon1) * a), float(lat1 + (lat2 - lat1) * a)]