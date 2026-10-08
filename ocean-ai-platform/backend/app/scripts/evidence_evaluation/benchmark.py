"""모델 제공자와 독립적인 평가 지표. 검토된 정답·실측 시간·비용 입력만 평가한다."""
import math
import statistics


PROTOCOLS = {
 'forecast': {
  'candidate_families': ['persistence', 'seasonal_naive', 'ridge', 'tree_boosting', 'sequence_model'],
  'metrics': ['mae', 'rmse', 'skill_vs_baseline', 'station_item_macro_mae'],
  'split': 'chronological train/validation/test; label horizon embargo; separate unseen-station evaluation',
  'must': ['approved_dataset', 'unit_specific_scores', 'frozen_horizon', 'baseline', 'no_test_tuning'],
 },
 'anomaly_detection': {
  'candidate_families': ['approved_qc_rules', 'robust_statistics', 'isolation_method', 'supervised_classifier'],
  'metrics': ['precision', 'recall', 'f1', 'false_positive_rate', 'event_recall', 'false_alarms_per_day', 'detection_delay'],
  'split': 'chronological and event grouped; threshold selected on validation only',
  'must': ['approved_labels', 'negative_period_review', 'event_definition', 'critical_event_recall_floor'],
 },
 'retrieval': {
  'candidate_families': ['lexical', 'existing_embedding', 'hybrid', 'hybrid_reranker'],
  'metrics': ['recall_at_k', 'mrr_at_k', 'ndcg_at_k', 'no_answer_behavior'],
  'split': 'hold out document families/editions and query templates; freeze corpus and relevance judgements',
  'must': ['reviewed_qrels', 'corpus_hash', 'model_digest', 'fixed_filters_and_k', 'no_answer_queries'],
 },
 'report_generation': {
  'candidate_families': ['evidence_template', 'local_llm', 'hosted_llm'],
  'metrics': ['supported_claim_rate', 'citation_precision', 'required_fact_coverage', 'unsupported_claims', 'review_minutes'],
  'split': 'held-out station periods/documents; shared evidence packet and rubric; blind review',
  'must': ['reviewed_claims', 'source_page_verification', 'numeric_date_checks', 'uncertainty_preservation', 'human_review'],
 },
}


def finite(values):
    values = list(values)
    if not values or any(not math.isfinite(float(v)) for v in values):
        raise ValueError('EMPTY_OR_NONFINITE')
    return values


def forecast(actual, predicted, baseline):
    actual, predicted, baseline = map(finite, (actual, predicted, baseline))
    if len({len(actual), len(predicted), len(baseline)}) != 1:
        raise ValueError('LENGTH_MISMATCH')
    mae = statistics.mean(abs(a-p) for a,p in zip(actual,predicted))
    base = statistics.mean(abs(a-b) for a,b in zip(actual,baseline))
    return {'mae': mae, 'rmse': math.sqrt(statistics.mean((a-p)**2 for a,p in zip(actual,predicted))),
            'baseline_mae': base, 'skill_vs_baseline': 1-mae/base if base else None}


def classification(actual, predicted):
    if not actual or len(actual) != len(predicted) or any(x not in (0,1) for x in actual+predicted):
        raise ValueError('INVALID_BINARY_LABELS')
    tp=sum(a==p==1 for a,p in zip(actual,predicted)); fp=sum(a==0 and p==1 for a,p in zip(actual,predicted))
    fn=sum(a==1 and p==0 for a,p in zip(actual,predicted)); tn=sum(a==p==0 for a,p in zip(actual,predicted))
    return {'tp':tp,'fp':fp,'fn':fn,'tn':tn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'false_positive_rate':fp/(fp+tn) if fp+tn else None}


def retrieval(ranking, relevant, k):
    if k < 1 or len(ranking) != len(set(ranking)):
        raise ValueError('INVALID_RANKING')
    relevant=set(relevant)
    if not relevant:
        return {'recall_at_k':None,'mrr_at_k':None,'ndcg_at_k':None,'status':'NO_ANSWER_CASE_REVIEW_REQUIRED'}
    hits=[i+1 for i,x in enumerate(ranking[:k]) if x in relevant]
    dcg=sum(1/math.log2(i+1) for i in hits)
    ideal=sum(1/math.log2(i+1) for i in range(1,min(k,len(relevant))+1))
    return {'recall_at_k':len(hits)/len(relevant),'mrr_at_k':1/hits[0] if hits else 0,'ndcg_at_k':dcg/ideal}


def report_quality(review):
    # 모델의 자기평가를 근거 충실도 점수로 사용하지 않는다.
    if review.get('status')!='REVIEWED' or not review.get('reviewer'):
        raise ValueError('HUMAN_REVIEW_REQUIRED')
    for num, den in [('supported_claims','claims'),('valid_citations','citations'),('covered_facts','required_facts')]:
        if not isinstance(review.get(num),int) or not isinstance(review.get(den),int) or not 0<=review[num]<=review[den]:
            raise ValueError('INVALID_REVIEW_COUNTS')
    ratio=lambda a,b:review[a]/review[b] if review[b] else None
    return {'supported_claim_rate':ratio('supported_claims','claims'),
            'citation_precision':ratio('valid_citations','citations'),
            'required_fact_coverage':ratio('covered_facts','required_facts'),
            'unsupported_claims':review['claims']-review['supported_claims']}


def resources(latency_ms, *, billed_cost=None, currency=None, measured_kwh=None, tariff=None):
    lat=sorted(finite(latency_ms))
    if min(lat)<0 or any(x is not None and (not math.isfinite(x) or x<0) for x in (billed_cost,measured_kwh,tariff)):
        raise ValueError('INVALID_RESOURCE_MEASUREMENT')
    if billed_cost is not None and not currency:
        raise ValueError('CURRENCY_REQUIRED')
    if (measured_kwh is None) != (tariff is None):
        raise ValueError('ENERGY_AND_TARIFF_REQUIRED_TOGETHER')
    if tariff is not None and not currency:
        raise ValueError('CURRENCY_REQUIRED')
    return {'samples':len(lat),'latency_p50_ms':statistics.median(lat),
            'latency_p95_ms':lat[math.ceil(.95*len(lat))-1],
            'billed_cost':billed_cost,'currency':currency,
            'electricity_cost':measured_kwh*tariff if measured_kwh is not None else None,
            'cost_scope':'provider charge and measured electricity only; hardware/labor excluded',
            'cost_status':'UNMEASURED' if billed_cost is None and measured_kwh is None else 'PARTIAL_MEASURED'}


def selection_gate(candidate, requirements):
    """사용자가 정한 품질·지연·비용 한계를 통과한 후보만 비교 가능. 임의 최종 선정 금지."""
    errors=[]
    for key in ('dataset_hash','protocol_hash','model_digest','hardware','metrics'):
        if not candidate.get(key): errors.append('MISSING_'+key.upper())
    if candidate.get('dataset_status')!='APPROVED': errors.append('DATASET_NOT_APPROVED')
    if candidate.get('split_validation')!='PASS': errors.append('SPLIT_NOT_VALIDATED')
    if not requirements: errors.append('ACCEPTANCE_LIMITS_NOT_SET')
    for metric, limits in requirements.items():
        val=candidate.get('metrics',{}).get(metric)
        if val is None or not isinstance(val,(int,float)) or not math.isfinite(val):
            errors.append('MISSING_METRIC:'+metric);continue
        if 'min' in limits and val<limits['min']: errors.append('BELOW_MIN:'+metric)
        if 'max' in limits and val>limits['max']: errors.append('ABOVE_MAX:'+metric)
    return {'status':'ELIGIBLE_FOR_REVIEW' if not errors else 'BLOCKED','reasons':errors}
