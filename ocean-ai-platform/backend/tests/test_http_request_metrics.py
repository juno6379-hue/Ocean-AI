"""A response counter cannot turn absent history into uptime or a zero rate."""
from datetime import datetime, timezone, timedelta

from app.services.http_request_metrics import RequestMetrics

BASE=datetime(2026,10,8,tzinfo=timezone.utc)


def test_completed_statuses_have_actual_denominators_and_window_filter():
    metrics=RequestMetrics(started_at=BASE)
    metrics.record(200,10,BASE+timedelta(seconds=1))
    metrics.record(404,20,BASE+timedelta(seconds=2))
    metrics.record(503,30,BASE+timedelta(seconds=3))
    result=metrics.overview(BASE,BASE+timedelta(seconds=2),BASE+timedelta(seconds=5))
    assert result['request_count']==2 and result['error_count']==1
    assert result['error_rate_percent']==50 and result['average_latency_ms']==15
    assert result['status_counts']=={'200':1,'404':1}
    assert result['capture_complete_for_requested_window'] is True


def test_old_unobserved_history_and_no_responses_are_not_zero_error_rate():
    metrics=RequestMetrics(started_at=BASE)
    result=metrics.overview(BASE-timedelta(days=1),BASE-timedelta(seconds=1),BASE)
    assert result['status']=='OUTSIDE_CAPTURE_WINDOW' and result['error_rate_percent'] is None
    result=metrics.overview(BASE-timedelta(days=1),BASE+timedelta(seconds=2),BASE+timedelta(seconds=2))
    assert result['status']=='NO_REQUESTS' and result['request_count']==0
    assert result['error_rate_percent'] is None and result['capture_complete_for_requested_window'] is False
    assert result['captured_from']==BASE.isoformat()


def test_truncated_history_never_claims_complete_selected_window():
    metrics=RequestMetrics(capacity=2,started_at=BASE)
    for seconds,status in [(1,200),(2,400),(3,200)]:
        metrics.record(status,1,BASE+timedelta(seconds=seconds))
    result=metrics.overview(BASE,BASE+timedelta(seconds=4),BASE+timedelta(seconds=4))
    assert result['request_count']==2 and result['error_rate_percent']==50
    assert result['capture_complete_for_requested_window'] is False
    assert result['truncated_through']==(BASE+timedelta(seconds=1)).isoformat()
    result=metrics.overview(BASE+timedelta(seconds=2),BASE+timedelta(seconds=4),BASE+timedelta(seconds=4))
    assert result['capture_complete_for_requested_window'] is True


def test_concurrent_completion_order_cannot_move_truncation_boundary_backwards():
    metrics=RequestMetrics(capacity=1,started_at=BASE)
    for second in (3,1,4):metrics.record(200,1,BASE+timedelta(seconds=second))
    result=metrics.overview(BASE+timedelta(seconds=2),BASE+timedelta(seconds=5),BASE+timedelta(seconds=5))
    assert result['truncated_through']==(BASE+timedelta(seconds=3)).isoformat()
    assert result['capture_complete_for_requested_window'] is False
