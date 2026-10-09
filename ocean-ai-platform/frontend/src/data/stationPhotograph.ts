export type StationPhotograph = {
  station: string;
  station_name?: string;
  status: 'AVAILABLE' | 'NO_PUBLIC_PHOTO';
  image_url: string | null;
  image_sha256: string | null;
  source_url: string;
  credit: string;
  captured_at: null;
  retrieved_at: string;
  historical_photo_asserted: false;
};

/** A current public photograph identifies a station; it does not date the observations. */
export function stationPhotograph(value: unknown, station: string): StationPhotograph {
  if (!value || typeof value !== 'object') throw new Error('사진 응답을 확인할 수 없습니다.');
  const record = value as Record<string, unknown>;
  const officialSource = 'https://www.khoa.go.kr/oceandata/oceaninfo/detail.do?obs_post_id=' + station;
  if (record.station !== station || record.source_url !== officialSource ||
      record.historical_photo_asserted !== false || record.captured_at !== null ||
      typeof record.credit !== 'string' || typeof record.retrieved_at !== 'string') {
    throw new Error('사진 관측소와 출처를 확인할 수 없습니다.');
  }
  if (record.status === 'NO_PUBLIC_PHOTO' && record.image_url === null && record.image_sha256 === null) {
    return record as StationPhotograph;
  }
  if (record.status !== 'AVAILABLE' || typeof record.image_url !== 'string' ||
      !/^data:image\/(?:gif|png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/.test(record.image_url) ||
      typeof record.image_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(record.image_sha256)) {
    throw new Error('공식 사진의 형식을 확인할 수 없습니다.');
  }
  return record as StationPhotograph;
}
