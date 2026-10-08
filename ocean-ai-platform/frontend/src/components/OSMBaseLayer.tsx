import { useState } from 'react';
import { TileLayer } from 'react-leaflet';

/** Shared OSM tiles; observation overlays remain independent of tile availability. */
export default function OSMBaseLayer() {
  const [failed,setFailed]=useState(false);
  return <><TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
    attribution={'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'}
    eventHandlers={{tileerror:()=>setFailed(true),loading:()=>setFailed(false)}}/>
    {failed&&<div role="status" className="absolute bottom-6 left-2 right-2 z-[450] rounded bg-white/95 border border-amber-200 p-2 text-xs text-amber-800">OSM 배경지도 일부를 불러오지 못했습니다. 관측소 목록과 자료 조회는 계속 사용할 수 있습니다.</div>}
  </>;
}
