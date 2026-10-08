"""공통 평가셋에서 얻은 후보별 예측/순위/검토 결과를 같은 기준으로 채점한다.

모델 호출과 별도이므로 로컬/원격 어느 공급자의 실제 측정 결과도 사용할 수 있다.
검토 전 데이터셋은 점수 산출 및 모델 순위 비교를 거부한다.
"""
import argparse
import json
from pathlib import Path
from benchmark import forecast,classification,retrieval,report_quality,resources,selection_gate
from temporal import digest


def evaluate(packet):
    dataset=packet['dataset'];protocol=packet['protocol']
    if dataset.get('status')!='APPROVED' or not dataset.get('reviewer_reference'):
        raise ValueError('DATASET_APPROVAL_REQUIRED')
    if not dataset.get('membership_hash') or dataset.get('split_validation')!='PASS':
        raise ValueError('FROZEN_MEMBERSHIP_AND_VALID_SPLIT_REQUIRED')
    if not dataset.get('test_case_ids') or not packet.get('candidates'):
        raise ValueError('EMPTY_EVALUATION')
    if not protocol.get('requirements'):
        raise ValueError('ACCEPTANCE_LIMITS_REQUIRED')
    task=protocol['task'];result=[]
    common=packet['reference']
    for candidate in packet['candidates']:
        if not candidate.get('model_digest') or not candidate.get('hardware'):
            raise ValueError('MODEL_AND_HARDWARE_IDENTITY_REQUIRED')
        if candidate.get('test_case_ids')!=dataset['test_case_ids']:
            raise ValueError('TEST_MEMBERSHIP_MISMATCH')
        if len(set(candidate['test_case_ids']))!=len(candidate['test_case_ids']):
            raise ValueError('DUPLICATE_TEST_ID')
        output=candidate['output']
        if task=='forecast':
            if len(output)!=len(dataset['test_case_ids']):raise ValueError('ROW_COUNT_MISMATCH')
            if not protocol.get('unit') or not protocol.get('horizon_seconds'):raise ValueError('UNIT_HORIZON_REQUIRED')
            scores=forecast(common['actual'],output,common['baseline'])
        elif task=='anomaly_detection':
            if len(output)!=len(dataset['test_case_ids']):raise ValueError('ROW_COUNT_MISMATCH')
            scores=classification(common['actual'],output)
        elif task=='retrieval':
            if set(output)!=set(dataset['test_case_ids']) or set(common['qrels'])!=set(output):raise ValueError('QUERY_SET_MISMATCH')
            per_query={qid:retrieval(output[qid],common['qrels'][qid],protocol['k']) for qid in output}
            scores={}
            for key in ('recall_at_k','mrr_at_k','ndcg_at_k'):
                vals=[r[key] for r in per_query.values() if r[key] is not None]
                scores[key]=sum(vals)/len(vals) if vals else None
            scores['no_answer_cases']=sum(not common['qrels'][q] for q in output)
        elif task=='report_generation':
            if set(output)!=set(dataset['test_case_ids']):raise ValueError('REPORT_CASE_MISMATCH')
            scored=[report_quality(output[q]) for q in dataset['test_case_ids']]
            scores={k:sum(x[k] for x in scored if x[k] is not None)/sum(x[k] is not None for x in scored)
                    if any(x[k] is not None for x in scored) else None for k in scored[0]}
            scores['unsupported_claims']=sum(x['unsupported_claims'] for x in scored)
        else:raise ValueError('UNKNOWN_TASK')
        measurement=candidate['measurement']
        if len(measurement['latency_ms'])!=len(dataset['test_case_ids']):raise ValueError('MEASUREMENT_COUNT_MISMATCH')
        cost=resources(**measurement)
        scores.update({k:v for k,v in cost.items() if k.startswith('latency_')})
        scores['billed_cost']=cost['billed_cost']
        contract={'dataset_hash':digest(dataset),'protocol_hash':digest(protocol),
                  'model_digest':candidate['model_digest'],'hardware':candidate['hardware'],
                  'dataset_status':dataset['status'],'split_validation':dataset['split_validation'],'metrics':scores}
        result.append({'candidate':candidate['name'],**contract,'resources':cost,
                       'selection_gate':selection_gate(contract,protocol['requirements'])})
    return {'task':task,'status':'SCORED_NOT_OPERATIONALLY_APPROVED','candidates':result,
            'note':'No automatic winner. Compare eligible candidates on quality, latency and measured cost; obtain operational review.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=evaluate(json.loads(a.input.read_text(encoding='utf8')))
    with a.output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
