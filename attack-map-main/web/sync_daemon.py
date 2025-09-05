import os, json, threading, time, tempfile, shutil
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from functools import lru_cache 

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

import maxminddb

load_dotenv()

_AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
_BUCKET = os.getenv("S3_BUCKET_NAME")
_KEY = os.getenv("S3_EVENTS_FILE_KEY", "events.json")
_LOCAL_PATH = os.getenv("LOCAL_EVENTS_FILE", "data/events.json")
_INTERVAL_S = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))
_GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH")

_client_singleton = None
_thread = None
_stop_flag = threading.Event()
_started = False
_lock = threading.Lock()
_geoip_reader = None
_geoip_lock = threading.Lock()


def _get_geoip_reader():
    global _geoip_reader
    if _geoip_reader is None:
        with _geoip_lock:
            if _geoip_reader is None:
                if not _GEOIP_DB_PATH or not Path(_GEOIP_DB_PATH).exists():
                    print("[sync] 오류: GeoLite2-City.mmdb 파일을 찾을 수 없습니다.")
                    return None
                try:
                    _geoip_reader = maxminddb.open_database(_GEOIP_DB_PATH)
                    print("[sync] GeoLite2-City.mmdb 파일을 메모리에 로드했습니다.")
                except maxminddb.errors.InvalidDatabaseError as e:
                    print(f"[sync] 오류: 잘못된 GeoLite2-City.mmdb 파일: {e}")
                    return None
    return _geoip_reader

@lru_cache(maxsize=4096) # 최대 4096개의 IP 조회 결과를 메모리에 저장
def _get_location_for_ip(ip: str) -> Optional[Dict[str, Any]]:
    """IP 주소에 대한 위치 정보를 조회하고 결과를 캐싱합니다."""
    reader = _get_geoip_reader()
    if not reader or not ip:
        return None
    
    try:
        match = reader.get(ip)
        if match:
            return {
                'lat': match.get('location', {}).get('latitude'),
                'lon': match.get('location', {}).get('longitude'),
                'country': match.get('country', {}).get('names', {}).get('en', 'Unknown')
            }
        return {'country': 'Unknown'} # 조회가 됐지만 정보가 없는 경우
    except Exception as e:
        print(f"[sync] IP '{ip}' 처리 오류: {e}")
        return {'country': 'Unknown'} # 오류 발생 시


def _fill_location_info(event: Dict[str, Any]):
    """주어진 이벤트에 위치 정보를 채웁니다 (캐시된 함수 사용)."""
    src_ip = event.get('src_ip')
    if src_ip:
        location_data = _get_location_for_ip(src_ip)
        if location_data:
            # event.update()를 사용해 여러 키를 한 번에 업데이트
            event.update(location_data)
        else:
            event['country'] = 'Unknown'


def _s3_client():
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = boto3.client("s3", aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"), region_name=_AWS_REGION)
    return _client_singleton


def _ensure_local_dir(path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _read_s3_json() -> Optional[Union[List[Any], Dict[str, Any]]]:
    try:
        resp = _s3_client().get_object(Bucket=_BUCKET, Key=_KEY)
        body = resp["Body"].read().decode("utf-8")
        return json.loads(body)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        print(f"[sync] S3 오류: {code} - {e}")
    except json.JSONDecodeError as e:
        print(f"[sync] JSON 파싱 오류: {e}")
    except Exception as e:
        print(f"[sync] 기타 오류: {e}")
    return None


def _atomic_write_json(path: str, data: Any):
    _ensure_local_dir(path)
    dir_ = str(Path(path).parent)
    fd, tmp = tempfile.mkstemp(prefix="events-", suffix=".json", dir=dir_, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, path)
    finally:
        try:
            if os.path.exists(tmp): os.remove(tmp)
        except Exception: pass


def _sync_once() -> int:
    s3_data = _read_s3_json()
    if s3_data is None: return 0

    s3_list = s3_data if isinstance(s3_data, list) else ([s3_data] if isinstance(s3_data, dict) else [])
    if not s3_list: return 0

    # 1. 위치 정보가 필요한 고유 IP 목록을 먼저 추출합니다.
    unique_ips_to_find = {
        item['src_ip'] for item in s3_list 
        if item.get('src_ip') and (item.get('lat') is None or item.get('country') in ['N/A', None])
    }
    
    # 2. 고유 IP 목록에 대해서만 GeoIP 조회를 수행하여 캐시를 채웁니다.
    if unique_ips_to_find:
        print(f"[sync] {len(unique_ips_to_find)}개의 고유 IP에 대한 위치 정보를 조회합니다.")
        for ip in unique_ips_to_find:
            _get_location_for_ip(ip) # 함수를 호출하여 캐시에 결과를 저장

    # 3. 전체 데이터를 순회하며 캐시된 정보로 빠르게 값을 채웁니다.
    filled_count = 0
    for item in s3_list:
        if item.get('src_ip') and (item.get('lat') is None or item.get('country') in ['N/A', None]):
            _fill_location_info(item)
            filled_count += 1
            
    with _lock:
        _atomic_write_json(_LOCAL_PATH, s3_list)
        
    return filled_count


def _loop():
    print(f"[sync] 시작: interval={_INTERVAL_S}s, bucket={_BUCKET}, key={_KEY}, local={_LOCAL_PATH}")
    while not _stop_flag.is_set():
        try:
            filled_count = _sync_once()
            print(f"[sync] 동기화 완료: {filled_count}건의 위치 정보가 업데이트 되었습니다.")
        except Exception as e:
            print(f"[sync] 루프 오류: {e}")
        _stop_flag.wait(_INTERVAL_S)
    print("[sync] 중지")

def start_sync_daemon() -> None:
    global _thread, _started
    if _started: return
    with _lock:
        if _started: return
        _stop_flag.clear()
        _thread = threading.Thread(target=_loop, daemon=True)
        _thread.start()
        _started = True

def stop_sync_daemon() -> None:
    global _thread, _started, _geoip_reader
    with _lock:
        if not _started: return
        _stop_flag.set()
        if _thread: _thread.join(timeout=2)
        _thread = None
        _started = False
    if _geoip_reader:
        _geoip_reader.close()
        _geoip_reader = None

if __name__ == "__main__":
    start_sync_daemon()
    try:
        while True: time.sleep(3600)
    except KeyboardInterrupt:
        stop_sync_daemon()