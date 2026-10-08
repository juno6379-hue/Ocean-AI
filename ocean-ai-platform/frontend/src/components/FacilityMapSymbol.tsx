import L from 'leaflet';

// Exact station_metadata.network_type values; symbols are a UI key, not inferred taxonomy.
export const FACILITY_TYPES = [
  { value: '조위관측소', label: '조위관측소', path: 'M8 20 10 8h4l2 12M9 8h6M10 4h4v4M5 20h14M4 13l3-1M17 12l3 1' },
  { value: '해양관측소', label: '해양관측소', path: 'M4 11l8-7 8 7M7 9v10h10V9M10 19v-5h4v5M3 22h18' },
  { value: '해양관측부이', label: '해양관측부이', path: 'M12 3v9M12 4h5l-5 4M8 12h8l2 6H6l2-6M3 21l3-1 3 1 3-1 3 1 3-1 3 1' },
  { value: 'HF-Radar', label: '해수유동관측소 (HF-radar)', path: 'M12 13v8M7 21h10M12 13l-5-5M5 5a10 10 0 0 0 14 14M8 4a7 7 0 0 1 12 6M9 8a3 3 0 0 1 5 3' },
  { value: '해양과학기지', label: '해양과학기지', path: 'M3 13h18M6 13v8M18 13v8M8 7h8v6M10 7V3h4v4M4 21h4M16 21h4M17 6h4M19 4v4' },
] as const;
const unknownPath = 'M12 3 21 12 12 21 3 12 12 3M12 8v5M12 16v.1';
const pathFor = (type: string | null) => FACILITY_TYPES.find(row => row.value === type)?.path || unknownPath;

export function FacilitySymbol({ type, className = 'w-4 h-4' }: { type: string | null; className?: string }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={pathFor(type)}/></svg>;
}

export function facilityMapIcon(type: string | null, selected = false) {
  // All current records have unconfirmed operating/QC status: never imply green/normal.
  return L.divIcon({ className: 'facility-map-marker', iconSize: [30, 30], iconAnchor: [15, 15],
    html: `<div style="width:30px;height:30px;background:white;color:#64748b;border:2px solid ${selected ? '#2563eb' : '#64748b'};border-radius:8px;box-shadow:0 1px 5px #0003;display:flex;align-items:center;justify-content:center"><svg aria-hidden="true" width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${pathFor(type)}"/></svg></div>` });
}
