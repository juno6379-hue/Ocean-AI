import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

// Use the existing compiler so the Node 20 container does not need native TS loading.
const source = readFileSync(new URL('../src/data/observationPeriod.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { CURRENT_OBSERVATION_MONTH, observationPeriod, observationContext,
  selectObservationSource, currentObservationPeriod, applyObservationPeriod } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('period apply commits both dates atomically and retains the selected station/scope',()=>{
  const current=new URLSearchParams('source=GD_OBS_BU&sea=S&station=TW_1&from=2026-07&to=2026-07');
  const next=applyObservationPeriod(current,'2022-12','2023-01');
  assert.equal(next.get('from'),'2022-12');assert.equal(next.get('to'),'2023-01');
  assert.equal(next.get('source'),'GD_OBS_BU');assert.equal(next.get('sea'),'S');assert.equal(next.get('station'),'TW_1');
  assert.equal(current.get('from'),'2026-07');
});
test('invalid and reversed period edits cannot replace the current displayed scope',()=>{
  const current=new URLSearchParams('from=2026-07&to=2026-07');
  for(const [from,to] of [['','2026-07'],['2026-13','2026-14'],['2026-08','2026-07'],['0000-01','2026-07']])
    assert.equal(applyObservationPeriod(current,from,to),null);
  assert.equal(current.get('from'),'2026-07');
});

test('monthly observation sources default to the July 2026 single month', () => {
  for (const source of ['', 'GD_OBS_ST_MONTHLY', 'GD_OBS_BU', 'GD_OBS_VBU', 'GR_OBS_ST']) {
    const period = observationPeriod(new URLSearchParams(source ? { source } : {}));
    assert.equal(period.from, '2026-07');
    assert.equal(period.to, '2026-07');
    assert.equal(period.isHistorical, false);
  }
});

test('an explicit period survives source changes and unrelated filters are retained', () => {
  const original = new URLSearchParams('from=2023-04&to=2024-08&source=GD_OBS_BU&network=N&sea=S&station=OLD&item=OLD&tab=raw');
  const next = selectObservationSource(original, 'GR_OBS_ST');
  assert.deepEqual(observationPeriod(next), { source: 'GR_OBS_ST', from: '2023-04', to: '2024-08', isHistorical: false });
  assert.equal(next.get('network'), 'N');
  assert.equal(next.get('sea'), 'S');
  assert.equal(next.get('tab'), 'raw');
  assert.equal(next.has('station'), false);
  assert.equal(next.has('item'), false);
  assert.equal(original.get('source'), 'GD_OBS_BU');
  assert.equal(original.get('station'), 'OLD');
});

test('explicit history selection retains the existing historical default and explicit overrides', () => {
  const period = observationPeriod(new URLSearchParams('source=HISTORICAL_RECONCILED'));
  assert.deepEqual(period, { source: 'HISTORICAL_RECONCILED', from: '2011-01', to: '2021-12', isHistorical: true });
  const overridden = observationPeriod(new URLSearchParams('source=HISTORICAL_RECONCILED&from=2014-03&to=2017-09'));
  assert.equal(overridden.from, '2014-03');
  assert.equal(overridden.to, '2017-09');
});

test('a source switch with no period uses the destination default instead of materializing a cumulative range', () => {
  const history = selectObservationSource(new URLSearchParams('sea=E'), 'HISTORICAL_RECONCILED');
  assert.equal(history.has('from'), false);
  assert.equal(observationPeriod(history).from, '2011-01');
  const monthly = selectObservationSource(history, 'GD_OBS_VBU');
  assert.equal(monthly.has('from'), false);
  assert.equal(observationPeriod(monthly).from, CURRENT_OBSERVATION_MONTH);
  assert.equal(observationPeriod(monthly).to, CURRENT_OBSERVATION_MONTH);
});

test('a specified endpoint is preserved independently from the missing endpoint default', () => {
  assert.equal(observationPeriod(new URLSearchParams('from=2022-06')).from, '2022-06');
  assert.equal(observationPeriod(new URLSearchParams('from=2022-06')).to, CURRENT_OBSERVATION_MONTH);
  assert.equal(observationPeriod(new URLSearchParams('to=2026-09')).to, '2026-09');
  assert.equal(observationPeriod(new URLSearchParams('to=2026-09')).from, CURRENT_OBSERVATION_MONTH);
});

test('navigation retains explicit source and period without spreading station/item to unrelated menus', () => {
  const context = observationContext(new URLSearchParams('source=GR_OBS_ST&from=2025-01&to=2025-02&network=N&sea=S&station=X&item=Y'));
  assert.deepEqual(Object.fromEntries(context), { source: 'GR_OBS_ST', from: '2025-01', to: '2025-02', network: 'N', sea: 'S' });
  assert.equal(observationContext(new URLSearchParams()).size, 0);
});

test('returning to the basis month is an explicit action that exits historical scope', () => {
  const original = new URLSearchParams('source=HISTORICAL_RECONCILED&from=2013-01&to=2015-12&sea=W&station=X');
  const next = currentObservationPeriod(original);
  assert.deepEqual(observationPeriod(next), { source: 'GD_OBS_ST_MONTHLY', from: '2026-07', to: '2026-07', isHistorical: false });
  assert.equal(next.get('sea'), 'W');
  assert.equal(next.has('station'), false);
  assert.equal(original.get('from'), '2013-01');
});
