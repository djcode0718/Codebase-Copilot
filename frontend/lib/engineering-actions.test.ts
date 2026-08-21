import { describe, expect, it } from 'vitest';
import { getContextualEngineeringActions } from './engineering-actions';

describe('getContextualEngineeringActions', () => {
  it('returns recommendation-focused actions for recommendation context', () => {
    const actions = getContextualEngineeringActions({ kind: 'recommendation', filePath: 'api/routers/health.py' });
    const ids = actions.map((action) => action.id);

    expect(ids).toEqual([
      'explain',
      'open_evidence',
      'review',
      'generate_fix',
      'generate_tests',
      'show_diff',
      'run_tests',
      'reanalyze',
      'ignore',
    ]);
  });

  it('auto-detects test files and returns test actions for file context', () => {
    const actions = getContextualEngineeringActions({ kind: 'file', filePath: 'tests/integration/test_router_chat.py' });
    const ids = actions.map((action) => action.id);

    expect(ids).toEqual([
      'explain',
      'coverage',
      'missing_cases',
      'generate_tests',
      'run_tests',
      'review',
      'open_ai_chat',
    ]);
  });

  it('auto-detects dependency manifests and returns dependency actions for file context', () => {
    const actions = getContextualEngineeringActions({ kind: 'file', filePath: 'frontend/package.json' });
    const ids = actions.map((action) => action.id);

    expect(ids).toEqual([
      'dependency_risk',
      'security',
      'upgrade_impact',
      'license',
      'generate_upgrade_plan',
      'review',
    ]);
  });

  it('returns commit actions including diff/test pathways for commit context', () => {
    const actions = getContextualEngineeringActions({ kind: 'commit', commitSha: 'abc1234' });
    const ids = actions.map((action) => action.id);

    expect(ids).toContain('show_diff');
    expect(ids).toContain('run_tests');
    expect(ids).toContain('open_ai_chat');
    expect(ids[0]).toBe('explain');
  });
});
