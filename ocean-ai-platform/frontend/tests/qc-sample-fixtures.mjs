// Isolated backend API DTOs; tokens are replaced with non-live test strings. Large Rule provenance is omitted.
// These fixtures never reach an operational API, and opaque hashes are not asserted as recomputed attestations.
export const sampleFixture={
 "context": {
  "schema_version": "qc-sample-context-1",
  "source": "SAMPLE",
  "is_sample": true,
  "approved": false,
  "transient": true,
  "production_writes": 0,
  "operational_writes": 0,
  "source_reads": 0,
  "model_training": 0,
  "final_qc_writes": 0,
  "restart_erases_state": true,
  "bootstrap_token": "qc-sample-bootstrap-fixture-not-live",
  "bootstrap_expires_in_seconds": 300,
  "fixed_clock": "2026-07-09T15:41:20+09:00",
  "window": {
   "source": "SAMPLE",
   "start": "2026-07-09T14:40:00+09:00",
   "end": "2026-07-09T15:40:00+09:00",
   "as_of": "2026-07-09T15:41:20+09:00",
   "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
   "offset": "+09:00",
   "granularity": "minute",
   "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
  },
  "scenario_catalog": [
   {
    "scenario_id": "normal",
    "label": "정상",
    "description": "명시된 가상 단위·센서·간격으로 정상 범위를 검증합니다."
   },
   {
    "scenario_id": "late",
    "label": "수신 지연",
    "description": "선택 관측값이 8분 늦게 수신되어 DE Rule을 초과합니다."
   },
   {
    "scenario_id": "missing",
    "label": "결측",
    "description": "3개 예정 슬롯이 수신되지 않았습니다. 보간 없이 null로 표시합니다."
   },
   {
    "scenario_id": "spike",
    "label": "Spike · 범위 초과",
    "description": "가상 수온 45도로 급변하여 SP 주의와 GR 범위 초과 BAD가 함께 계산됩니다."
   }
  ],
  "flag_catalog": [
   {
    "code": "1",
    "label": "정상",
    "semantic": "GOOD",
    "color": "#10b981",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "3",
    "label": "주의 / Suspect",
    "semantic": "SUSPECT",
    "color": "#f59e0b",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "4",
    "label": "BAD",
    "semantic": "BAD",
    "color": "#ef4444",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "9",
    "label": "결측 판정",
    "semantic": "MISSING",
    "color": "#a855f7",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "NOT_EVALUATED",
    "label": "Rule 미평가",
    "semantic": "NOT_EVALUATED",
    "color": "#94a3b8",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "UNKNOWN",
    "label": "미확인",
    "semantic": "UNKNOWN",
    "color": "#9ca3af",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   }
  ],
  "sample_definition_version": "QC_SAMPLE_SYNTHETIC_V1",
  "expires_in_seconds": 14400,
  "max_sessions": 64,
  "capabilities": {
   "create_session": true,
   "operational_identity": false,
   "trained_ai": false,
   "definitive_qc": false
  },
  "result_sha256": "4fd5104770492bf1624ad9a8a6752096a85890bfc0386e6969f38c055af93ced"
 },
 "session": {
  "schema_version": "qc-sample-session-1",
  "source": "SAMPLE",
  "is_sample": true,
  "approved": false,
  "transient": true,
  "production_writes": 0,
  "operational_writes": 0,
  "source_reads": 0,
  "model_training": 0,
  "final_qc_writes": 0,
  "restart_erases_state": true,
  "session_id": "qc-sample-session-3wGQD9JJxaHlbO3yZ5YbHS1x",
  "session_token": "qc-sample-token-fixture-not-live",
  "session_revision": 1,
  "generation": 1,
  "expires_in_seconds": 14400,
  "idempotent_replay": false,
  "window": {
   "source": "SAMPLE",
   "start": "2026-07-09T14:40:00+09:00",
   "end": "2026-07-09T15:40:00+09:00",
   "as_of": "2026-07-09T15:41:20+09:00",
   "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
   "offset": "+09:00",
   "granularity": "minute",
   "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
  },
  "session_history": [
   {
    "sequence": 1,
    "action": "CREATE_SESSION",
    "generation": 1,
    "session_revision": 1,
    "sample_clock": "2026-07-09T15:41:20+09:00",
    "actor": "SAMPLE_ENGINE"
   }
  ],
  "result_sha256": "577512f5fb0059f1c3f2d2b1c15e9165208832f0058650168059785b9ce1e05c"
 },
 "overview": {
  "schema_version": "qc-sample-overview-1",
  "source": "SAMPLE",
  "is_sample": true,
  "approved": false,
  "transient": true,
  "production_writes": 0,
  "operational_writes": 0,
  "source_reads": 0,
  "model_training": 0,
  "final_qc_writes": 0,
  "restart_erases_state": true,
  "session_id": "qc-sample-session-3wGQD9JJxaHlbO3yZ5YbHS1x",
  "session_revision": 1,
  "generation": 1,
  "window": {
   "source": "SAMPLE",
   "start": "2026-07-09T14:40:00+09:00",
   "end": "2026-07-09T15:40:00+09:00",
   "as_of": "2026-07-09T15:41:20+09:00",
   "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
   "offset": "+09:00",
   "granularity": "minute",
   "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
  },
  "flag_catalog": [
   {
    "code": "1",
    "label": "정상",
    "semantic": "GOOD",
    "color": "#10b981",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "3",
    "label": "주의 / Suspect",
    "semantic": "SUSPECT",
    "color": "#f59e0b",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "4",
    "label": "BAD",
    "semantic": "BAD",
    "color": "#ef4444",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "9",
    "label": "결측 판정",
    "semantic": "MISSING",
    "color": "#a855f7",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "NOT_EVALUATED",
    "label": "Rule 미평가",
    "semantic": "NOT_EVALUATED",
    "color": "#94a3b8",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   },
   {
    "code": "UNKNOWN",
    "label": "미확인",
    "semantic": "UNKNOWN",
    "color": "#9ca3af",
    "color_policy": "QC_DISPLAY_TONES_2",
    "source": "SAMPLE",
    "stage": "SAMPLE_RULE_QC"
   }
  ],
  "summary": {
   "normal": {
    "count": 1,
    "rate": 25,
    "denominator": 4,
    "stage": "SAMPLE_CASE",
    "denominator_basis": "REPRESENTATIVE_SAMPLE_CASES"
   },
   "suspect": {
    "count": 1,
    "rate": 25,
    "denominator": 4,
    "stage": "SAMPLE_CASE",
    "denominator_basis": "REPRESENTATIVE_SAMPLE_CASES"
   },
   "bad": {
    "count": 1,
    "rate": 25,
    "denominator": 4,
    "stage": "SAMPLE_CASE",
    "denominator_basis": "REPRESENTATIVE_SAMPLE_CASES"
   },
   "missing": {
    "count": 1,
    "rate": 25,
    "denominator": 4,
    "stage": "SAMPLE_CASE",
    "denominator_basis": "REPRESENTATIVE_SAMPLE_CASES"
   },
   "pending": {
    "count": 4,
    "rate": 100,
    "denominator": 4,
    "stage": "SAMPLE_REVIEW_WORKFLOW",
    "definitive_qc": false
   },
   "completed": {
    "count": 0,
    "rate": 0,
    "denominator": 4,
    "stage": "SAMPLE_REVIEW_WORKFLOW",
    "definitive_qc": false
   }
  },
  "counts": {
   "case_count": 4,
   "planned_slots": 244,
   "received_slots": 241,
   "missing_slots": 3,
   "card_denominator_basis": "REPRESENTATIVE_SAMPLE_CASES",
   "series_denominator_basis": "SYNTHETIC_PLANNED_SLOTS"
  },
  "flag_distribution": [
   {
    "code": "1",
    "label": "정상",
    "color": "#10b981",
    "count": 1,
    "rate": 25,
    "denominator": 4
   },
   {
    "code": "3",
    "label": "주의 / Suspect",
    "color": "#f59e0b",
    "count": 1,
    "rate": 25,
    "denominator": 4
   },
   {
    "code": "4",
    "label": "BAD",
    "color": "#ef4444",
    "count": 1,
    "rate": 25,
    "denominator": 4
   },
   {
    "code": "9",
    "label": "결측 판정",
    "color": "#a855f7",
    "count": 1,
    "rate": 25,
    "denominator": 4
   },
   {
    "code": "NOT_EVALUATED",
    "label": "Rule 미평가",
    "color": "#94a3b8",
    "count": 0,
    "rate": 0,
    "denominator": 4
   },
   {
    "code": "UNKNOWN",
    "label": "미확인",
    "color": "#9ca3af",
    "count": 0,
    "rate": 0,
    "denominator": 4
   }
  ],
  "quality_trend": [
   {
    "bucket": "2026-07-09T14:40:00+09:00",
    "start": "2026-07-09T14:40:00+09:00",
    "end": "2026-07-09T14:40:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:41:00+09:00",
    "start": "2026-07-09T14:41:00+09:00",
    "end": "2026-07-09T14:41:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:42:00+09:00",
    "start": "2026-07-09T14:42:00+09:00",
    "end": "2026-07-09T14:42:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:43:00+09:00",
    "start": "2026-07-09T14:43:00+09:00",
    "end": "2026-07-09T14:43:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:44:00+09:00",
    "start": "2026-07-09T14:44:00+09:00",
    "end": "2026-07-09T14:44:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:45:00+09:00",
    "start": "2026-07-09T14:45:00+09:00",
    "end": "2026-07-09T14:45:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:46:00+09:00",
    "start": "2026-07-09T14:46:00+09:00",
    "end": "2026-07-09T14:46:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:47:00+09:00",
    "start": "2026-07-09T14:47:00+09:00",
    "end": "2026-07-09T14:47:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:48:00+09:00",
    "start": "2026-07-09T14:48:00+09:00",
    "end": "2026-07-09T14:48:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:49:00+09:00",
    "start": "2026-07-09T14:49:00+09:00",
    "end": "2026-07-09T14:49:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:50:00+09:00",
    "start": "2026-07-09T14:50:00+09:00",
    "end": "2026-07-09T14:50:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:51:00+09:00",
    "start": "2026-07-09T14:51:00+09:00",
    "end": "2026-07-09T14:51:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:52:00+09:00",
    "start": "2026-07-09T14:52:00+09:00",
    "end": "2026-07-09T14:52:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:53:00+09:00",
    "start": "2026-07-09T14:53:00+09:00",
    "end": "2026-07-09T14:53:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:54:00+09:00",
    "start": "2026-07-09T14:54:00+09:00",
    "end": "2026-07-09T14:54:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:55:00+09:00",
    "start": "2026-07-09T14:55:00+09:00",
    "end": "2026-07-09T14:55:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:56:00+09:00",
    "start": "2026-07-09T14:56:00+09:00",
    "end": "2026-07-09T14:56:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:57:00+09:00",
    "start": "2026-07-09T14:57:00+09:00",
    "end": "2026-07-09T14:57:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:58:00+09:00",
    "start": "2026-07-09T14:58:00+09:00",
    "end": "2026-07-09T14:58:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T14:59:00+09:00",
    "start": "2026-07-09T14:59:00+09:00",
    "end": "2026-07-09T14:59:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:00:00+09:00",
    "start": "2026-07-09T15:00:00+09:00",
    "end": "2026-07-09T15:00:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:01:00+09:00",
    "start": "2026-07-09T15:01:00+09:00",
    "end": "2026-07-09T15:01:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:02:00+09:00",
    "start": "2026-07-09T15:02:00+09:00",
    "end": "2026-07-09T15:02:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:03:00+09:00",
    "start": "2026-07-09T15:03:00+09:00",
    "end": "2026-07-09T15:03:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:04:00+09:00",
    "start": "2026-07-09T15:04:00+09:00",
    "end": "2026-07-09T15:04:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:05:00+09:00",
    "start": "2026-07-09T15:05:00+09:00",
    "end": "2026-07-09T15:05:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:06:00+09:00",
    "start": "2026-07-09T15:06:00+09:00",
    "end": "2026-07-09T15:06:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:07:00+09:00",
    "start": "2026-07-09T15:07:00+09:00",
    "end": "2026-07-09T15:07:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:08:00+09:00",
    "start": "2026-07-09T15:08:00+09:00",
    "end": "2026-07-09T15:08:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:09:00+09:00",
    "start": "2026-07-09T15:09:00+09:00",
    "end": "2026-07-09T15:09:00+09:00",
    "total": 4,
    "counts": {
     "normal": 3,
     "suspect": 0,
     "bad": 0,
     "missing": 1,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:10:00+09:00",
    "start": "2026-07-09T15:10:00+09:00",
    "end": "2026-07-09T15:10:00+09:00",
    "total": 4,
    "counts": {
     "normal": 2,
     "suspect": 0,
     "bad": 1,
     "missing": 1,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:11:00+09:00",
    "start": "2026-07-09T15:11:00+09:00",
    "end": "2026-07-09T15:11:00+09:00",
    "total": 4,
    "counts": {
     "normal": 2,
     "suspect": 1,
     "bad": 0,
     "missing": 1,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:12:00+09:00",
    "start": "2026-07-09T15:12:00+09:00",
    "end": "2026-07-09T15:12:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:13:00+09:00",
    "start": "2026-07-09T15:13:00+09:00",
    "end": "2026-07-09T15:13:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:14:00+09:00",
    "start": "2026-07-09T15:14:00+09:00",
    "end": "2026-07-09T15:14:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:15:00+09:00",
    "start": "2026-07-09T15:15:00+09:00",
    "end": "2026-07-09T15:15:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:16:00+09:00",
    "start": "2026-07-09T15:16:00+09:00",
    "end": "2026-07-09T15:16:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:17:00+09:00",
    "start": "2026-07-09T15:17:00+09:00",
    "end": "2026-07-09T15:17:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:18:00+09:00",
    "start": "2026-07-09T15:18:00+09:00",
    "end": "2026-07-09T15:18:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:19:00+09:00",
    "start": "2026-07-09T15:19:00+09:00",
    "end": "2026-07-09T15:19:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:20:00+09:00",
    "start": "2026-07-09T15:20:00+09:00",
    "end": "2026-07-09T15:20:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:21:00+09:00",
    "start": "2026-07-09T15:21:00+09:00",
    "end": "2026-07-09T15:21:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:22:00+09:00",
    "start": "2026-07-09T15:22:00+09:00",
    "end": "2026-07-09T15:22:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:23:00+09:00",
    "start": "2026-07-09T15:23:00+09:00",
    "end": "2026-07-09T15:23:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:24:00+09:00",
    "start": "2026-07-09T15:24:00+09:00",
    "end": "2026-07-09T15:24:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:25:00+09:00",
    "start": "2026-07-09T15:25:00+09:00",
    "end": "2026-07-09T15:25:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:26:00+09:00",
    "start": "2026-07-09T15:26:00+09:00",
    "end": "2026-07-09T15:26:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:27:00+09:00",
    "start": "2026-07-09T15:27:00+09:00",
    "end": "2026-07-09T15:27:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:28:00+09:00",
    "start": "2026-07-09T15:28:00+09:00",
    "end": "2026-07-09T15:28:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:29:00+09:00",
    "start": "2026-07-09T15:29:00+09:00",
    "end": "2026-07-09T15:29:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:30:00+09:00",
    "start": "2026-07-09T15:30:00+09:00",
    "end": "2026-07-09T15:30:00+09:00",
    "total": 4,
    "counts": {
     "normal": 3,
     "suspect": 1,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:31:00+09:00",
    "start": "2026-07-09T15:31:00+09:00",
    "end": "2026-07-09T15:31:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:32:00+09:00",
    "start": "2026-07-09T15:32:00+09:00",
    "end": "2026-07-09T15:32:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:33:00+09:00",
    "start": "2026-07-09T15:33:00+09:00",
    "end": "2026-07-09T15:33:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:34:00+09:00",
    "start": "2026-07-09T15:34:00+09:00",
    "end": "2026-07-09T15:34:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:35:00+09:00",
    "start": "2026-07-09T15:35:00+09:00",
    "end": "2026-07-09T15:35:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:36:00+09:00",
    "start": "2026-07-09T15:36:00+09:00",
    "end": "2026-07-09T15:36:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:37:00+09:00",
    "start": "2026-07-09T15:37:00+09:00",
    "end": "2026-07-09T15:37:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:38:00+09:00",
    "start": "2026-07-09T15:38:00+09:00",
    "end": "2026-07-09T15:38:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:39:00+09:00",
    "start": "2026-07-09T15:39:00+09:00",
    "end": "2026-07-09T15:39:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "bucket": "2026-07-09T15:40:00+09:00",
    "start": "2026-07-09T15:40:00+09:00",
    "end": "2026-07-09T15:40:00+09:00",
    "total": 4,
    "counts": {
     "normal": 4,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   }
  ],
  "rule_qc_counts": {
   "catalog_count": 12,
   "result_count": 2928,
   "items": [
    {
     "rule_id": "WT",
     "rule_name": "시간 검사",
     "evaluated_count": 241,
     "anomaly_count": 0,
     "not_evaluated_count": 3,
     "full_test_evaluated_count": 241,
     "missing_precheck_count": 0,
     "sample_configured": true,
     "state": "EVALUATED"
    },
    {
     "rule_id": "LO",
     "rule_name": "위치 검사",
     "evaluated_count": 0,
     "anomaly_count": 0,
     "not_evaluated_count": 244,
     "full_test_evaluated_count": 0,
     "missing_precheck_count": 0,
     "sample_configured": false,
     "state": "NOT_EVALUATED"
    },
    {
     "rule_id": "ER",
     "rule_name": "오류값 검사",
     "evaluated_count": 244,
     "anomaly_count": 3,
     "not_evaluated_count": 0,
     "full_test_evaluated_count": 241,
     "missing_precheck_count": 3,
     "sample_configured": true,
     "state": "EVALUATED"
    },
    {
     "rule_id": "GR",
     "rule_name": "전지구적 한계 검사",
     "evaluated_count": 244,
     "anomaly_count": 4,
     "not_evaluated_count": 0,
     "full_test_evaluated_count": 241,
     "missing_precheck_count": 3,
     "sample_configured": true,
     "state": "EVALUATED"
    },
    {
     "rule_id": "GD",
     "rule_name": "고정값 검사",
     "evaluated_count": 234,
     "anomaly_count": 3,
     "not_evaluated_count": 10,
     "full_test_evaluated_count": 231,
     "missing_precheck_count": 3,
     "sample_configured": true,
     "state": "EVALUATED"
    },
    {
     "rule_id": "RL",
     "rule_name": "내적일치성 검사",
     "evaluated_count": 0,
     "anomaly_count": 0,
     "not_evaluated_count": 244,
     "full_test_evaluated_count": 0,
     "missing_precheck_count": 0,
     "sample_configured": false,
     "state": "NOT_EVALUATED"
    },
    {
     "rule_id": "SP",
     "rule_name": "튐값 검사",
     "evaluated_count": 239,
     "anomaly_count": 5,
     "not_evaluated_count": 5,
     "full_test_evaluated_count": 236,
     "missing_precheck_count": 3,
     "sample_configured": true,
     "state": "EVALUATED"
    },
    {
     "rule_id": "RR",
     "rule_name": "지역적 한계 검사",
     "evaluated_count": 3,
     "anomaly_count": 3,
     "not_evaluated_count": 241,
     "full_test_evaluated_count": 0,
     "missing_precheck_count": 3,
     "sample_configured": false,
     "state": "EVALUATED"
    },
    {
     "rule_id": "SR",
     "rule_name": "계절적 한계 검사",
     "evaluated_count": 3,
     "anomaly_count": 3,
     "not_evaluated_count": 241,
     "full_test_evaluated_count": 0,
     "missing_precheck_count": 3,
     "sample_configured": false,
     "state": "EVALUATED"
    },
    {
     "rule_id": "ST",
     "rule_name": "통계 검사",
     "evaluated_count": 3,
     "anomaly_count": 3,
     "not_evaluated_count": 241,
     "full_test_evaluated_count": 0,
     "missing_precheck_count": 3,
     "sample_configured": false,
     "state": "EVALUATED"
    },
    {
     "rule_id": "DE",
     "rule_name": "지연시간 검사",
     "evaluated_count": 241,
     "anomaly_count": 1,
     "not_evaluated_count": 3,
     "full_test_evaluated_count": 241,
     "missing_precheck_count": 0,
     "sample_configured": true,
     "state": "EVALUATED"
    },
    {
     "rule_id": "PO",
     "rule_name": "전원 검사",
     "evaluated_count": 0,
     "anomaly_count": 0,
     "not_evaluated_count": 244,
     "full_test_evaluated_count": 0,
     "missing_precheck_count": 0,
     "sample_configured": false,
     "state": "NOT_EVALUATED"
    }
   ]
  },
  "station_variable_matrix": [
   {
    "station_id": "SAMPLE-NORMAL",
    "station_name": "샘플 정상 관측소",
    "variable_code": "WATER_TEMP",
    "label": "정상",
    "total": 61,
    "counts": {
     "normal": 61,
     "suspect": 0,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "station_id": "SAMPLE-LATE",
    "station_name": "샘플 수신 지연 관측소",
    "variable_code": "WATER_TEMP",
    "label": "수신 지연",
    "total": 61,
    "counts": {
     "normal": 60,
     "suspect": 1,
     "bad": 0,
     "missing": 0,
     "unknown": 0
    }
   },
   {
    "station_id": "SAMPLE-MISSING",
    "station_name": "샘플 결측 관측소",
    "variable_code": "WATER_TEMP",
    "label": "결측",
    "total": 61,
    "counts": {
     "normal": 58,
     "suspect": 0,
     "bad": 0,
     "missing": 3,
     "unknown": 0
    }
   },
   {
    "station_id": "SAMPLE-SPIKE",
    "station_name": "샘플 Spike · 범위 초과 관측소",
    "variable_code": "WATER_TEMP",
    "label": "Spike · 범위 초과",
    "total": 61,
    "counts": {
     "normal": 59,
     "suspect": 1,
     "bad": 1,
     "missing": 0,
     "unknown": 0
    }
   }
  ],
  "cases": [
   {
    "case_id": "sample-normal-g1",
    "scenario_id": "normal",
    "label": "정상",
    "description": "명시된 가상 단위·센서·간격으로 정상 범위를 검증합니다.",
    "station_id": "SAMPLE-NORMAL",
    "station_name": "샘플 정상 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:30:00+09:00",
    "value": 19.750002,
    "flag": "1",
    "meaning": "GOOD",
    "rule_ids": [],
    "delay_seconds": 1,
    "is_missing": false,
    "revision": 1,
    "recommendation_sha256": "f701308cb48da66453604c5454a433d9800995a8d7870211ae1b645ff64e72de",
    "review_status": "PENDING"
   },
   {
    "case_id": "sample-late-g1",
    "scenario_id": "late",
    "label": "수신 지연",
    "description": "선택 관측값이 8분 늦게 수신되어 DE Rule을 초과합니다.",
    "station_id": "SAMPLE-LATE",
    "station_name": "샘플 수신 지연 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:30:00+09:00",
    "value": 19.750002,
    "flag": "3",
    "meaning": "SUSPECT",
    "rule_ids": [
     "DE"
    ],
    "delay_seconds": 480,
    "is_missing": false,
    "revision": 1,
    "recommendation_sha256": "4c9e2773bd9d2147474875a592787e8b4ab79448a6466babb314059faf2937fa",
    "review_status": "PENDING"
   },
   {
    "case_id": "sample-missing-g1",
    "scenario_id": "missing",
    "label": "결측",
    "description": "3개 예정 슬롯이 수신되지 않았습니다. 보간 없이 null로 표시합니다.",
    "station_id": "SAMPLE-MISSING",
    "station_name": "샘플 결측 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:10:00+09:00",
    "value": null,
    "flag": "9",
    "meaning": "MISSING",
    "rule_ids": [
     "ER",
     "GR",
     "GD",
     "SP",
     "RR",
     "SR",
     "ST"
    ],
    "delay_seconds": null,
    "is_missing": true,
    "revision": 1,
    "recommendation_sha256": "8859224fe03ecd8ef3f4c82ae40aa521359c2e6289a0d0f3ea8c02c9d044e56e",
    "review_status": "PENDING"
   },
   {
    "case_id": "sample-spike-g1",
    "scenario_id": "spike",
    "label": "Spike · 범위 초과",
    "description": "가상 수온 45도로 급변하여 SP 주의와 GR 범위 초과 BAD가 함께 계산됩니다.",
    "station_id": "SAMPLE-SPIKE",
    "station_name": "샘플 Spike · 범위 초과 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:10:00+09:00",
    "value": 45,
    "flag": "4",
    "meaning": "BAD",
    "rule_ids": [
     "GR",
     "SP"
    ],
    "delay_seconds": 1,
    "is_missing": false,
    "revision": 1,
    "recommendation_sha256": "b6365ae1ebf34328a58c678ce58d4c9ea8c40d040f68c5a8d6c194a2d29d16c2",
    "review_status": "PENDING"
   }
  ],
  "review_queue": {
   "rows": [
    {
     "case_id": "sample-normal-g1",
     "scenario_id": "normal",
     "label": "정상",
     "description": "명시된 가상 단위·센서·간격으로 정상 범위를 검증합니다.",
     "station_id": "SAMPLE-NORMAL",
     "station_name": "샘플 정상 관측소",
     "variable_code": "WATER_TEMP",
     "unit": "degree_C",
     "observation_time": "2026-07-09T15:30:00+09:00",
     "value": 19.750002,
     "flag": "1",
     "meaning": "GOOD",
     "rule_ids": [],
     "delay_seconds": 1,
     "is_missing": false,
     "revision": 1,
     "recommendation_sha256": "f701308cb48da66453604c5454a433d9800995a8d7870211ae1b645ff64e72de",
     "review_status": "PENDING"
    },
    {
     "case_id": "sample-late-g1",
     "scenario_id": "late",
     "label": "수신 지연",
     "description": "선택 관측값이 8분 늦게 수신되어 DE Rule을 초과합니다.",
     "station_id": "SAMPLE-LATE",
     "station_name": "샘플 수신 지연 관측소",
     "variable_code": "WATER_TEMP",
     "unit": "degree_C",
     "observation_time": "2026-07-09T15:30:00+09:00",
     "value": 19.750002,
     "flag": "3",
     "meaning": "SUSPECT",
     "rule_ids": [
      "DE"
     ],
     "delay_seconds": 480,
     "is_missing": false,
     "revision": 1,
     "recommendation_sha256": "4c9e2773bd9d2147474875a592787e8b4ab79448a6466babb314059faf2937fa",
     "review_status": "PENDING"
    },
    {
     "case_id": "sample-missing-g1",
     "scenario_id": "missing",
     "label": "결측",
     "description": "3개 예정 슬롯이 수신되지 않았습니다. 보간 없이 null로 표시합니다.",
     "station_id": "SAMPLE-MISSING",
     "station_name": "샘플 결측 관측소",
     "variable_code": "WATER_TEMP",
     "unit": "degree_C",
     "observation_time": "2026-07-09T15:10:00+09:00",
     "value": null,
     "flag": "9",
     "meaning": "MISSING",
     "rule_ids": [
      "ER",
      "GR",
      "GD",
      "SP",
      "RR",
      "SR",
      "ST"
     ],
     "delay_seconds": null,
     "is_missing": true,
     "revision": 1,
     "recommendation_sha256": "8859224fe03ecd8ef3f4c82ae40aa521359c2e6289a0d0f3ea8c02c9d044e56e",
     "review_status": "PENDING"
    },
    {
     "case_id": "sample-spike-g1",
     "scenario_id": "spike",
     "label": "Spike · 범위 초과",
     "description": "가상 수온 45도로 급변하여 SP 주의와 GR 범위 초과 BAD가 함께 계산됩니다.",
     "station_id": "SAMPLE-SPIKE",
     "station_name": "샘플 Spike · 범위 초과 관측소",
     "variable_code": "WATER_TEMP",
     "unit": "degree_C",
     "observation_time": "2026-07-09T15:10:00+09:00",
     "value": 45,
     "flag": "4",
     "meaning": "BAD",
     "rule_ids": [
      "GR",
      "SP"
     ],
     "delay_seconds": 1,
     "is_missing": false,
     "revision": 1,
     "recommendation_sha256": "b6365ae1ebf34328a58c678ce58d4c9ea8c40d040f68c5a8d6c194a2d29d16c2",
     "review_status": "PENDING"
    }
   ],
   "total": 4
  },
  "session_history": [
   {
    "sequence": 1,
    "action": "CREATE_SESSION",
    "generation": 1,
    "session_revision": 1,
    "sample_clock": "2026-07-09T15:41:20+09:00",
    "actor": "SAMPLE_ENGINE"
   }
  ],
  "states": {
   "ai": "NOT_RUN",
   "model": "NO_MODEL",
   "approval": "SAMPLE_ONLY"
  },
  "provenance": {
   "source": "SAMPLE",
   "is_sample": true,
   "approved": false,
   "transient": true,
   "production_writes": 0,
   "operational_writes": 0,
   "source_reads": 0,
   "model_training": 0,
   "final_qc_writes": 0,
   "restart_erases_state": true,
   "rule_engine_version": "guide-existing-12-v1",
   "rule_implementation_sha256": "9993072a38e264808c828a93a460908bef59a6e9e8d58cdc11198425eef2ff51",
   "sample_definition_version": "QC_SAMPLE_SYNTHETIC_V1",
   "sample_definition_sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
   "rule_catalog_sha256": "7d30ad39f1ff40bbfb2224866f869ffd53782e958a94f3e71bf767b35e8d4889",
   "clock_warning": "명시된 가상 +09:00 시각이며 실제 원천의 시간대를 확정하지 않습니다.",
   "missing_policy": "EXPLICIT_SYNTHETIC_SENTINEL_FOR_ABSENT_SLOT; DISPLAY_NULL; NO_INTERPOLATION",
   "ai_status": "NOT_RUN",
   "rule_authority": "CONDITIONAL_SYNTHETIC_CONFIGURATION_NOT_SOURCE_APPROVAL"
  },
  "result_sha256": "f3ba044112cb1dfc236dd33d9e587c3aca117738a468f5eea3439eff32a9f1b5"
 },
 "details": {
  "normal": {
   "schema_version": "qc-sample-detail-1",
   "source": "SAMPLE",
   "is_sample": true,
   "approved": false,
   "transient": true,
   "production_writes": 0,
   "operational_writes": 0,
   "source_reads": 0,
   "model_training": 0,
   "final_qc_writes": 0,
   "restart_erases_state": true,
   "session_id": "qc-sample-session-3wGQD9JJxaHlbO3yZ5YbHS1x",
   "session_revision": 1,
   "generation": 1,
   "window": {
    "source": "SAMPLE",
    "start": "2026-07-09T14:40:00+09:00",
    "end": "2026-07-09T15:40:00+09:00",
    "as_of": "2026-07-09T15:41:20+09:00",
    "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
    "offset": "+09:00",
    "granularity": "minute",
    "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
   },
   "case": {
    "case_id": "sample-normal-g1",
    "scenario_id": "normal",
    "label": "정상",
    "description": "명시된 가상 단위·센서·간격으로 정상 범위를 검증합니다.",
    "station_id": "SAMPLE-NORMAL",
    "station_name": "샘플 정상 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:30:00+09:00",
    "value": 19.750002,
    "flag": "1",
    "meaning": "GOOD",
    "rule_ids": [],
    "delay_seconds": 1,
    "is_missing": false,
    "revision": 1,
    "recommendation_sha256": "f701308cb48da66453604c5454a433d9800995a8d7870211ae1b645ff64e72de",
    "review_status": "PENDING"
   },
   "revision": 1,
   "recommendation_sha256": "f701308cb48da66453604c5454a433d9800995a8d7870211ae1b645ff64e72de",
   "series": {
    "rows": [
     {
      "observation_id": "SAMPLE:normal:0",
      "observation_time": "2026-07-09T14:40:00+09:00",
      "value": 20,
      "rule_input_value": 20,
      "source_literal": "20.0",
      "received_time": "2026-07-09T14:40:01+09:00",
      "available_at": "2026-07-09T14:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:1",
      "observation_time": "2026-07-09T14:41:00+09:00",
      "value": 20.054557,
      "rule_input_value": 20.054557,
      "source_literal": "20.054557",
      "received_time": "2026-07-09T14:41:01+09:00",
      "available_at": "2026-07-09T14:41:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:2",
      "observation_time": "2026-07-09T14:42:00+09:00",
      "value": 20.106485,
      "rule_input_value": 20.106485,
      "source_literal": "20.106485",
      "received_time": "2026-07-09T14:42:01+09:00",
      "available_at": "2026-07-09T14:42:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:3",
      "observation_time": "2026-07-09T14:43:00+09:00",
      "value": 20.153279,
      "rule_input_value": 20.153279,
      "source_literal": "20.153279",
      "received_time": "2026-07-09T14:43:01+09:00",
      "available_at": "2026-07-09T14:43:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:4",
      "observation_time": "2026-07-09T14:44:00+09:00",
      "value": 20.192685,
      "rule_input_value": 20.192685,
      "source_literal": "20.192685",
      "received_time": "2026-07-09T14:44:01+09:00",
      "available_at": "2026-07-09T14:44:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:5",
      "observation_time": "2026-07-09T14:45:00+09:00",
      "value": 20.222802,
      "rule_input_value": 20.222802,
      "source_literal": "20.222802",
      "received_time": "2026-07-09T14:45:01+09:00",
      "available_at": "2026-07-09T14:45:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:6",
      "observation_time": "2026-07-09T14:46:00+09:00",
      "value": 20.242179,
      "rule_input_value": 20.242179,
      "source_literal": "20.242179",
      "received_time": "2026-07-09T14:46:01+09:00",
      "available_at": "2026-07-09T14:46:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:7",
      "observation_time": "2026-07-09T14:47:00+09:00",
      "value": 20.249881,
      "rule_input_value": 20.249881,
      "source_literal": "20.249881",
      "received_time": "2026-07-09T14:47:01+09:00",
      "available_at": "2026-07-09T14:47:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:8",
      "observation_time": "2026-07-09T14:48:00+09:00",
      "value": 20.245539,
      "rule_input_value": 20.245539,
      "source_literal": "20.245539",
      "received_time": "2026-07-09T14:48:01+09:00",
      "available_at": "2026-07-09T14:48:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:9",
      "observation_time": "2026-07-09T14:49:00+09:00",
      "value": 20.229359,
      "rule_input_value": 20.229359,
      "source_literal": "20.229359",
      "received_time": "2026-07-09T14:49:01+09:00",
      "available_at": "2026-07-09T14:49:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:10",
      "observation_time": "2026-07-09T14:50:00+09:00",
      "value": 20.202124,
      "rule_input_value": 20.202124,
      "source_literal": "20.202124",
      "received_time": "2026-07-09T14:50:01+09:00",
      "available_at": "2026-07-09T14:50:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:11",
      "observation_time": "2026-07-09T14:51:00+09:00",
      "value": 20.165145,
      "rule_input_value": 20.165145,
      "source_literal": "20.165145",
      "received_time": "2026-07-09T14:51:01+09:00",
      "available_at": "2026-07-09T14:51:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:12",
      "observation_time": "2026-07-09T14:52:00+09:00",
      "value": 20.120206,
      "rule_input_value": 20.120206,
      "source_literal": "20.120206",
      "received_time": "2026-07-09T14:52:01+09:00",
      "available_at": "2026-07-09T14:52:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:13",
      "observation_time": "2026-07-09T14:53:00+09:00",
      "value": 20.069471,
      "rule_input_value": 20.069471,
      "source_literal": "20.069471",
      "received_time": "2026-07-09T14:53:01+09:00",
      "available_at": "2026-07-09T14:53:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:14",
      "observation_time": "2026-07-09T14:54:00+09:00",
      "value": 20.015388,
      "rule_input_value": 20.015388,
      "source_literal": "20.015388",
      "received_time": "2026-07-09T14:54:01+09:00",
      "available_at": "2026-07-09T14:54:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:15",
      "observation_time": "2026-07-09T14:55:00+09:00",
      "value": 19.960564,
      "rule_input_value": 19.960564,
      "source_literal": "19.960564",
      "received_time": "2026-07-09T14:55:01+09:00",
      "available_at": "2026-07-09T14:55:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:16",
      "observation_time": "2026-07-09T14:56:00+09:00",
      "value": 19.90764,
      "rule_input_value": 19.90764,
      "source_literal": "19.90764",
      "received_time": "2026-07-09T14:56:01+09:00",
      "available_at": "2026-07-09T14:56:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:17",
      "observation_time": "2026-07-09T14:57:00+09:00",
      "value": 19.859168,
      "rule_input_value": 19.859168,
      "source_literal": "19.859168",
      "received_time": "2026-07-09T14:57:01+09:00",
      "available_at": "2026-07-09T14:57:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:18",
      "observation_time": "2026-07-09T14:58:00+09:00",
      "value": 19.817485,
      "rule_input_value": 19.817485,
      "source_literal": "19.817485",
      "received_time": "2026-07-09T14:58:01+09:00",
      "available_at": "2026-07-09T14:58:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:19",
      "observation_time": "2026-07-09T14:59:00+09:00",
      "value": 19.784601,
      "rule_input_value": 19.784601,
      "source_literal": "19.784601",
      "received_time": "2026-07-09T14:59:01+09:00",
      "available_at": "2026-07-09T14:59:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:20",
      "observation_time": "2026-07-09T15:00:00+09:00",
      "value": 19.762099,
      "rule_input_value": 19.762099,
      "source_literal": "19.762099",
      "received_time": "2026-07-09T15:00:01+09:00",
      "available_at": "2026-07-09T15:00:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:21",
      "observation_time": "2026-07-09T15:01:00+09:00",
      "value": 19.751066,
      "rule_input_value": 19.751066,
      "source_literal": "19.751066",
      "received_time": "2026-07-09T15:01:01+09:00",
      "available_at": "2026-07-09T15:01:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:22",
      "observation_time": "2026-07-09T15:02:00+09:00",
      "value": 19.752033,
      "rule_input_value": 19.752033,
      "source_literal": "19.752033",
      "received_time": "2026-07-09T15:02:01+09:00",
      "available_at": "2026-07-09T15:02:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:23",
      "observation_time": "2026-07-09T15:03:00+09:00",
      "value": 19.764953,
      "rule_input_value": 19.764953,
      "source_literal": "19.764953",
      "received_time": "2026-07-09T15:03:01+09:00",
      "available_at": "2026-07-09T15:03:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:24",
      "observation_time": "2026-07-09T15:04:00+09:00",
      "value": 19.789203,
      "rule_input_value": 19.789203,
      "source_literal": "19.789203",
      "received_time": "2026-07-09T15:04:01+09:00",
      "available_at": "2026-07-09T15:04:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:25",
      "observation_time": "2026-07-09T15:05:00+09:00",
      "value": 19.823615,
      "rule_input_value": 19.823615,
      "source_literal": "19.823615",
      "received_time": "2026-07-09T15:05:01+09:00",
      "available_at": "2026-07-09T15:05:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:26",
      "observation_time": "2026-07-09T15:06:00+09:00",
      "value": 19.866529,
      "rule_input_value": 19.866529,
      "source_literal": "19.866529",
      "received_time": "2026-07-09T15:06:01+09:00",
      "available_at": "2026-07-09T15:06:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:27",
      "observation_time": "2026-07-09T15:07:00+09:00",
      "value": 19.915878,
      "rule_input_value": 19.915878,
      "source_literal": "19.915878",
      "received_time": "2026-07-09T15:07:01+09:00",
      "available_at": "2026-07-09T15:07:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:28",
      "observation_time": "2026-07-09T15:08:00+09:00",
      "value": 19.969282,
      "rule_input_value": 19.969282,
      "source_literal": "19.969282",
      "received_time": "2026-07-09T15:08:01+09:00",
      "available_at": "2026-07-09T15:08:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:29",
      "observation_time": "2026-07-09T15:09:00+09:00",
      "value": 20.024166,
      "rule_input_value": 20.024166,
      "source_literal": "20.024166",
      "received_time": "2026-07-09T15:09:01+09:00",
      "available_at": "2026-07-09T15:09:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:30",
      "observation_time": "2026-07-09T15:10:00+09:00",
      "value": 20.077885,
      "rule_input_value": 20.077885,
      "source_literal": "20.077885",
      "received_time": "2026-07-09T15:10:01+09:00",
      "available_at": "2026-07-09T15:10:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:31",
      "observation_time": "2026-07-09T15:11:00+09:00",
      "value": 20.12785,
      "rule_input_value": 20.12785,
      "source_literal": "20.12785",
      "received_time": "2026-07-09T15:11:01+09:00",
      "available_at": "2026-07-09T15:11:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:32",
      "observation_time": "2026-07-09T15:12:00+09:00",
      "value": 20.171652,
      "rule_input_value": 20.171652,
      "source_literal": "20.171652",
      "received_time": "2026-07-09T15:12:01+09:00",
      "available_at": "2026-07-09T15:12:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:33",
      "observation_time": "2026-07-09T15:13:00+09:00",
      "value": 20.20718,
      "rule_input_value": 20.20718,
      "source_literal": "20.20718",
      "received_time": "2026-07-09T15:13:01+09:00",
      "available_at": "2026-07-09T15:13:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:34",
      "observation_time": "2026-07-09T15:14:00+09:00",
      "value": 20.23272,
      "rule_input_value": 20.23272,
      "source_literal": "20.23272",
      "received_time": "2026-07-09T15:14:01+09:00",
      "available_at": "2026-07-09T15:14:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:35",
      "observation_time": "2026-07-09T15:15:00+09:00",
      "value": 20.247042,
      "rule_input_value": 20.247042,
      "source_literal": "20.247042",
      "received_time": "2026-07-09T15:15:01+09:00",
      "available_at": "2026-07-09T15:15:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:36",
      "observation_time": "2026-07-09T15:16:00+09:00",
      "value": 20.249455,
      "rule_input_value": 20.249455,
      "source_literal": "20.249455",
      "received_time": "2026-07-09T15:16:01+09:00",
      "available_at": "2026-07-09T15:16:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:37",
      "observation_time": "2026-07-09T15:17:00+09:00",
      "value": 20.239844,
      "rule_input_value": 20.239844,
      "source_literal": "20.239844",
      "received_time": "2026-07-09T15:17:01+09:00",
      "available_at": "2026-07-09T15:17:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:38",
      "observation_time": "2026-07-09T15:18:00+09:00",
      "value": 20.21867,
      "rule_input_value": 20.21867,
      "source_literal": "20.21867",
      "received_time": "2026-07-09T15:18:01+09:00",
      "available_at": "2026-07-09T15:18:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:39",
      "observation_time": "2026-07-09T15:19:00+09:00",
      "value": 20.186956,
      "rule_input_value": 20.186956,
      "source_literal": "20.186956",
      "received_time": "2026-07-09T15:19:01+09:00",
      "available_at": "2026-07-09T15:19:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:40",
      "observation_time": "2026-07-09T15:20:00+09:00",
      "value": 20.146229,
      "rule_input_value": 20.146229,
      "source_literal": "20.146229",
      "received_time": "2026-07-09T15:20:01+09:00",
      "available_at": "2026-07-09T15:20:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:41",
      "observation_time": "2026-07-09T15:21:00+09:00",
      "value": 20.098454,
      "rule_input_value": 20.098454,
      "source_literal": "20.098454",
      "received_time": "2026-07-09T15:21:01+09:00",
      "available_at": "2026-07-09T15:21:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:42",
      "observation_time": "2026-07-09T15:22:00+09:00",
      "value": 20.045932,
      "rule_input_value": 20.045932,
      "source_literal": "20.045932",
      "received_time": "2026-07-09T15:22:01+09:00",
      "available_at": "2026-07-09T15:22:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:43",
      "observation_time": "2026-07-09T15:23:00+09:00",
      "value": 19.991196,
      "rule_input_value": 19.991196,
      "source_literal": "19.991196",
      "received_time": "2026-07-09T15:23:01+09:00",
      "available_at": "2026-07-09T15:23:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:44",
      "observation_time": "2026-07-09T15:24:00+09:00",
      "value": 19.936885,
      "rule_input_value": 19.936885,
      "source_literal": "19.936885",
      "received_time": "2026-07-09T15:24:01+09:00",
      "available_at": "2026-07-09T15:24:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:45",
      "observation_time": "2026-07-09T15:25:00+09:00",
      "value": 19.885616,
      "rule_input_value": 19.885616,
      "source_literal": "19.885616",
      "received_time": "2026-07-09T15:25:01+09:00",
      "available_at": "2026-07-09T15:25:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:46",
      "observation_time": "2026-07-09T15:26:00+09:00",
      "value": 19.839861,
      "rule_input_value": 19.839861,
      "source_literal": "19.839861",
      "received_time": "2026-07-09T15:26:01+09:00",
      "available_at": "2026-07-09T15:26:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:47",
      "observation_time": "2026-07-09T15:27:00+09:00",
      "value": 19.801826,
      "rule_input_value": 19.801826,
      "source_literal": "19.801826",
      "received_time": "2026-07-09T15:27:01+09:00",
      "available_at": "2026-07-09T15:27:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:48",
      "observation_time": "2026-07-09T15:28:00+09:00",
      "value": 19.773343,
      "rule_input_value": 19.773343,
      "source_literal": "19.773343",
      "received_time": "2026-07-09T15:28:01+09:00",
      "available_at": "2026-07-09T15:28:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:49",
      "observation_time": "2026-07-09T15:29:00+09:00",
      "value": 19.755787,
      "rule_input_value": 19.755787,
      "source_literal": "19.755787",
      "received_time": "2026-07-09T15:29:01+09:00",
      "available_at": "2026-07-09T15:29:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:50",
      "observation_time": "2026-07-09T15:30:00+09:00",
      "value": 19.750002,
      "rule_input_value": 19.750002,
      "source_literal": "19.750002",
      "received_time": "2026-07-09T15:30:01+09:00",
      "available_at": "2026-07-09T15:30:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:51",
      "observation_time": "2026-07-09T15:31:00+09:00",
      "value": 19.756269,
      "rule_input_value": 19.756269,
      "source_literal": "19.756269",
      "received_time": "2026-07-09T15:31:01+09:00",
      "available_at": "2026-07-09T15:31:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:52",
      "observation_time": "2026-07-09T15:32:00+09:00",
      "value": 19.774286,
      "rule_input_value": 19.774286,
      "source_literal": "19.774286",
      "received_time": "2026-07-09T15:32:01+09:00",
      "available_at": "2026-07-09T15:32:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:53",
      "observation_time": "2026-07-09T15:33:00+09:00",
      "value": 19.803182,
      "rule_input_value": 19.803182,
      "source_literal": "19.803182",
      "received_time": "2026-07-09T15:33:01+09:00",
      "available_at": "2026-07-09T15:33:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:54",
      "observation_time": "2026-07-09T15:34:00+09:00",
      "value": 19.841567,
      "rule_input_value": 19.841567,
      "source_literal": "19.841567",
      "received_time": "2026-07-09T15:34:01+09:00",
      "available_at": "2026-07-09T15:34:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:55",
      "observation_time": "2026-07-09T15:35:00+09:00",
      "value": 19.887588,
      "rule_input_value": 19.887588,
      "source_literal": "19.887588",
      "received_time": "2026-07-09T15:35:01+09:00",
      "available_at": "2026-07-09T15:35:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:56",
      "observation_time": "2026-07-09T15:36:00+09:00",
      "value": 19.939029,
      "rule_input_value": 19.939029,
      "source_literal": "19.939029",
      "received_time": "2026-07-09T15:36:01+09:00",
      "available_at": "2026-07-09T15:36:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:57",
      "observation_time": "2026-07-09T15:37:00+09:00",
      "value": 19.993408,
      "rule_input_value": 19.993408,
      "source_literal": "19.993408",
      "received_time": "2026-07-09T15:37:01+09:00",
      "available_at": "2026-07-09T15:37:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:58",
      "observation_time": "2026-07-09T15:38:00+09:00",
      "value": 20.048105,
      "rule_input_value": 20.048105,
      "source_literal": "20.048105",
      "received_time": "2026-07-09T15:38:01+09:00",
      "available_at": "2026-07-09T15:38:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:59",
      "observation_time": "2026-07-09T15:39:00+09:00",
      "value": 20.100484,
      "rule_input_value": 20.100484,
      "source_literal": "20.100484",
      "received_time": "2026-07-09T15:39:01+09:00",
      "available_at": "2026-07-09T15:39:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:normal:60",
      "observation_time": "2026-07-09T15:40:00+09:00",
      "value": 20.148018,
      "rule_input_value": 20.148018,
      "source_literal": "20.148018",
      "received_time": "2026-07-09T15:40:01+09:00",
      "available_at": "2026-07-09T15:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     }
    ],
    "unit": "degree_C",
    "cadence_seconds": 60,
    "planned_slots": 61,
    "received_slots": 61,
    "missing_slots": 0,
    "interpolated": false
   },
   "rules": [
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "LOCATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 40,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 120,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "NOT_APPLICABLE_IN_TABLE_2_9",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 1,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 300,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:normal:50",
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "scope": {
      "station_id": "SAMPLE-NORMAL",
      "sensor_id": "SAMPLE-NORMAL-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-NORMAL-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "RELATED_OBSERVATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    }
   ],
   "rule_specs": [
    {
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "sentinels": [
       -999
      ]
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "min": 0,
      "max": 40,
      "boundary": "CLOSED"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "duration_seconds": 120,
      "interval_seconds": 60,
      "duration_boundary": "AT_LEAST"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "interval_seconds": 60,
      "max_delta": 1,
      "difference": "LINEAR"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "max_delay_seconds": 300
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    }
   ],
   "equipment": {
    "source": "SAMPLE",
    "synthetic": true,
    "station_id": "SAMPLE-NORMAL",
    "physical_sensor_id": "SAMPLE-NORMAL-SENSOR",
    "sensor_episode_id": "SAMPLE-NORMAL-EPISODE",
    "label": "가상 수온 센서",
    "unit": "degree_C"
   },
   "source_facts": {
    "physical_sensor_id": "SAMPLE-NORMAL-SENSOR",
    "sensor_episode_id": "SAMPLE-NORMAL-EPISODE",
    "quantity_kind": "WATER_TEMP_SCALAR",
    "clock_semantics": "EXPLICIT_SYNTHETIC_OFFSET",
    "source_timezone_name": "Etc/GMT-9",
    "effective_start": "2026-07-09T13:40:00+09:00",
    "effective_end": "2026-07-09T16:40:00+09:00",
    "available_at": "2026-07-09T14:39:00+09:00",
    "version_available_at": "2026-07-09T14:39:00+09:00",
    "evidence": {
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
    }
   },
   "evidence": [
    {
     "kind": "SYNTHETIC_SOURCE_CONTRACT",
     "source": "SAMPLE",
     "label": "명시된 가상 원천·센서 계약",
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "description": "실제 원천·계정·승인과 관계없는 고정 샘플 정의입니다."
    },
    {
     "kind": "ACTUAL_RULE_EXECUTION",
     "source": "SAMPLE",
     "label": "기존 Rule 엔진 계산 결과",
     "sha256": "367cf976b808c69c5b2dceb11d6d9a08981c380764f6c7bfaecb398ba1ff5e5d",
     "description": "WT/ER/GR/GD/SP/DE는 가상 설정으로 계산합니다. 다른 Rule의 관련·과거 근거는 제공하지 않았으며, 결측 sentinel 선행 검사 9는 과거 baseline 검사 완료를 뜻하지 않습니다."
    }
   ],
   "ai": {
    "status": "NOT_RUN",
    "trained_model": false,
    "result": null
   },
   "workflow": {
    "status": "PENDING",
    "blocked": true,
    "downstream_executed": false,
    "approved": false,
    "definitive_qc": false,
    "history": [
     {
      "sequence": 1,
      "action": "CREATE",
      "from_state": null,
      "to_state": "PENDING",
      "comment": "샘플 검토가 필요하여 후속 단계에서 정지했습니다.",
      "actor": "SAMPLE_ENGINE",
      "sample_clock": "2026-07-09T15:41:20+09:00"
     }
    ],
    "revision": 1,
    "recommendation_sha256": "f701308cb48da66453604c5454a433d9800995a8d7870211ae1b645ff64e72de",
    "capabilities": {
     "comment": true,
     "approve": true,
     "hold": true,
     "reject": true,
     "resume": false
    }
   },
   "provenance": {
    "source": "SAMPLE",
    "is_sample": true,
    "approved": false,
    "transient": true,
    "production_writes": 0,
    "operational_writes": 0,
    "source_reads": 0,
    "model_training": 0,
    "final_qc_writes": 0,
    "restart_erases_state": true,
    "rule_engine_version": "guide-existing-12-v1",
    "rule_implementation_sha256": "9993072a38e264808c828a93a460908bef59a6e9e8d58cdc11198425eef2ff51",
    "sample_definition_version": "QC_SAMPLE_SYNTHETIC_V1",
    "sample_definition_sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
    "rule_catalog_sha256": "7d30ad39f1ff40bbfb2224866f869ffd53782e958a94f3e71bf767b35e8d4889",
    "clock_warning": "명시된 가상 +09:00 시각이며 실제 원천의 시간대를 확정하지 않습니다.",
    "missing_policy": "EXPLICIT_SYNTHETIC_SENTINEL_FOR_ABSENT_SLOT; DISPLAY_NULL; NO_INTERPOLATION",
    "ai_status": "NOT_RUN",
    "rule_authority": "CONDITIONAL_SYNTHETIC_CONFIGURATION_NOT_SOURCE_APPROVAL"
   },
   "idempotent_replay": false,
   "result_sha256": "4df19a04361d0b9b4bfc06b5184a5f73dcda97d058d9df14441289b536f8d086"
  },
  "late": {
   "schema_version": "qc-sample-detail-1",
   "source": "SAMPLE",
   "is_sample": true,
   "approved": false,
   "transient": true,
   "production_writes": 0,
   "operational_writes": 0,
   "source_reads": 0,
   "model_training": 0,
   "final_qc_writes": 0,
   "restart_erases_state": true,
   "session_id": "qc-sample-session-3wGQD9JJxaHlbO3yZ5YbHS1x",
   "session_revision": 1,
   "generation": 1,
   "window": {
    "source": "SAMPLE",
    "start": "2026-07-09T14:40:00+09:00",
    "end": "2026-07-09T15:40:00+09:00",
    "as_of": "2026-07-09T15:41:20+09:00",
    "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
    "offset": "+09:00",
    "granularity": "minute",
    "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
   },
   "case": {
    "case_id": "sample-late-g1",
    "scenario_id": "late",
    "label": "수신 지연",
    "description": "선택 관측값이 8분 늦게 수신되어 DE Rule을 초과합니다.",
    "station_id": "SAMPLE-LATE",
    "station_name": "샘플 수신 지연 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:30:00+09:00",
    "value": 19.750002,
    "flag": "3",
    "meaning": "SUSPECT",
    "rule_ids": [
     "DE"
    ],
    "delay_seconds": 480,
    "is_missing": false,
    "revision": 1,
    "recommendation_sha256": "4c9e2773bd9d2147474875a592787e8b4ab79448a6466babb314059faf2937fa",
    "review_status": "PENDING"
   },
   "revision": 1,
   "recommendation_sha256": "4c9e2773bd9d2147474875a592787e8b4ab79448a6466babb314059faf2937fa",
   "series": {
    "rows": [
     {
      "observation_id": "SAMPLE:late:0",
      "observation_time": "2026-07-09T14:40:00+09:00",
      "value": 20,
      "rule_input_value": 20,
      "source_literal": "20.0",
      "received_time": "2026-07-09T14:40:01+09:00",
      "available_at": "2026-07-09T14:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:1",
      "observation_time": "2026-07-09T14:41:00+09:00",
      "value": 20.054557,
      "rule_input_value": 20.054557,
      "source_literal": "20.054557",
      "received_time": "2026-07-09T14:41:01+09:00",
      "available_at": "2026-07-09T14:41:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:2",
      "observation_time": "2026-07-09T14:42:00+09:00",
      "value": 20.106485,
      "rule_input_value": 20.106485,
      "source_literal": "20.106485",
      "received_time": "2026-07-09T14:42:01+09:00",
      "available_at": "2026-07-09T14:42:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:3",
      "observation_time": "2026-07-09T14:43:00+09:00",
      "value": 20.153279,
      "rule_input_value": 20.153279,
      "source_literal": "20.153279",
      "received_time": "2026-07-09T14:43:01+09:00",
      "available_at": "2026-07-09T14:43:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:4",
      "observation_time": "2026-07-09T14:44:00+09:00",
      "value": 20.192685,
      "rule_input_value": 20.192685,
      "source_literal": "20.192685",
      "received_time": "2026-07-09T14:44:01+09:00",
      "available_at": "2026-07-09T14:44:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:5",
      "observation_time": "2026-07-09T14:45:00+09:00",
      "value": 20.222802,
      "rule_input_value": 20.222802,
      "source_literal": "20.222802",
      "received_time": "2026-07-09T14:45:01+09:00",
      "available_at": "2026-07-09T14:45:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:6",
      "observation_time": "2026-07-09T14:46:00+09:00",
      "value": 20.242179,
      "rule_input_value": 20.242179,
      "source_literal": "20.242179",
      "received_time": "2026-07-09T14:46:01+09:00",
      "available_at": "2026-07-09T14:46:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:7",
      "observation_time": "2026-07-09T14:47:00+09:00",
      "value": 20.249881,
      "rule_input_value": 20.249881,
      "source_literal": "20.249881",
      "received_time": "2026-07-09T14:47:01+09:00",
      "available_at": "2026-07-09T14:47:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:8",
      "observation_time": "2026-07-09T14:48:00+09:00",
      "value": 20.245539,
      "rule_input_value": 20.245539,
      "source_literal": "20.245539",
      "received_time": "2026-07-09T14:48:01+09:00",
      "available_at": "2026-07-09T14:48:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:9",
      "observation_time": "2026-07-09T14:49:00+09:00",
      "value": 20.229359,
      "rule_input_value": 20.229359,
      "source_literal": "20.229359",
      "received_time": "2026-07-09T14:49:01+09:00",
      "available_at": "2026-07-09T14:49:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:10",
      "observation_time": "2026-07-09T14:50:00+09:00",
      "value": 20.202124,
      "rule_input_value": 20.202124,
      "source_literal": "20.202124",
      "received_time": "2026-07-09T14:50:01+09:00",
      "available_at": "2026-07-09T14:50:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:11",
      "observation_time": "2026-07-09T14:51:00+09:00",
      "value": 20.165145,
      "rule_input_value": 20.165145,
      "source_literal": "20.165145",
      "received_time": "2026-07-09T14:51:01+09:00",
      "available_at": "2026-07-09T14:51:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:12",
      "observation_time": "2026-07-09T14:52:00+09:00",
      "value": 20.120206,
      "rule_input_value": 20.120206,
      "source_literal": "20.120206",
      "received_time": "2026-07-09T14:52:01+09:00",
      "available_at": "2026-07-09T14:52:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:13",
      "observation_time": "2026-07-09T14:53:00+09:00",
      "value": 20.069471,
      "rule_input_value": 20.069471,
      "source_literal": "20.069471",
      "received_time": "2026-07-09T14:53:01+09:00",
      "available_at": "2026-07-09T14:53:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:14",
      "observation_time": "2026-07-09T14:54:00+09:00",
      "value": 20.015388,
      "rule_input_value": 20.015388,
      "source_literal": "20.015388",
      "received_time": "2026-07-09T14:54:01+09:00",
      "available_at": "2026-07-09T14:54:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:15",
      "observation_time": "2026-07-09T14:55:00+09:00",
      "value": 19.960564,
      "rule_input_value": 19.960564,
      "source_literal": "19.960564",
      "received_time": "2026-07-09T14:55:01+09:00",
      "available_at": "2026-07-09T14:55:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:16",
      "observation_time": "2026-07-09T14:56:00+09:00",
      "value": 19.90764,
      "rule_input_value": 19.90764,
      "source_literal": "19.90764",
      "received_time": "2026-07-09T14:56:01+09:00",
      "available_at": "2026-07-09T14:56:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:17",
      "observation_time": "2026-07-09T14:57:00+09:00",
      "value": 19.859168,
      "rule_input_value": 19.859168,
      "source_literal": "19.859168",
      "received_time": "2026-07-09T14:57:01+09:00",
      "available_at": "2026-07-09T14:57:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:18",
      "observation_time": "2026-07-09T14:58:00+09:00",
      "value": 19.817485,
      "rule_input_value": 19.817485,
      "source_literal": "19.817485",
      "received_time": "2026-07-09T14:58:01+09:00",
      "available_at": "2026-07-09T14:58:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:19",
      "observation_time": "2026-07-09T14:59:00+09:00",
      "value": 19.784601,
      "rule_input_value": 19.784601,
      "source_literal": "19.784601",
      "received_time": "2026-07-09T14:59:01+09:00",
      "available_at": "2026-07-09T14:59:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:20",
      "observation_time": "2026-07-09T15:00:00+09:00",
      "value": 19.762099,
      "rule_input_value": 19.762099,
      "source_literal": "19.762099",
      "received_time": "2026-07-09T15:00:01+09:00",
      "available_at": "2026-07-09T15:00:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:21",
      "observation_time": "2026-07-09T15:01:00+09:00",
      "value": 19.751066,
      "rule_input_value": 19.751066,
      "source_literal": "19.751066",
      "received_time": "2026-07-09T15:01:01+09:00",
      "available_at": "2026-07-09T15:01:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:22",
      "observation_time": "2026-07-09T15:02:00+09:00",
      "value": 19.752033,
      "rule_input_value": 19.752033,
      "source_literal": "19.752033",
      "received_time": "2026-07-09T15:02:01+09:00",
      "available_at": "2026-07-09T15:02:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:23",
      "observation_time": "2026-07-09T15:03:00+09:00",
      "value": 19.764953,
      "rule_input_value": 19.764953,
      "source_literal": "19.764953",
      "received_time": "2026-07-09T15:03:01+09:00",
      "available_at": "2026-07-09T15:03:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:24",
      "observation_time": "2026-07-09T15:04:00+09:00",
      "value": 19.789203,
      "rule_input_value": 19.789203,
      "source_literal": "19.789203",
      "received_time": "2026-07-09T15:04:01+09:00",
      "available_at": "2026-07-09T15:04:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:25",
      "observation_time": "2026-07-09T15:05:00+09:00",
      "value": 19.823615,
      "rule_input_value": 19.823615,
      "source_literal": "19.823615",
      "received_time": "2026-07-09T15:05:01+09:00",
      "available_at": "2026-07-09T15:05:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:26",
      "observation_time": "2026-07-09T15:06:00+09:00",
      "value": 19.866529,
      "rule_input_value": 19.866529,
      "source_literal": "19.866529",
      "received_time": "2026-07-09T15:06:01+09:00",
      "available_at": "2026-07-09T15:06:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:27",
      "observation_time": "2026-07-09T15:07:00+09:00",
      "value": 19.915878,
      "rule_input_value": 19.915878,
      "source_literal": "19.915878",
      "received_time": "2026-07-09T15:07:01+09:00",
      "available_at": "2026-07-09T15:07:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:28",
      "observation_time": "2026-07-09T15:08:00+09:00",
      "value": 19.969282,
      "rule_input_value": 19.969282,
      "source_literal": "19.969282",
      "received_time": "2026-07-09T15:08:01+09:00",
      "available_at": "2026-07-09T15:08:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:29",
      "observation_time": "2026-07-09T15:09:00+09:00",
      "value": 20.024166,
      "rule_input_value": 20.024166,
      "source_literal": "20.024166",
      "received_time": "2026-07-09T15:09:01+09:00",
      "available_at": "2026-07-09T15:09:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:30",
      "observation_time": "2026-07-09T15:10:00+09:00",
      "value": 20.077885,
      "rule_input_value": 20.077885,
      "source_literal": "20.077885",
      "received_time": "2026-07-09T15:10:01+09:00",
      "available_at": "2026-07-09T15:10:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:31",
      "observation_time": "2026-07-09T15:11:00+09:00",
      "value": 20.12785,
      "rule_input_value": 20.12785,
      "source_literal": "20.12785",
      "received_time": "2026-07-09T15:11:01+09:00",
      "available_at": "2026-07-09T15:11:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:32",
      "observation_time": "2026-07-09T15:12:00+09:00",
      "value": 20.171652,
      "rule_input_value": 20.171652,
      "source_literal": "20.171652",
      "received_time": "2026-07-09T15:12:01+09:00",
      "available_at": "2026-07-09T15:12:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:33",
      "observation_time": "2026-07-09T15:13:00+09:00",
      "value": 20.20718,
      "rule_input_value": 20.20718,
      "source_literal": "20.20718",
      "received_time": "2026-07-09T15:13:01+09:00",
      "available_at": "2026-07-09T15:13:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:34",
      "observation_time": "2026-07-09T15:14:00+09:00",
      "value": 20.23272,
      "rule_input_value": 20.23272,
      "source_literal": "20.23272",
      "received_time": "2026-07-09T15:14:01+09:00",
      "available_at": "2026-07-09T15:14:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:35",
      "observation_time": "2026-07-09T15:15:00+09:00",
      "value": 20.247042,
      "rule_input_value": 20.247042,
      "source_literal": "20.247042",
      "received_time": "2026-07-09T15:15:01+09:00",
      "available_at": "2026-07-09T15:15:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:36",
      "observation_time": "2026-07-09T15:16:00+09:00",
      "value": 20.249455,
      "rule_input_value": 20.249455,
      "source_literal": "20.249455",
      "received_time": "2026-07-09T15:16:01+09:00",
      "available_at": "2026-07-09T15:16:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:37",
      "observation_time": "2026-07-09T15:17:00+09:00",
      "value": 20.239844,
      "rule_input_value": 20.239844,
      "source_literal": "20.239844",
      "received_time": "2026-07-09T15:17:01+09:00",
      "available_at": "2026-07-09T15:17:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:38",
      "observation_time": "2026-07-09T15:18:00+09:00",
      "value": 20.21867,
      "rule_input_value": 20.21867,
      "source_literal": "20.21867",
      "received_time": "2026-07-09T15:18:01+09:00",
      "available_at": "2026-07-09T15:18:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:39",
      "observation_time": "2026-07-09T15:19:00+09:00",
      "value": 20.186956,
      "rule_input_value": 20.186956,
      "source_literal": "20.186956",
      "received_time": "2026-07-09T15:19:01+09:00",
      "available_at": "2026-07-09T15:19:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:40",
      "observation_time": "2026-07-09T15:20:00+09:00",
      "value": 20.146229,
      "rule_input_value": 20.146229,
      "source_literal": "20.146229",
      "received_time": "2026-07-09T15:20:01+09:00",
      "available_at": "2026-07-09T15:20:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:41",
      "observation_time": "2026-07-09T15:21:00+09:00",
      "value": 20.098454,
      "rule_input_value": 20.098454,
      "source_literal": "20.098454",
      "received_time": "2026-07-09T15:21:01+09:00",
      "available_at": "2026-07-09T15:21:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:42",
      "observation_time": "2026-07-09T15:22:00+09:00",
      "value": 20.045932,
      "rule_input_value": 20.045932,
      "source_literal": "20.045932",
      "received_time": "2026-07-09T15:22:01+09:00",
      "available_at": "2026-07-09T15:22:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:43",
      "observation_time": "2026-07-09T15:23:00+09:00",
      "value": 19.991196,
      "rule_input_value": 19.991196,
      "source_literal": "19.991196",
      "received_time": "2026-07-09T15:23:01+09:00",
      "available_at": "2026-07-09T15:23:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:44",
      "observation_time": "2026-07-09T15:24:00+09:00",
      "value": 19.936885,
      "rule_input_value": 19.936885,
      "source_literal": "19.936885",
      "received_time": "2026-07-09T15:24:01+09:00",
      "available_at": "2026-07-09T15:24:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:45",
      "observation_time": "2026-07-09T15:25:00+09:00",
      "value": 19.885616,
      "rule_input_value": 19.885616,
      "source_literal": "19.885616",
      "received_time": "2026-07-09T15:25:01+09:00",
      "available_at": "2026-07-09T15:25:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:46",
      "observation_time": "2026-07-09T15:26:00+09:00",
      "value": 19.839861,
      "rule_input_value": 19.839861,
      "source_literal": "19.839861",
      "received_time": "2026-07-09T15:26:01+09:00",
      "available_at": "2026-07-09T15:26:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:47",
      "observation_time": "2026-07-09T15:27:00+09:00",
      "value": 19.801826,
      "rule_input_value": 19.801826,
      "source_literal": "19.801826",
      "received_time": "2026-07-09T15:27:01+09:00",
      "available_at": "2026-07-09T15:27:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:48",
      "observation_time": "2026-07-09T15:28:00+09:00",
      "value": 19.773343,
      "rule_input_value": 19.773343,
      "source_literal": "19.773343",
      "received_time": "2026-07-09T15:28:01+09:00",
      "available_at": "2026-07-09T15:28:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:49",
      "observation_time": "2026-07-09T15:29:00+09:00",
      "value": 19.755787,
      "rule_input_value": 19.755787,
      "source_literal": "19.755787",
      "received_time": "2026-07-09T15:29:01+09:00",
      "available_at": "2026-07-09T15:29:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:50",
      "observation_time": "2026-07-09T15:30:00+09:00",
      "value": 19.750002,
      "rule_input_value": 19.750002,
      "source_literal": "19.750002",
      "received_time": "2026-07-09T15:38:00+09:00",
      "available_at": "2026-07-09T15:38:00+09:00",
      "delay_seconds": 480,
      "is_missing": false,
      "is_late": true,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "3",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "3",
        "reason": "LIMIT_EXCEEDED"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:51",
      "observation_time": "2026-07-09T15:31:00+09:00",
      "value": 19.756269,
      "rule_input_value": 19.756269,
      "source_literal": "19.756269",
      "received_time": "2026-07-09T15:31:01+09:00",
      "available_at": "2026-07-09T15:31:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:52",
      "observation_time": "2026-07-09T15:32:00+09:00",
      "value": 19.774286,
      "rule_input_value": 19.774286,
      "source_literal": "19.774286",
      "received_time": "2026-07-09T15:32:01+09:00",
      "available_at": "2026-07-09T15:32:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:53",
      "observation_time": "2026-07-09T15:33:00+09:00",
      "value": 19.803182,
      "rule_input_value": 19.803182,
      "source_literal": "19.803182",
      "received_time": "2026-07-09T15:33:01+09:00",
      "available_at": "2026-07-09T15:33:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:54",
      "observation_time": "2026-07-09T15:34:00+09:00",
      "value": 19.841567,
      "rule_input_value": 19.841567,
      "source_literal": "19.841567",
      "received_time": "2026-07-09T15:34:01+09:00",
      "available_at": "2026-07-09T15:34:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:55",
      "observation_time": "2026-07-09T15:35:00+09:00",
      "value": 19.887588,
      "rule_input_value": 19.887588,
      "source_literal": "19.887588",
      "received_time": "2026-07-09T15:35:01+09:00",
      "available_at": "2026-07-09T15:35:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:56",
      "observation_time": "2026-07-09T15:36:00+09:00",
      "value": 19.939029,
      "rule_input_value": 19.939029,
      "source_literal": "19.939029",
      "received_time": "2026-07-09T15:36:01+09:00",
      "available_at": "2026-07-09T15:36:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:57",
      "observation_time": "2026-07-09T15:37:00+09:00",
      "value": 19.993408,
      "rule_input_value": 19.993408,
      "source_literal": "19.993408",
      "received_time": "2026-07-09T15:37:01+09:00",
      "available_at": "2026-07-09T15:37:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:58",
      "observation_time": "2026-07-09T15:38:00+09:00",
      "value": 20.048105,
      "rule_input_value": 20.048105,
      "source_literal": "20.048105",
      "received_time": "2026-07-09T15:38:01+09:00",
      "available_at": "2026-07-09T15:38:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:59",
      "observation_time": "2026-07-09T15:39:00+09:00",
      "value": 20.100484,
      "rule_input_value": 20.100484,
      "source_literal": "20.100484",
      "received_time": "2026-07-09T15:39:01+09:00",
      "available_at": "2026-07-09T15:39:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:late:60",
      "observation_time": "2026-07-09T15:40:00+09:00",
      "value": 20.148018,
      "rule_input_value": 20.148018,
      "source_literal": "20.148018",
      "received_time": "2026-07-09T15:40:01+09:00",
      "available_at": "2026-07-09T15:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     }
    ],
    "unit": "degree_C",
    "cadence_seconds": 60,
    "planned_slots": 61,
    "received_slots": 61,
    "missing_slots": 0,
    "interpolated": false
   },
   "rules": [
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "LOCATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 40,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 120,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "NOT_APPLICABLE_IN_TABLE_2_9",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 1,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": 300,
     "result_flag": "3",
     "evaluation_status": "EVALUATED",
     "result_reason": "LIMIT_EXCEEDED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:late:50",
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "scope": {
      "station_id": "SAMPLE-LATE",
      "sensor_id": "SAMPLE-LATE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-LATE-EPISODE"
     },
     "event_at": "2026-07-09T15:30:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 19.750002,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "RELATED_OBSERVATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    }
   ],
   "rule_specs": [
    {
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "sentinels": [
       -999
      ]
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "min": 0,
      "max": 40,
      "boundary": "CLOSED"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "duration_seconds": 120,
      "interval_seconds": 60,
      "duration_boundary": "AT_LEAST"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "interval_seconds": 60,
      "max_delta": 1,
      "difference": "LINEAR"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "max_delay_seconds": 300
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    }
   ],
   "equipment": {
    "source": "SAMPLE",
    "synthetic": true,
    "station_id": "SAMPLE-LATE",
    "physical_sensor_id": "SAMPLE-LATE-SENSOR",
    "sensor_episode_id": "SAMPLE-LATE-EPISODE",
    "label": "가상 수온 센서",
    "unit": "degree_C"
   },
   "source_facts": {
    "physical_sensor_id": "SAMPLE-LATE-SENSOR",
    "sensor_episode_id": "SAMPLE-LATE-EPISODE",
    "quantity_kind": "WATER_TEMP_SCALAR",
    "clock_semantics": "EXPLICIT_SYNTHETIC_OFFSET",
    "source_timezone_name": "Etc/GMT-9",
    "effective_start": "2026-07-09T13:40:00+09:00",
    "effective_end": "2026-07-09T16:40:00+09:00",
    "available_at": "2026-07-09T14:39:00+09:00",
    "version_available_at": "2026-07-09T14:39:00+09:00",
    "evidence": {
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
    }
   },
   "evidence": [
    {
     "kind": "SYNTHETIC_SOURCE_CONTRACT",
     "source": "SAMPLE",
     "label": "명시된 가상 원천·센서 계약",
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "description": "실제 원천·계정·승인과 관계없는 고정 샘플 정의입니다."
    },
    {
     "kind": "ACTUAL_RULE_EXECUTION",
     "source": "SAMPLE",
     "label": "기존 Rule 엔진 계산 결과",
     "sha256": "5ec7b8a7ae2041415b172774a5262568606a53985579026ecac05f5a3eee80b3",
     "description": "WT/ER/GR/GD/SP/DE는 가상 설정으로 계산합니다. 다른 Rule의 관련·과거 근거는 제공하지 않았으며, 결측 sentinel 선행 검사 9는 과거 baseline 검사 완료를 뜻하지 않습니다."
    }
   ],
   "ai": {
    "status": "NOT_RUN",
    "trained_model": false,
    "result": null
   },
   "workflow": {
    "status": "PENDING",
    "blocked": true,
    "downstream_executed": false,
    "approved": false,
    "definitive_qc": false,
    "history": [
     {
      "sequence": 1,
      "action": "CREATE",
      "from_state": null,
      "to_state": "PENDING",
      "comment": "샘플 검토가 필요하여 후속 단계에서 정지했습니다.",
      "actor": "SAMPLE_ENGINE",
      "sample_clock": "2026-07-09T15:41:20+09:00"
     }
    ],
    "revision": 1,
    "recommendation_sha256": "4c9e2773bd9d2147474875a592787e8b4ab79448a6466babb314059faf2937fa",
    "capabilities": {
     "comment": true,
     "approve": true,
     "hold": true,
     "reject": true,
     "resume": false
    }
   },
   "provenance": {
    "source": "SAMPLE",
    "is_sample": true,
    "approved": false,
    "transient": true,
    "production_writes": 0,
    "operational_writes": 0,
    "source_reads": 0,
    "model_training": 0,
    "final_qc_writes": 0,
    "restart_erases_state": true,
    "rule_engine_version": "guide-existing-12-v1",
    "rule_implementation_sha256": "9993072a38e264808c828a93a460908bef59a6e9e8d58cdc11198425eef2ff51",
    "sample_definition_version": "QC_SAMPLE_SYNTHETIC_V1",
    "sample_definition_sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
    "rule_catalog_sha256": "7d30ad39f1ff40bbfb2224866f869ffd53782e958a94f3e71bf767b35e8d4889",
    "clock_warning": "명시된 가상 +09:00 시각이며 실제 원천의 시간대를 확정하지 않습니다.",
    "missing_policy": "EXPLICIT_SYNTHETIC_SENTINEL_FOR_ABSENT_SLOT; DISPLAY_NULL; NO_INTERPOLATION",
    "ai_status": "NOT_RUN",
    "rule_authority": "CONDITIONAL_SYNTHETIC_CONFIGURATION_NOT_SOURCE_APPROVAL"
   },
   "idempotent_replay": false,
   "result_sha256": "18a73dfe513dc6bf1e37c5067eb36ca28e555f20ded255515b3c500db6f5ca4e"
  },
  "missing": {
   "schema_version": "qc-sample-detail-1",
   "source": "SAMPLE",
   "is_sample": true,
   "approved": false,
   "transient": true,
   "production_writes": 0,
   "operational_writes": 0,
   "source_reads": 0,
   "model_training": 0,
   "final_qc_writes": 0,
   "restart_erases_state": true,
   "session_id": "qc-sample-session-3wGQD9JJxaHlbO3yZ5YbHS1x",
   "session_revision": 1,
   "generation": 1,
   "window": {
    "source": "SAMPLE",
    "start": "2026-07-09T14:40:00+09:00",
    "end": "2026-07-09T15:40:00+09:00",
    "as_of": "2026-07-09T15:41:20+09:00",
    "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
    "offset": "+09:00",
    "granularity": "minute",
    "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
   },
   "case": {
    "case_id": "sample-missing-g1",
    "scenario_id": "missing",
    "label": "결측",
    "description": "3개 예정 슬롯이 수신되지 않았습니다. 보간 없이 null로 표시합니다.",
    "station_id": "SAMPLE-MISSING",
    "station_name": "샘플 결측 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:10:00+09:00",
    "value": null,
    "flag": "9",
    "meaning": "MISSING",
    "rule_ids": [
     "ER",
     "GR",
     "GD",
     "SP",
     "RR",
     "SR",
     "ST"
    ],
    "delay_seconds": null,
    "is_missing": true,
    "revision": 1,
    "recommendation_sha256": "8859224fe03ecd8ef3f4c82ae40aa521359c2e6289a0d0f3ea8c02c9d044e56e",
    "review_status": "PENDING"
   },
   "revision": 1,
   "recommendation_sha256": "8859224fe03ecd8ef3f4c82ae40aa521359c2e6289a0d0f3ea8c02c9d044e56e",
   "series": {
    "rows": [
     {
      "observation_id": "SAMPLE:missing:0",
      "observation_time": "2026-07-09T14:40:00+09:00",
      "value": 20,
      "rule_input_value": 20,
      "source_literal": "20.0",
      "received_time": "2026-07-09T14:40:01+09:00",
      "available_at": "2026-07-09T14:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:1",
      "observation_time": "2026-07-09T14:41:00+09:00",
      "value": 20.054557,
      "rule_input_value": 20.054557,
      "source_literal": "20.054557",
      "received_time": "2026-07-09T14:41:01+09:00",
      "available_at": "2026-07-09T14:41:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:2",
      "observation_time": "2026-07-09T14:42:00+09:00",
      "value": 20.106485,
      "rule_input_value": 20.106485,
      "source_literal": "20.106485",
      "received_time": "2026-07-09T14:42:01+09:00",
      "available_at": "2026-07-09T14:42:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:3",
      "observation_time": "2026-07-09T14:43:00+09:00",
      "value": 20.153279,
      "rule_input_value": 20.153279,
      "source_literal": "20.153279",
      "received_time": "2026-07-09T14:43:01+09:00",
      "available_at": "2026-07-09T14:43:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:4",
      "observation_time": "2026-07-09T14:44:00+09:00",
      "value": 20.192685,
      "rule_input_value": 20.192685,
      "source_literal": "20.192685",
      "received_time": "2026-07-09T14:44:01+09:00",
      "available_at": "2026-07-09T14:44:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:5",
      "observation_time": "2026-07-09T14:45:00+09:00",
      "value": 20.222802,
      "rule_input_value": 20.222802,
      "source_literal": "20.222802",
      "received_time": "2026-07-09T14:45:01+09:00",
      "available_at": "2026-07-09T14:45:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:6",
      "observation_time": "2026-07-09T14:46:00+09:00",
      "value": 20.242179,
      "rule_input_value": 20.242179,
      "source_literal": "20.242179",
      "received_time": "2026-07-09T14:46:01+09:00",
      "available_at": "2026-07-09T14:46:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:7",
      "observation_time": "2026-07-09T14:47:00+09:00",
      "value": 20.249881,
      "rule_input_value": 20.249881,
      "source_literal": "20.249881",
      "received_time": "2026-07-09T14:47:01+09:00",
      "available_at": "2026-07-09T14:47:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:8",
      "observation_time": "2026-07-09T14:48:00+09:00",
      "value": 20.245539,
      "rule_input_value": 20.245539,
      "source_literal": "20.245539",
      "received_time": "2026-07-09T14:48:01+09:00",
      "available_at": "2026-07-09T14:48:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:9",
      "observation_time": "2026-07-09T14:49:00+09:00",
      "value": 20.229359,
      "rule_input_value": 20.229359,
      "source_literal": "20.229359",
      "received_time": "2026-07-09T14:49:01+09:00",
      "available_at": "2026-07-09T14:49:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:10",
      "observation_time": "2026-07-09T14:50:00+09:00",
      "value": 20.202124,
      "rule_input_value": 20.202124,
      "source_literal": "20.202124",
      "received_time": "2026-07-09T14:50:01+09:00",
      "available_at": "2026-07-09T14:50:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:11",
      "observation_time": "2026-07-09T14:51:00+09:00",
      "value": 20.165145,
      "rule_input_value": 20.165145,
      "source_literal": "20.165145",
      "received_time": "2026-07-09T14:51:01+09:00",
      "available_at": "2026-07-09T14:51:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:12",
      "observation_time": "2026-07-09T14:52:00+09:00",
      "value": 20.120206,
      "rule_input_value": 20.120206,
      "source_literal": "20.120206",
      "received_time": "2026-07-09T14:52:01+09:00",
      "available_at": "2026-07-09T14:52:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:13",
      "observation_time": "2026-07-09T14:53:00+09:00",
      "value": 20.069471,
      "rule_input_value": 20.069471,
      "source_literal": "20.069471",
      "received_time": "2026-07-09T14:53:01+09:00",
      "available_at": "2026-07-09T14:53:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:14",
      "observation_time": "2026-07-09T14:54:00+09:00",
      "value": 20.015388,
      "rule_input_value": 20.015388,
      "source_literal": "20.015388",
      "received_time": "2026-07-09T14:54:01+09:00",
      "available_at": "2026-07-09T14:54:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:15",
      "observation_time": "2026-07-09T14:55:00+09:00",
      "value": 19.960564,
      "rule_input_value": 19.960564,
      "source_literal": "19.960564",
      "received_time": "2026-07-09T14:55:01+09:00",
      "available_at": "2026-07-09T14:55:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:16",
      "observation_time": "2026-07-09T14:56:00+09:00",
      "value": 19.90764,
      "rule_input_value": 19.90764,
      "source_literal": "19.90764",
      "received_time": "2026-07-09T14:56:01+09:00",
      "available_at": "2026-07-09T14:56:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:17",
      "observation_time": "2026-07-09T14:57:00+09:00",
      "value": 19.859168,
      "rule_input_value": 19.859168,
      "source_literal": "19.859168",
      "received_time": "2026-07-09T14:57:01+09:00",
      "available_at": "2026-07-09T14:57:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:18",
      "observation_time": "2026-07-09T14:58:00+09:00",
      "value": 19.817485,
      "rule_input_value": 19.817485,
      "source_literal": "19.817485",
      "received_time": "2026-07-09T14:58:01+09:00",
      "available_at": "2026-07-09T14:58:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:19",
      "observation_time": "2026-07-09T14:59:00+09:00",
      "value": 19.784601,
      "rule_input_value": 19.784601,
      "source_literal": "19.784601",
      "received_time": "2026-07-09T14:59:01+09:00",
      "available_at": "2026-07-09T14:59:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:20",
      "observation_time": "2026-07-09T15:00:00+09:00",
      "value": 19.762099,
      "rule_input_value": 19.762099,
      "source_literal": "19.762099",
      "received_time": "2026-07-09T15:00:01+09:00",
      "available_at": "2026-07-09T15:00:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:21",
      "observation_time": "2026-07-09T15:01:00+09:00",
      "value": 19.751066,
      "rule_input_value": 19.751066,
      "source_literal": "19.751066",
      "received_time": "2026-07-09T15:01:01+09:00",
      "available_at": "2026-07-09T15:01:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:22",
      "observation_time": "2026-07-09T15:02:00+09:00",
      "value": 19.752033,
      "rule_input_value": 19.752033,
      "source_literal": "19.752033",
      "received_time": "2026-07-09T15:02:01+09:00",
      "available_at": "2026-07-09T15:02:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:23",
      "observation_time": "2026-07-09T15:03:00+09:00",
      "value": 19.764953,
      "rule_input_value": 19.764953,
      "source_literal": "19.764953",
      "received_time": "2026-07-09T15:03:01+09:00",
      "available_at": "2026-07-09T15:03:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:24",
      "observation_time": "2026-07-09T15:04:00+09:00",
      "value": 19.789203,
      "rule_input_value": 19.789203,
      "source_literal": "19.789203",
      "received_time": "2026-07-09T15:04:01+09:00",
      "available_at": "2026-07-09T15:04:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:25",
      "observation_time": "2026-07-09T15:05:00+09:00",
      "value": 19.823615,
      "rule_input_value": 19.823615,
      "source_literal": "19.823615",
      "received_time": "2026-07-09T15:05:01+09:00",
      "available_at": "2026-07-09T15:05:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:26",
      "observation_time": "2026-07-09T15:06:00+09:00",
      "value": 19.866529,
      "rule_input_value": 19.866529,
      "source_literal": "19.866529",
      "received_time": "2026-07-09T15:06:01+09:00",
      "available_at": "2026-07-09T15:06:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:27",
      "observation_time": "2026-07-09T15:07:00+09:00",
      "value": 19.915878,
      "rule_input_value": 19.915878,
      "source_literal": "19.915878",
      "received_time": "2026-07-09T15:07:01+09:00",
      "available_at": "2026-07-09T15:07:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:28",
      "observation_time": "2026-07-09T15:08:00+09:00",
      "value": 19.969282,
      "rule_input_value": 19.969282,
      "source_literal": "19.969282",
      "received_time": "2026-07-09T15:08:01+09:00",
      "available_at": "2026-07-09T15:08:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:29",
      "observation_time": "2026-07-09T15:09:00+09:00",
      "value": null,
      "rule_input_value": -999,
      "source_literal": null,
      "received_time": null,
      "available_at": "2026-07-09T15:41:20+09:00",
      "delay_seconds": null,
      "is_missing": true,
      "is_late": false,
      "observed": false,
      "record_kind": "SCHEDULED_SLOT_GAP",
      "interpolated": false,
      "flag": "9",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "NOT_EVALUATED",
        "reason": "AWARE_TIMESTAMP_REQUIRED"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "GR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "GD",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "RR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "SR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "ST",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "DE",
        "flag": "NOT_EVALUATED",
        "reason": "AWARE_TIMESTAMP_REQUIRED"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:30",
      "observation_time": "2026-07-09T15:10:00+09:00",
      "value": null,
      "rule_input_value": -999,
      "source_literal": null,
      "received_time": null,
      "available_at": "2026-07-09T15:41:20+09:00",
      "delay_seconds": null,
      "is_missing": true,
      "is_late": false,
      "observed": false,
      "record_kind": "SCHEDULED_SLOT_GAP",
      "interpolated": false,
      "flag": "9",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "NOT_EVALUATED",
        "reason": "AWARE_TIMESTAMP_REQUIRED"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "GR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "GD",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "RR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "SR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "ST",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "DE",
        "flag": "NOT_EVALUATED",
        "reason": "AWARE_TIMESTAMP_REQUIRED"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:31",
      "observation_time": "2026-07-09T15:11:00+09:00",
      "value": null,
      "rule_input_value": -999,
      "source_literal": null,
      "received_time": null,
      "available_at": "2026-07-09T15:41:20+09:00",
      "delay_seconds": null,
      "is_missing": true,
      "is_late": false,
      "observed": false,
      "record_kind": "SCHEDULED_SLOT_GAP",
      "interpolated": false,
      "flag": "9",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "NOT_EVALUATED",
        "reason": "AWARE_TIMESTAMP_REQUIRED"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "GR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "GD",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "RR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "SR",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "ST",
        "flag": "9",
        "reason": "DECLARED_MISSING_SENTINEL"
       },
       {
        "rule_id": "DE",
        "flag": "NOT_EVALUATED",
        "reason": "AWARE_TIMESTAMP_REQUIRED"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:32",
      "observation_time": "2026-07-09T15:12:00+09:00",
      "value": 20.171652,
      "rule_input_value": 20.171652,
      "source_literal": "20.171652",
      "received_time": "2026-07-09T15:12:01+09:00",
      "available_at": "2026-07-09T15:12:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "MISSING_SENTINEL_IN_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "NOT_EVALUATED",
        "reason": "MISSING_SENTINEL_IN_WINDOW"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:33",
      "observation_time": "2026-07-09T15:13:00+09:00",
      "value": 20.20718,
      "rule_input_value": 20.20718,
      "source_literal": "20.20718",
      "received_time": "2026-07-09T15:13:01+09:00",
      "available_at": "2026-07-09T15:13:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "MISSING_SENTINEL_IN_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:34",
      "observation_time": "2026-07-09T15:14:00+09:00",
      "value": 20.23272,
      "rule_input_value": 20.23272,
      "source_literal": "20.23272",
      "received_time": "2026-07-09T15:14:01+09:00",
      "available_at": "2026-07-09T15:14:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:35",
      "observation_time": "2026-07-09T15:15:00+09:00",
      "value": 20.247042,
      "rule_input_value": 20.247042,
      "source_literal": "20.247042",
      "received_time": "2026-07-09T15:15:01+09:00",
      "available_at": "2026-07-09T15:15:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:36",
      "observation_time": "2026-07-09T15:16:00+09:00",
      "value": 20.249455,
      "rule_input_value": 20.249455,
      "source_literal": "20.249455",
      "received_time": "2026-07-09T15:16:01+09:00",
      "available_at": "2026-07-09T15:16:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:37",
      "observation_time": "2026-07-09T15:17:00+09:00",
      "value": 20.239844,
      "rule_input_value": 20.239844,
      "source_literal": "20.239844",
      "received_time": "2026-07-09T15:17:01+09:00",
      "available_at": "2026-07-09T15:17:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:38",
      "observation_time": "2026-07-09T15:18:00+09:00",
      "value": 20.21867,
      "rule_input_value": 20.21867,
      "source_literal": "20.21867",
      "received_time": "2026-07-09T15:18:01+09:00",
      "available_at": "2026-07-09T15:18:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:39",
      "observation_time": "2026-07-09T15:19:00+09:00",
      "value": 20.186956,
      "rule_input_value": 20.186956,
      "source_literal": "20.186956",
      "received_time": "2026-07-09T15:19:01+09:00",
      "available_at": "2026-07-09T15:19:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:40",
      "observation_time": "2026-07-09T15:20:00+09:00",
      "value": 20.146229,
      "rule_input_value": 20.146229,
      "source_literal": "20.146229",
      "received_time": "2026-07-09T15:20:01+09:00",
      "available_at": "2026-07-09T15:20:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:41",
      "observation_time": "2026-07-09T15:21:00+09:00",
      "value": 20.098454,
      "rule_input_value": 20.098454,
      "source_literal": "20.098454",
      "received_time": "2026-07-09T15:21:01+09:00",
      "available_at": "2026-07-09T15:21:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:42",
      "observation_time": "2026-07-09T15:22:00+09:00",
      "value": 20.045932,
      "rule_input_value": 20.045932,
      "source_literal": "20.045932",
      "received_time": "2026-07-09T15:22:01+09:00",
      "available_at": "2026-07-09T15:22:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:43",
      "observation_time": "2026-07-09T15:23:00+09:00",
      "value": 19.991196,
      "rule_input_value": 19.991196,
      "source_literal": "19.991196",
      "received_time": "2026-07-09T15:23:01+09:00",
      "available_at": "2026-07-09T15:23:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:44",
      "observation_time": "2026-07-09T15:24:00+09:00",
      "value": 19.936885,
      "rule_input_value": 19.936885,
      "source_literal": "19.936885",
      "received_time": "2026-07-09T15:24:01+09:00",
      "available_at": "2026-07-09T15:24:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:45",
      "observation_time": "2026-07-09T15:25:00+09:00",
      "value": 19.885616,
      "rule_input_value": 19.885616,
      "source_literal": "19.885616",
      "received_time": "2026-07-09T15:25:01+09:00",
      "available_at": "2026-07-09T15:25:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:46",
      "observation_time": "2026-07-09T15:26:00+09:00",
      "value": 19.839861,
      "rule_input_value": 19.839861,
      "source_literal": "19.839861",
      "received_time": "2026-07-09T15:26:01+09:00",
      "available_at": "2026-07-09T15:26:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:47",
      "observation_time": "2026-07-09T15:27:00+09:00",
      "value": 19.801826,
      "rule_input_value": 19.801826,
      "source_literal": "19.801826",
      "received_time": "2026-07-09T15:27:01+09:00",
      "available_at": "2026-07-09T15:27:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:48",
      "observation_time": "2026-07-09T15:28:00+09:00",
      "value": 19.773343,
      "rule_input_value": 19.773343,
      "source_literal": "19.773343",
      "received_time": "2026-07-09T15:28:01+09:00",
      "available_at": "2026-07-09T15:28:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:49",
      "observation_time": "2026-07-09T15:29:00+09:00",
      "value": 19.755787,
      "rule_input_value": 19.755787,
      "source_literal": "19.755787",
      "received_time": "2026-07-09T15:29:01+09:00",
      "available_at": "2026-07-09T15:29:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:50",
      "observation_time": "2026-07-09T15:30:00+09:00",
      "value": 19.750002,
      "rule_input_value": 19.750002,
      "source_literal": "19.750002",
      "received_time": "2026-07-09T15:30:01+09:00",
      "available_at": "2026-07-09T15:30:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:51",
      "observation_time": "2026-07-09T15:31:00+09:00",
      "value": 19.756269,
      "rule_input_value": 19.756269,
      "source_literal": "19.756269",
      "received_time": "2026-07-09T15:31:01+09:00",
      "available_at": "2026-07-09T15:31:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:52",
      "observation_time": "2026-07-09T15:32:00+09:00",
      "value": 19.774286,
      "rule_input_value": 19.774286,
      "source_literal": "19.774286",
      "received_time": "2026-07-09T15:32:01+09:00",
      "available_at": "2026-07-09T15:32:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:53",
      "observation_time": "2026-07-09T15:33:00+09:00",
      "value": 19.803182,
      "rule_input_value": 19.803182,
      "source_literal": "19.803182",
      "received_time": "2026-07-09T15:33:01+09:00",
      "available_at": "2026-07-09T15:33:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:54",
      "observation_time": "2026-07-09T15:34:00+09:00",
      "value": 19.841567,
      "rule_input_value": 19.841567,
      "source_literal": "19.841567",
      "received_time": "2026-07-09T15:34:01+09:00",
      "available_at": "2026-07-09T15:34:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:55",
      "observation_time": "2026-07-09T15:35:00+09:00",
      "value": 19.887588,
      "rule_input_value": 19.887588,
      "source_literal": "19.887588",
      "received_time": "2026-07-09T15:35:01+09:00",
      "available_at": "2026-07-09T15:35:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:56",
      "observation_time": "2026-07-09T15:36:00+09:00",
      "value": 19.939029,
      "rule_input_value": 19.939029,
      "source_literal": "19.939029",
      "received_time": "2026-07-09T15:36:01+09:00",
      "available_at": "2026-07-09T15:36:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:57",
      "observation_time": "2026-07-09T15:37:00+09:00",
      "value": 19.993408,
      "rule_input_value": 19.993408,
      "source_literal": "19.993408",
      "received_time": "2026-07-09T15:37:01+09:00",
      "available_at": "2026-07-09T15:37:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:58",
      "observation_time": "2026-07-09T15:38:00+09:00",
      "value": 20.048105,
      "rule_input_value": 20.048105,
      "source_literal": "20.048105",
      "received_time": "2026-07-09T15:38:01+09:00",
      "available_at": "2026-07-09T15:38:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:59",
      "observation_time": "2026-07-09T15:39:00+09:00",
      "value": 20.100484,
      "rule_input_value": 20.100484,
      "source_literal": "20.100484",
      "received_time": "2026-07-09T15:39:01+09:00",
      "available_at": "2026-07-09T15:39:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:missing:60",
      "observation_time": "2026-07-09T15:40:00+09:00",
      "value": 20.148018,
      "rule_input_value": 20.148018,
      "source_literal": "20.148018",
      "received_time": "2026-07-09T15:40:01+09:00",
      "available_at": "2026-07-09T15:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     }
    ],
    "unit": "degree_C",
    "cadence_seconds": 60,
    "planned_slots": 61,
    "received_slots": 58,
    "missing_slots": 3,
    "interpolated": false
   },
   "rules": [
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "AWARE_TIMESTAMP_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "LOCATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "NOT_APPLICABLE_IN_TABLE_2_9",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "9",
     "evaluation_status": "MISSING",
     "result_reason": "DECLARED_MISSING_SENTINEL",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "AWARE_TIMESTAMP_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:missing:30",
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "scope": {
      "station_id": "SAMPLE-MISSING",
      "sensor_id": "SAMPLE-MISSING-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-MISSING-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": -999,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "RELATED_OBSERVATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    }
   ],
   "rule_specs": [
    {
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "sentinels": [
       -999
      ]
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "min": 0,
      "max": 40,
      "boundary": "CLOSED"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "duration_seconds": 120,
      "interval_seconds": 60,
      "duration_boundary": "AT_LEAST"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "interval_seconds": 60,
      "max_delta": 1,
      "difference": "LINEAR"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "max_delay_seconds": 300
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    }
   ],
   "equipment": {
    "source": "SAMPLE",
    "synthetic": true,
    "station_id": "SAMPLE-MISSING",
    "physical_sensor_id": "SAMPLE-MISSING-SENSOR",
    "sensor_episode_id": "SAMPLE-MISSING-EPISODE",
    "label": "가상 수온 센서",
    "unit": "degree_C"
   },
   "source_facts": {
    "physical_sensor_id": "SAMPLE-MISSING-SENSOR",
    "sensor_episode_id": "SAMPLE-MISSING-EPISODE",
    "quantity_kind": "WATER_TEMP_SCALAR",
    "clock_semantics": "EXPLICIT_SYNTHETIC_OFFSET",
    "source_timezone_name": "Etc/GMT-9",
    "effective_start": "2026-07-09T13:40:00+09:00",
    "effective_end": "2026-07-09T16:40:00+09:00",
    "available_at": "2026-07-09T14:39:00+09:00",
    "version_available_at": "2026-07-09T14:39:00+09:00",
    "evidence": {
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
    }
   },
   "evidence": [
    {
     "kind": "SYNTHETIC_SOURCE_CONTRACT",
     "source": "SAMPLE",
     "label": "명시된 가상 원천·센서 계약",
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "description": "실제 원천·계정·승인과 관계없는 고정 샘플 정의입니다."
    },
    {
     "kind": "ACTUAL_RULE_EXECUTION",
     "source": "SAMPLE",
     "label": "기존 Rule 엔진 계산 결과",
     "sha256": "e94840b9b1950972234bc60287c96147a322d184de266931c2d6322e5a143844",
     "description": "WT/ER/GR/GD/SP/DE는 가상 설정으로 계산합니다. 다른 Rule의 관련·과거 근거는 제공하지 않았으며, 결측 sentinel 선행 검사 9는 과거 baseline 검사 완료를 뜻하지 않습니다."
    }
   ],
   "ai": {
    "status": "NOT_RUN",
    "trained_model": false,
    "result": null
   },
   "workflow": {
    "status": "PENDING",
    "blocked": true,
    "downstream_executed": false,
    "approved": false,
    "definitive_qc": false,
    "history": [
     {
      "sequence": 1,
      "action": "CREATE",
      "from_state": null,
      "to_state": "PENDING",
      "comment": "샘플 검토가 필요하여 후속 단계에서 정지했습니다.",
      "actor": "SAMPLE_ENGINE",
      "sample_clock": "2026-07-09T15:41:20+09:00"
     }
    ],
    "revision": 1,
    "recommendation_sha256": "8859224fe03ecd8ef3f4c82ae40aa521359c2e6289a0d0f3ea8c02c9d044e56e",
    "capabilities": {
     "comment": true,
     "approve": true,
     "hold": true,
     "reject": true,
     "resume": false
    }
   },
   "provenance": {
    "source": "SAMPLE",
    "is_sample": true,
    "approved": false,
    "transient": true,
    "production_writes": 0,
    "operational_writes": 0,
    "source_reads": 0,
    "model_training": 0,
    "final_qc_writes": 0,
    "restart_erases_state": true,
    "rule_engine_version": "guide-existing-12-v1",
    "rule_implementation_sha256": "9993072a38e264808c828a93a460908bef59a6e9e8d58cdc11198425eef2ff51",
    "sample_definition_version": "QC_SAMPLE_SYNTHETIC_V1",
    "sample_definition_sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
    "rule_catalog_sha256": "7d30ad39f1ff40bbfb2224866f869ffd53782e958a94f3e71bf767b35e8d4889",
    "clock_warning": "명시된 가상 +09:00 시각이며 실제 원천의 시간대를 확정하지 않습니다.",
    "missing_policy": "EXPLICIT_SYNTHETIC_SENTINEL_FOR_ABSENT_SLOT; DISPLAY_NULL; NO_INTERPOLATION",
    "ai_status": "NOT_RUN",
    "rule_authority": "CONDITIONAL_SYNTHETIC_CONFIGURATION_NOT_SOURCE_APPROVAL"
   },
   "idempotent_replay": false,
   "result_sha256": "73449674ff3969d99cb484059c5614ab10840e6ad8ca2e0aff59291a2d634250"
  },
  "spike": {
   "schema_version": "qc-sample-detail-1",
   "source": "SAMPLE",
   "is_sample": true,
   "approved": false,
   "transient": true,
   "production_writes": 0,
   "operational_writes": 0,
   "source_reads": 0,
   "model_training": 0,
   "final_qc_writes": 0,
   "restart_erases_state": true,
   "session_id": "qc-sample-session-3wGQD9JJxaHlbO3yZ5YbHS1x",
   "session_revision": 1,
   "generation": 1,
   "window": {
    "source": "SAMPLE",
    "start": "2026-07-09T14:40:00+09:00",
    "end": "2026-07-09T15:40:00+09:00",
    "as_of": "2026-07-09T15:41:20+09:00",
    "clock_basis": "EXPLICIT_SYNTHETIC_OFFSET",
    "offset": "+09:00",
    "granularity": "minute",
    "window_id": "5a89aa21e0bb1e98d95e2d87131560fb9dc37e96f967f4aea8c3d8f11f6ea0f3"
   },
   "case": {
    "case_id": "sample-spike-g1",
    "scenario_id": "spike",
    "label": "Spike · 범위 초과",
    "description": "가상 수온 45도로 급변하여 SP 주의와 GR 범위 초과 BAD가 함께 계산됩니다.",
    "station_id": "SAMPLE-SPIKE",
    "station_name": "샘플 Spike · 범위 초과 관측소",
    "variable_code": "WATER_TEMP",
    "unit": "degree_C",
    "observation_time": "2026-07-09T15:10:00+09:00",
    "value": 45,
    "flag": "4",
    "meaning": "BAD",
    "rule_ids": [
     "GR",
     "SP"
    ],
    "delay_seconds": 1,
    "is_missing": false,
    "revision": 1,
    "recommendation_sha256": "b6365ae1ebf34328a58c678ce58d4c9ea8c40d040f68c5a8d6c194a2d29d16c2",
    "review_status": "PENDING"
   },
   "revision": 1,
   "recommendation_sha256": "b6365ae1ebf34328a58c678ce58d4c9ea8c40d040f68c5a8d6c194a2d29d16c2",
   "series": {
    "rows": [
     {
      "observation_id": "SAMPLE:spike:0",
      "observation_time": "2026-07-09T14:40:00+09:00",
      "value": 20,
      "rule_input_value": 20,
      "source_literal": "20.0",
      "received_time": "2026-07-09T14:40:01+09:00",
      "available_at": "2026-07-09T14:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:1",
      "observation_time": "2026-07-09T14:41:00+09:00",
      "value": 20.054557,
      "rule_input_value": 20.054557,
      "source_literal": "20.054557",
      "received_time": "2026-07-09T14:41:01+09:00",
      "available_at": "2026-07-09T14:41:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "NOT_EVALUATED",
        "reason": "INSUFFICIENT_CAUSAL_WINDOW"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:2",
      "observation_time": "2026-07-09T14:42:00+09:00",
      "value": 20.106485,
      "rule_input_value": 20.106485,
      "source_literal": "20.106485",
      "received_time": "2026-07-09T14:42:01+09:00",
      "available_at": "2026-07-09T14:42:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:3",
      "observation_time": "2026-07-09T14:43:00+09:00",
      "value": 20.153279,
      "rule_input_value": 20.153279,
      "source_literal": "20.153279",
      "received_time": "2026-07-09T14:43:01+09:00",
      "available_at": "2026-07-09T14:43:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:4",
      "observation_time": "2026-07-09T14:44:00+09:00",
      "value": 20.192685,
      "rule_input_value": 20.192685,
      "source_literal": "20.192685",
      "received_time": "2026-07-09T14:44:01+09:00",
      "available_at": "2026-07-09T14:44:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:5",
      "observation_time": "2026-07-09T14:45:00+09:00",
      "value": 20.222802,
      "rule_input_value": 20.222802,
      "source_literal": "20.222802",
      "received_time": "2026-07-09T14:45:01+09:00",
      "available_at": "2026-07-09T14:45:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:6",
      "observation_time": "2026-07-09T14:46:00+09:00",
      "value": 20.242179,
      "rule_input_value": 20.242179,
      "source_literal": "20.242179",
      "received_time": "2026-07-09T14:46:01+09:00",
      "available_at": "2026-07-09T14:46:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:7",
      "observation_time": "2026-07-09T14:47:00+09:00",
      "value": 20.249881,
      "rule_input_value": 20.249881,
      "source_literal": "20.249881",
      "received_time": "2026-07-09T14:47:01+09:00",
      "available_at": "2026-07-09T14:47:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:8",
      "observation_time": "2026-07-09T14:48:00+09:00",
      "value": 20.245539,
      "rule_input_value": 20.245539,
      "source_literal": "20.245539",
      "received_time": "2026-07-09T14:48:01+09:00",
      "available_at": "2026-07-09T14:48:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:9",
      "observation_time": "2026-07-09T14:49:00+09:00",
      "value": 20.229359,
      "rule_input_value": 20.229359,
      "source_literal": "20.229359",
      "received_time": "2026-07-09T14:49:01+09:00",
      "available_at": "2026-07-09T14:49:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:10",
      "observation_time": "2026-07-09T14:50:00+09:00",
      "value": 20.202124,
      "rule_input_value": 20.202124,
      "source_literal": "20.202124",
      "received_time": "2026-07-09T14:50:01+09:00",
      "available_at": "2026-07-09T14:50:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:11",
      "observation_time": "2026-07-09T14:51:00+09:00",
      "value": 20.165145,
      "rule_input_value": 20.165145,
      "source_literal": "20.165145",
      "received_time": "2026-07-09T14:51:01+09:00",
      "available_at": "2026-07-09T14:51:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:12",
      "observation_time": "2026-07-09T14:52:00+09:00",
      "value": 20.120206,
      "rule_input_value": 20.120206,
      "source_literal": "20.120206",
      "received_time": "2026-07-09T14:52:01+09:00",
      "available_at": "2026-07-09T14:52:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:13",
      "observation_time": "2026-07-09T14:53:00+09:00",
      "value": 20.069471,
      "rule_input_value": 20.069471,
      "source_literal": "20.069471",
      "received_time": "2026-07-09T14:53:01+09:00",
      "available_at": "2026-07-09T14:53:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:14",
      "observation_time": "2026-07-09T14:54:00+09:00",
      "value": 20.015388,
      "rule_input_value": 20.015388,
      "source_literal": "20.015388",
      "received_time": "2026-07-09T14:54:01+09:00",
      "available_at": "2026-07-09T14:54:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:15",
      "observation_time": "2026-07-09T14:55:00+09:00",
      "value": 19.960564,
      "rule_input_value": 19.960564,
      "source_literal": "19.960564",
      "received_time": "2026-07-09T14:55:01+09:00",
      "available_at": "2026-07-09T14:55:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:16",
      "observation_time": "2026-07-09T14:56:00+09:00",
      "value": 19.90764,
      "rule_input_value": 19.90764,
      "source_literal": "19.90764",
      "received_time": "2026-07-09T14:56:01+09:00",
      "available_at": "2026-07-09T14:56:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:17",
      "observation_time": "2026-07-09T14:57:00+09:00",
      "value": 19.859168,
      "rule_input_value": 19.859168,
      "source_literal": "19.859168",
      "received_time": "2026-07-09T14:57:01+09:00",
      "available_at": "2026-07-09T14:57:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:18",
      "observation_time": "2026-07-09T14:58:00+09:00",
      "value": 19.817485,
      "rule_input_value": 19.817485,
      "source_literal": "19.817485",
      "received_time": "2026-07-09T14:58:01+09:00",
      "available_at": "2026-07-09T14:58:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:19",
      "observation_time": "2026-07-09T14:59:00+09:00",
      "value": 19.784601,
      "rule_input_value": 19.784601,
      "source_literal": "19.784601",
      "received_time": "2026-07-09T14:59:01+09:00",
      "available_at": "2026-07-09T14:59:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:20",
      "observation_time": "2026-07-09T15:00:00+09:00",
      "value": 19.762099,
      "rule_input_value": 19.762099,
      "source_literal": "19.762099",
      "received_time": "2026-07-09T15:00:01+09:00",
      "available_at": "2026-07-09T15:00:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:21",
      "observation_time": "2026-07-09T15:01:00+09:00",
      "value": 19.751066,
      "rule_input_value": 19.751066,
      "source_literal": "19.751066",
      "received_time": "2026-07-09T15:01:01+09:00",
      "available_at": "2026-07-09T15:01:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:22",
      "observation_time": "2026-07-09T15:02:00+09:00",
      "value": 19.752033,
      "rule_input_value": 19.752033,
      "source_literal": "19.752033",
      "received_time": "2026-07-09T15:02:01+09:00",
      "available_at": "2026-07-09T15:02:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:23",
      "observation_time": "2026-07-09T15:03:00+09:00",
      "value": 19.764953,
      "rule_input_value": 19.764953,
      "source_literal": "19.764953",
      "received_time": "2026-07-09T15:03:01+09:00",
      "available_at": "2026-07-09T15:03:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:24",
      "observation_time": "2026-07-09T15:04:00+09:00",
      "value": 19.789203,
      "rule_input_value": 19.789203,
      "source_literal": "19.789203",
      "received_time": "2026-07-09T15:04:01+09:00",
      "available_at": "2026-07-09T15:04:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:25",
      "observation_time": "2026-07-09T15:05:00+09:00",
      "value": 19.823615,
      "rule_input_value": 19.823615,
      "source_literal": "19.823615",
      "received_time": "2026-07-09T15:05:01+09:00",
      "available_at": "2026-07-09T15:05:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:26",
      "observation_time": "2026-07-09T15:06:00+09:00",
      "value": 19.866529,
      "rule_input_value": 19.866529,
      "source_literal": "19.866529",
      "received_time": "2026-07-09T15:06:01+09:00",
      "available_at": "2026-07-09T15:06:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:27",
      "observation_time": "2026-07-09T15:07:00+09:00",
      "value": 19.915878,
      "rule_input_value": 19.915878,
      "source_literal": "19.915878",
      "received_time": "2026-07-09T15:07:01+09:00",
      "available_at": "2026-07-09T15:07:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:28",
      "observation_time": "2026-07-09T15:08:00+09:00",
      "value": 19.969282,
      "rule_input_value": 19.969282,
      "source_literal": "19.969282",
      "received_time": "2026-07-09T15:08:01+09:00",
      "available_at": "2026-07-09T15:08:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:29",
      "observation_time": "2026-07-09T15:09:00+09:00",
      "value": 20.024166,
      "rule_input_value": 20.024166,
      "source_literal": "20.024166",
      "received_time": "2026-07-09T15:09:01+09:00",
      "available_at": "2026-07-09T15:09:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:30",
      "observation_time": "2026-07-09T15:10:00+09:00",
      "value": 45,
      "rule_input_value": 45,
      "source_literal": "45.0",
      "received_time": "2026-07-09T15:10:01+09:00",
      "available_at": "2026-07-09T15:10:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "4",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "4",
        "reason": "LIMIT_EXCEEDED"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "3",
        "reason": "LIMIT_EXCEEDED"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:31",
      "observation_time": "2026-07-09T15:11:00+09:00",
      "value": 20.12785,
      "rule_input_value": 20.12785,
      "source_literal": "20.12785",
      "received_time": "2026-07-09T15:11:01+09:00",
      "available_at": "2026-07-09T15:11:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "3",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "3",
        "reason": "LIMIT_EXCEEDED"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:32",
      "observation_time": "2026-07-09T15:12:00+09:00",
      "value": 20.171652,
      "rule_input_value": 20.171652,
      "source_literal": "20.171652",
      "received_time": "2026-07-09T15:12:01+09:00",
      "available_at": "2026-07-09T15:12:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:33",
      "observation_time": "2026-07-09T15:13:00+09:00",
      "value": 20.20718,
      "rule_input_value": 20.20718,
      "source_literal": "20.20718",
      "received_time": "2026-07-09T15:13:01+09:00",
      "available_at": "2026-07-09T15:13:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:34",
      "observation_time": "2026-07-09T15:14:00+09:00",
      "value": 20.23272,
      "rule_input_value": 20.23272,
      "source_literal": "20.23272",
      "received_time": "2026-07-09T15:14:01+09:00",
      "available_at": "2026-07-09T15:14:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:35",
      "observation_time": "2026-07-09T15:15:00+09:00",
      "value": 20.247042,
      "rule_input_value": 20.247042,
      "source_literal": "20.247042",
      "received_time": "2026-07-09T15:15:01+09:00",
      "available_at": "2026-07-09T15:15:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:36",
      "observation_time": "2026-07-09T15:16:00+09:00",
      "value": 20.249455,
      "rule_input_value": 20.249455,
      "source_literal": "20.249455",
      "received_time": "2026-07-09T15:16:01+09:00",
      "available_at": "2026-07-09T15:16:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:37",
      "observation_time": "2026-07-09T15:17:00+09:00",
      "value": 20.239844,
      "rule_input_value": 20.239844,
      "source_literal": "20.239844",
      "received_time": "2026-07-09T15:17:01+09:00",
      "available_at": "2026-07-09T15:17:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:38",
      "observation_time": "2026-07-09T15:18:00+09:00",
      "value": 20.21867,
      "rule_input_value": 20.21867,
      "source_literal": "20.21867",
      "received_time": "2026-07-09T15:18:01+09:00",
      "available_at": "2026-07-09T15:18:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:39",
      "observation_time": "2026-07-09T15:19:00+09:00",
      "value": 20.186956,
      "rule_input_value": 20.186956,
      "source_literal": "20.186956",
      "received_time": "2026-07-09T15:19:01+09:00",
      "available_at": "2026-07-09T15:19:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:40",
      "observation_time": "2026-07-09T15:20:00+09:00",
      "value": 20.146229,
      "rule_input_value": 20.146229,
      "source_literal": "20.146229",
      "received_time": "2026-07-09T15:20:01+09:00",
      "available_at": "2026-07-09T15:20:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:41",
      "observation_time": "2026-07-09T15:21:00+09:00",
      "value": 20.098454,
      "rule_input_value": 20.098454,
      "source_literal": "20.098454",
      "received_time": "2026-07-09T15:21:01+09:00",
      "available_at": "2026-07-09T15:21:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:42",
      "observation_time": "2026-07-09T15:22:00+09:00",
      "value": 20.045932,
      "rule_input_value": 20.045932,
      "source_literal": "20.045932",
      "received_time": "2026-07-09T15:22:01+09:00",
      "available_at": "2026-07-09T15:22:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:43",
      "observation_time": "2026-07-09T15:23:00+09:00",
      "value": 19.991196,
      "rule_input_value": 19.991196,
      "source_literal": "19.991196",
      "received_time": "2026-07-09T15:23:01+09:00",
      "available_at": "2026-07-09T15:23:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:44",
      "observation_time": "2026-07-09T15:24:00+09:00",
      "value": 19.936885,
      "rule_input_value": 19.936885,
      "source_literal": "19.936885",
      "received_time": "2026-07-09T15:24:01+09:00",
      "available_at": "2026-07-09T15:24:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:45",
      "observation_time": "2026-07-09T15:25:00+09:00",
      "value": 19.885616,
      "rule_input_value": 19.885616,
      "source_literal": "19.885616",
      "received_time": "2026-07-09T15:25:01+09:00",
      "available_at": "2026-07-09T15:25:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:46",
      "observation_time": "2026-07-09T15:26:00+09:00",
      "value": 19.839861,
      "rule_input_value": 19.839861,
      "source_literal": "19.839861",
      "received_time": "2026-07-09T15:26:01+09:00",
      "available_at": "2026-07-09T15:26:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:47",
      "observation_time": "2026-07-09T15:27:00+09:00",
      "value": 19.801826,
      "rule_input_value": 19.801826,
      "source_literal": "19.801826",
      "received_time": "2026-07-09T15:27:01+09:00",
      "available_at": "2026-07-09T15:27:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:48",
      "observation_time": "2026-07-09T15:28:00+09:00",
      "value": 19.773343,
      "rule_input_value": 19.773343,
      "source_literal": "19.773343",
      "received_time": "2026-07-09T15:28:01+09:00",
      "available_at": "2026-07-09T15:28:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:49",
      "observation_time": "2026-07-09T15:29:00+09:00",
      "value": 19.755787,
      "rule_input_value": 19.755787,
      "source_literal": "19.755787",
      "received_time": "2026-07-09T15:29:01+09:00",
      "available_at": "2026-07-09T15:29:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:50",
      "observation_time": "2026-07-09T15:30:00+09:00",
      "value": 19.750002,
      "rule_input_value": 19.750002,
      "source_literal": "19.750002",
      "received_time": "2026-07-09T15:30:01+09:00",
      "available_at": "2026-07-09T15:30:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:51",
      "observation_time": "2026-07-09T15:31:00+09:00",
      "value": 19.756269,
      "rule_input_value": 19.756269,
      "source_literal": "19.756269",
      "received_time": "2026-07-09T15:31:01+09:00",
      "available_at": "2026-07-09T15:31:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:52",
      "observation_time": "2026-07-09T15:32:00+09:00",
      "value": 19.774286,
      "rule_input_value": 19.774286,
      "source_literal": "19.774286",
      "received_time": "2026-07-09T15:32:01+09:00",
      "available_at": "2026-07-09T15:32:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:53",
      "observation_time": "2026-07-09T15:33:00+09:00",
      "value": 19.803182,
      "rule_input_value": 19.803182,
      "source_literal": "19.803182",
      "received_time": "2026-07-09T15:33:01+09:00",
      "available_at": "2026-07-09T15:33:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:54",
      "observation_time": "2026-07-09T15:34:00+09:00",
      "value": 19.841567,
      "rule_input_value": 19.841567,
      "source_literal": "19.841567",
      "received_time": "2026-07-09T15:34:01+09:00",
      "available_at": "2026-07-09T15:34:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:55",
      "observation_time": "2026-07-09T15:35:00+09:00",
      "value": 19.887588,
      "rule_input_value": 19.887588,
      "source_literal": "19.887588",
      "received_time": "2026-07-09T15:35:01+09:00",
      "available_at": "2026-07-09T15:35:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:56",
      "observation_time": "2026-07-09T15:36:00+09:00",
      "value": 19.939029,
      "rule_input_value": 19.939029,
      "source_literal": "19.939029",
      "received_time": "2026-07-09T15:36:01+09:00",
      "available_at": "2026-07-09T15:36:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:57",
      "observation_time": "2026-07-09T15:37:00+09:00",
      "value": 19.993408,
      "rule_input_value": 19.993408,
      "source_literal": "19.993408",
      "received_time": "2026-07-09T15:37:01+09:00",
      "available_at": "2026-07-09T15:37:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:58",
      "observation_time": "2026-07-09T15:38:00+09:00",
      "value": 20.048105,
      "rule_input_value": 20.048105,
      "source_literal": "20.048105",
      "received_time": "2026-07-09T15:38:01+09:00",
      "available_at": "2026-07-09T15:38:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:59",
      "observation_time": "2026-07-09T15:39:00+09:00",
      "value": 20.100484,
      "rule_input_value": 20.100484,
      "source_literal": "20.100484",
      "received_time": "2026-07-09T15:39:01+09:00",
      "available_at": "2026-07-09T15:39:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     },
     {
      "observation_id": "SAMPLE:spike:60",
      "observation_time": "2026-07-09T15:40:00+09:00",
      "value": 20.148018,
      "rule_input_value": 20.148018,
      "source_literal": "20.148018",
      "received_time": "2026-07-09T15:40:01+09:00",
      "available_at": "2026-07-09T15:40:01+09:00",
      "delay_seconds": 1,
      "is_missing": false,
      "is_late": false,
      "observed": true,
      "record_kind": "SYNTHETIC_OBSERVATION",
      "interpolated": false,
      "flag": "1",
      "rule_flags": [
       {
        "rule_id": "WT",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "LO",
        "flag": "NOT_EVALUATED",
        "reason": "LOCATION_REQUIRED"
       },
       {
        "rule_id": "ER",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GR",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "GD",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RL",
        "flag": "NOT_EVALUATED",
        "reason": "NOT_APPLICABLE_IN_TABLE_2_9"
       },
       {
        "rule_id": "SP",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "RR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "SR",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "ST",
        "flag": "NOT_EVALUATED",
        "reason": "PAST_BASELINE_REQUIRED"
       },
       {
        "rule_id": "DE",
        "flag": "1",
        "reason": "WITHIN_CONFIGURED_TEST"
       },
       {
        "rule_id": "PO",
        "flag": "NOT_EVALUATED",
        "reason": "RELATED_OBSERVATION_REQUIRED"
       }
      ]
     }
    ],
    "unit": "degree_C",
    "cadence_seconds": 60,
    "planned_slots": 61,
    "received_slots": 61,
    "missing_slots": 0,
    "interpolated": false
   },
   "rules": [
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "LOCATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": 40,
     "result_flag": "4",
     "evaluation_status": "EVALUATED",
     "result_reason": "LIMIT_EXCEEDED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": 120,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "NOT_APPLICABLE_IN_TABLE_2_9",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": 1,
     "result_flag": "3",
     "evaluation_status": "EVALUATED",
     "result_reason": "LIMIT_EXCEEDED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "PAST_BASELINE_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": 300,
     "result_flag": "1",
     "evaluation_status": "EVALUATED",
     "result_reason": "WITHIN_CONFIGURED_TEST",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    },
    {
     "observation_id": "SAMPLE:spike:30",
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "scope": {
      "station_id": "SAMPLE-SPIKE",
      "sensor_id": "SAMPLE-SPIKE-CHANNEL",
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "sensor_episode_id": "SAMPLE-SPIKE-EPISODE"
     },
     "event_at": "2026-07-09T15:10:00+09:00",
     "available_at": "2026-07-09T06:41:20+00:00",
     "input_value": 45,
     "threshold_value": null,
     "result_flag": "NOT_EVALUATED",
     "evaluation_status": "NOT_EVALUATED",
     "result_reason": "RELATED_OBSERVATION_REQUIRED",
     "result_score": null,
     "provenance_json": {
      "ui_fixture_original_provenance_omitted": true
     },
     "approved": false,
     "analysis_only": true
    }
   ],
   "rule_specs": [
    {
     "qc_rule_id": "QC-SAMPLE-WT",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "WT",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-LO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "LO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ER",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ER",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "sentinels": [
       -999
      ]
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "min": 0,
      "max": 40,
      "boundary": "CLOSED"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-GD",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "GD",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "duration_seconds": 120,
      "interval_seconds": 60,
      "duration_boundary": "AT_LEAST"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RL",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RL",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SP",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SP",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "interval_seconds": 60,
      "max_delta": 1,
      "difference": "LINEAR"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-RR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "RR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-SR",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "SR",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-ST",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "ST",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    },
    {
     "qc_rule_id": "QC-SAMPLE-DE",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "DE",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3",
      "max_delay_seconds": 300
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": true,
     "unconfigured_reason": null
    },
    {
     "qc_rule_id": "QC-SAMPLE-PO",
     "rule_version": "QC_SAMPLE_SYNTHETIC_V1",
     "kind": "PO",
     "parameters": {
      "variable_code": "WATER_TEMP",
      "unit": "degree_C",
      "quantity_kind": "WATER_TEMP_SCALAR",
      "missing_sentinels": [
       -999
      ],
      "calendar_timezone": "UTC",
      "failure_flag": "3"
     },
     "provenance": {
      "guide_sha256": "d1fd062b7f7313d6dee585692a20665cb4dd724a16008ccdae5ddf250054c9d9",
      "pdf_pages": [
       23,
       81
      ],
      "profile_id": "EXPLICIT_SYNTHETIC_TEST_CONFIGURATION",
      "configuration_reference": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      },
      "conflict_resolution": {
       "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
       "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
      }
     },
     "sample_configured": false,
     "unconfigured_reason": "SAMPLE_RELATED_OR_HISTORICAL_EVIDENCE_NOT_SUPPLIED"
    }
   ],
   "equipment": {
    "source": "SAMPLE",
    "synthetic": true,
    "station_id": "SAMPLE-SPIKE",
    "physical_sensor_id": "SAMPLE-SPIKE-SENSOR",
    "sensor_episode_id": "SAMPLE-SPIKE-EPISODE",
    "label": "가상 수온 센서",
    "unit": "degree_C"
   },
   "source_facts": {
    "physical_sensor_id": "SAMPLE-SPIKE-SENSOR",
    "sensor_episode_id": "SAMPLE-SPIKE-EPISODE",
    "quantity_kind": "WATER_TEMP_SCALAR",
    "clock_semantics": "EXPLICIT_SYNTHETIC_OFFSET",
    "source_timezone_name": "Etc/GMT-9",
    "effective_start": "2026-07-09T13:40:00+09:00",
    "effective_end": "2026-07-09T16:40:00+09:00",
    "available_at": "2026-07-09T14:39:00+09:00",
    "version_available_at": "2026-07-09T14:39:00+09:00",
    "evidence": {
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "locator": "SAMPLE:QC_SAMPLE_SYNTHETIC_V1:GENERATED_NO_REAL_SOURCE"
    }
   },
   "evidence": [
    {
     "kind": "SYNTHETIC_SOURCE_CONTRACT",
     "source": "SAMPLE",
     "label": "명시된 가상 원천·센서 계약",
     "sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
     "description": "실제 원천·계정·승인과 관계없는 고정 샘플 정의입니다."
    },
    {
     "kind": "ACTUAL_RULE_EXECUTION",
     "source": "SAMPLE",
     "label": "기존 Rule 엔진 계산 결과",
     "sha256": "5efaf85e1d5d835f1742ae94668afe349b512de234069859d07b5198e1040607",
     "description": "WT/ER/GR/GD/SP/DE는 가상 설정으로 계산합니다. 다른 Rule의 관련·과거 근거는 제공하지 않았으며, 결측 sentinel 선행 검사 9는 과거 baseline 검사 완료를 뜻하지 않습니다."
    }
   ],
   "ai": {
    "status": "NOT_RUN",
    "trained_model": false,
    "result": null
   },
   "workflow": {
    "status": "PENDING",
    "blocked": true,
    "downstream_executed": false,
    "approved": false,
    "definitive_qc": false,
    "history": [
     {
      "sequence": 1,
      "action": "CREATE",
      "from_state": null,
      "to_state": "PENDING",
      "comment": "샘플 검토가 필요하여 후속 단계에서 정지했습니다.",
      "actor": "SAMPLE_ENGINE",
      "sample_clock": "2026-07-09T15:41:20+09:00"
     }
    ],
    "revision": 1,
    "recommendation_sha256": "b6365ae1ebf34328a58c678ce58d4c9ea8c40d040f68c5a8d6c194a2d29d16c2",
    "capabilities": {
     "comment": true,
     "approve": true,
     "hold": true,
     "reject": true,
     "resume": false
    }
   },
   "provenance": {
    "source": "SAMPLE",
    "is_sample": true,
    "approved": false,
    "transient": true,
    "production_writes": 0,
    "operational_writes": 0,
    "source_reads": 0,
    "model_training": 0,
    "final_qc_writes": 0,
    "restart_erases_state": true,
    "rule_engine_version": "guide-existing-12-v1",
    "rule_implementation_sha256": "9993072a38e264808c828a93a460908bef59a6e9e8d58cdc11198425eef2ff51",
    "sample_definition_version": "QC_SAMPLE_SYNTHETIC_V1",
    "sample_definition_sha256": "7f865fa666589228235538dc9e68535129451a9e3152fa4aa3ba83a1657007e7",
    "rule_catalog_sha256": "7d30ad39f1ff40bbfb2224866f869ffd53782e958a94f3e71bf767b35e8d4889",
    "clock_warning": "명시된 가상 +09:00 시각이며 실제 원천의 시간대를 확정하지 않습니다.",
    "missing_policy": "EXPLICIT_SYNTHETIC_SENTINEL_FOR_ABSENT_SLOT; DISPLAY_NULL; NO_INTERPOLATION",
    "ai_status": "NOT_RUN",
    "rule_authority": "CONDITIONAL_SYNTHETIC_CONFIGURATION_NOT_SOURCE_APPROVAL"
   },
   "idempotent_replay": false,
   "result_sha256": "d4820c3d181e3ce595fec90c9c2c719b974b16d37445b2c2d8823abea27dd7f3"
  }
 }
};
