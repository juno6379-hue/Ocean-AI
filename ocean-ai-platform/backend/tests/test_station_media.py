import base64
import hashlib
import pytest
from fastapi import HTTPException
from app.services.station_media import parse_photo,photograph

def page(station='DT_0028',payload=b'GIF89a' + b'\0'*16):
    # The provider labels a GIF as PNG; the client must use the actual signature.
    return '<input id="data" data-obsPostId="'+station+'" data-obsPostName="진도"><img alt="관측소 이미지" src="data:image/png;base64,'+base64.b64encode(payload).decode()+'">'

def test_photo_binds_exact_station_and_detects_real_mime_without_claiming_historical_date():
    result=parse_photo(page(),'DT_0028')
    assert result['image_url'].startswith('data:image/gif;base64,')
    assert result['captured_at'] is None and result['historical_photo_asserted'] is False
    assert result['image_sha256']==hashlib.sha256(b'GIF89a' + b'\0'*16).hexdigest()
    with pytest.raises(HTTPException):parse_photo(page('DT_0001'),'DT_0028')
    with pytest.raises(HTTPException):parse_photo(page(payload=b'<script>'),'DT_0028')

def test_missing_photo_is_not_a_generic_station_picture_or_network_request():
    result=parse_photo('<input id="data" data-obsPostId="DT_0028">','DT_0028')
    assert result['image_url'] is None and result['image_sha256'] is None
    assert result['captured_at'] is None and result['historical_photo_asserted'] is False
    assert result['source_url'].endswith('obs_post_id=DT_0028')
    with pytest.raises(HTTPException) as error:photograph('../evil','2026-10-09')
    assert error.value.status_code==422


def test_conflicting_identity_cannot_be_overwritten_by_a_matching_later_input():
    html='<input id="data" data-obsPostId="DT_0001">'+page()
    with pytest.raises(HTTPException) as error:parse_photo(html,'DT_0028')
    assert error.value.status_code==502


def test_wrapped_base64_is_decoded_to_identical_bytes():
    content=b'GIF89a' + b'\0'*16
    payload=base64.b64encode(content).decode()
    html=page().replace(payload,payload[:12]+'\n'+payload[12:])
    result=parse_photo(html,'DT_0028')
    assert base64.b64decode(result['image_url'].split(',')[1])==content
    assert result['image_sha256']==hashlib.sha256(content).hexdigest()
