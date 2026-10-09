"""Public KHOA station photographs, bound to the returned station identity."""
import base64
import hashlib
from datetime import datetime,timezone
from functools import lru_cache
from html.parser import HTMLParser
import re
import httpx
from fastapi import HTTPException

DETAIL_URL='https://www.khoa.go.kr/oceandata/oceaninfo/detail.do'

class StationPhotoParser(HTMLParser):
    def __init__(self):
        super().__init__();self.identities=[];self.name=None;self.photos=[]
    def handle_starttag(self,tag,attrs):
        fields=dict(attrs)
        if tag=='input' and fields.get('id')=='data':
            self.identities.append(fields.get('data-obspostid'));self.name=fields.get('data-obspostname')
        if tag=='img' and fields.get('alt')=='관측소 이미지':self.photos.append(fields.get('src',''))

def parse_photo(html,station):
    parser=StationPhotoParser();parser.feed(html)
    if not parser.identities or any(identity!=station for identity in parser.identities):
        raise HTTPException(502,'공식 사진 응답의 관측소 코드가 일치하지 않습니다.')
    metadata=dict(station=station,station_name=parser.name,
        source_url=DETAIL_URL+'?obs_post_id='+station,credit='국립해양조사원 바다누리 해양정보',
        captured_at=None,retrieved_at=datetime.now(timezone.utc).isoformat(),historical_photo_asserted=False)
    if not parser.photos:return dict(**metadata,status='NO_PUBLIC_PHOTO',image_url=None,image_sha256=None)
    source=parser.photos[0]
    match=re.fullmatch(r'data:image/[a-zA-Z]+;base64,([A-Za-z0-9+/=\s]+)',source)
    if not match:raise HTTPException(502,'공식 사진의 이미지 형식을 확인할 수 없습니다.')
    try:content=base64.b64decode(re.sub(r'\s+','',match[1]),validate=True)
    except ValueError:raise HTTPException(502,'공식 사진의 base64 형식이 올바르지 않습니다.')
    mime='image/gif' if content.startswith((b'GIF87a',b'GIF89a')) else 'image/png' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else None
    if mime is None or len(content)>8_000_000:raise HTTPException(502,'지원하지 않는 공식 사진 형식입니다.')
    return dict(**metadata,status='AVAILABLE',image_url='data:'+mime+';base64,'+base64.b64encode(content).decode(),
        image_sha256=hashlib.sha256(content).hexdigest())

@lru_cache(maxsize=64)
def photograph(station,cache_day):
    if not re.fullmatch(r'[A-Z]{2}_[0-9]{4}',station):raise HTTPException(422,'공식 관측소 코드 형식을 선택하세요.')
    try:
        with httpx.Client(timeout=15,follow_redirects=False) as client:
            with client.stream('POST',DETAIL_URL,data={'obs_post_id':station}) as response:
                response.raise_for_status();chunks=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>12_000_000:raise HTTPException(502,'공식 상세페이지가 허용 크기를 초과했습니다.')
                    chunks.append(chunk)
                return parse_photo(b''.join(chunks).decode('utf-8'),station)
    except (httpx.HTTPError,UnicodeDecodeError):raise HTTPException(502,'공식 관측소 사진을 불러오지 못했습니다.')
