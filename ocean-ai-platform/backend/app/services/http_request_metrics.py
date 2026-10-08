"""Completed HTTP responses for this process; no identities, paths or payloads."""
from collections import Counter, deque
from datetime import datetime, timezone
from threading import Lock


class RequestMetrics:
    def __init__(self, capacity=50000, started_at=None):
        self.started_at = started_at or datetime.now(timezone.utc)
        self.capacity = capacity
        self.records = deque()
        self.lock = Lock()
        self.truncated_through = None

    def record(self, status, duration_ms, completed_at=None):
        at = completed_at or datetime.now(timezone.utc)
        with self.lock:
            if len(self.records) >= self.capacity:
                removed_at = self.records.popleft()[0]
                self.truncated_through = max(self.truncated_through or removed_at, removed_at)
            self.records.append((at, int(status), max(0, float(duration_ms))))

    def overview(self, start, end, now=None):
        now = now or datetime.now(timezone.utc)
        with self.lock:
            records = list(self.records)
            truncated = self.truncated_through
        selected = [r for r in records if start <= r[0] <= end]
        counts = Counter(r[1] for r in selected)
        errors = sum(count for status, count in counts.items() if status >= 400)
        capture_start = max(start, self.started_at, truncated or self.started_at)
        capture_end = min(end, now)
        overlap = capture_start <= capture_end
        complete = start >= self.started_at and end <= now and (truncated is None or start > truncated)
        return {
            'status': 'AVAILABLE' if selected else 'NO_REQUESTS' if overlap else 'OUTSIDE_CAPTURE_WINDOW',
            'coverage': 'CURRENT_PROCESS_ONLY', 'capture_complete_for_requested_window': complete,
            'process_started_at': self.started_at.isoformat(),
            'captured_from': capture_start.isoformat() if overlap else None,
            'captured_to': capture_end.isoformat() if overlap else None,
            'requested_from': start.isoformat(), 'requested_to': end.isoformat(),
            'request_count': len(selected), 'error_count': errors,
            'error_rate_percent': round(100 * errors / len(selected), 3) if selected else None,
            'average_latency_ms': round(sum(r[2] for r in selected) / len(selected), 3) if selected else None,
            'status_counts': {str(key): count for key, count in sorted(counts.items())},
            'error_definition': 'HTTP_STATUS_GTE_400',
            'retention_limit': self.capacity, 'truncated_through': truncated.isoformat() if truncated else None,
            'note': '현재 API 프로세스가 완료한 응답의 기록 구간입니다. 재시작 전·기록 밖 요청과 서비스 가동률은 포함하지 않습니다. 이번 조회 응답은 완료 후 기록됩니다.',
        }


request_metrics = RequestMetrics()
