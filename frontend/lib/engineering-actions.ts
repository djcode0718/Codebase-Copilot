export type EngineeringActionId =
  | 'explain'
  | 'review'
  | 'find_bugs'
  | 'security'
  | 'performance'
  | 'architecture'
  | 'code_quality'
  | 'coverage'
  | 'missing_cases'
  | 'dependency_risk'
  | 'upgrade_impact'
  | 'license'
  | 'generate_upgrade_plan'
  | 'generate_tests'
  | 'generate_fix'
  | 'show_diff'
  | 'run_tests'
  | 'impact'
  | 'compare'
  | 'analyze'
  | 'health'
  | 'open_ai_chat'
  | 'history'
  | 'open_evidence'
  | 'reanalyze'
  | 'ignore';

export interface EngineeringAction {
  id: EngineeringActionId;
  label: string;
}

export type EngineeringActionContext = {
  kind: 'file' | 'recommendation' | 'finding' | 'branch';
  filePath?: string;
};

const ACTIONS: Record<EngineeringActionId, EngineeringAction> = {
  explain: { id: 'explain', label: 'Explain' },
  review: { id: 'review', label: 'Review' },
  find_bugs: { id: 'find_bugs', label: 'Find Bugs' },
  security: { id: 'security', label: 'Security' },
  performance: { id: 'performance', label: 'Performance' },
  architecture: { id: 'architecture', label: 'Architecture' },
  code_quality: { id: 'code_quality', label: 'Code Quality' },
  coverage: { id: 'coverage', label: 'Coverage' },
  missing_cases: { id: 'missing_cases', label: 'Missing Cases' },
  dependency_risk: { id: 'dependency_risk', label: 'Dependency Risk' },
  upgrade_impact: { id: 'upgrade_impact', label: 'Upgrade Impact' },
  license: { id: 'license', label: 'License' },
  generate_upgrade_plan: { id: 'generate_upgrade_plan', label: 'Upgrade Plan' },
  generate_tests: { id: 'generate_tests', label: 'Generate Tests' },
  generate_fix: { id: 'generate_fix', label: 'Generate Fix' },
  show_diff: { id: 'show_diff', label: 'Show Diff' },
  run_tests: { id: 'run_tests', label: 'Run Tests' },
  impact: { id: 'impact', label: 'Impact' },
  compare: { id: 'compare', label: 'Compare' },
  analyze: { id: 'analyze', label: 'Analyze' },
  health: { id: 'health', label: 'Health' },
  open_ai_chat: { id: 'open_ai_chat', label: 'Open AI Chat' },
  history: { id: 'history', label: 'History' },
  open_evidence: { id: 'open_evidence', label: 'Open Evidence' },
  reanalyze: { id: 'reanalyze', label: 'Re-analyze' },
  ignore: { id: 'ignore', label: 'Ignore' },
};

function looksLikeTestFile(path: string): boolean {
  const p = path.toLowerCase();
  return /(^|\/)(tests?|__tests__)\//.test(p) || /(^|\/)test_[^/]+\.[a-z0-9]+$/.test(p);
}

function looksLikeDependencyFile(path: string): boolean {
  const p = path.toLowerCase();
  return [
    'requirements.txt',
    'requirements-api.txt',
    'requirements-minimal.txt',
    'package.json',
    'package-lock.json',
    'pnpm-lock.yaml',
    'poetry.lock',
    'pyproject.toml',
    'go.mod',
    'go.sum',
    'pom.xml',
    'cargo.toml',
    'cargo.lock',
  ].some((name) => p.endsWith(name));
}

function toActions(ids: EngineeringActionId[]): EngineeringAction[] {
  return ids.map((id) => ACTIONS[id]);
}

export function getContextualEngineeringActions(context: EngineeringActionContext): EngineeringAction[] {
  if (context.kind === 'branch') {
    return toActions(['compare', 'analyze', 'health', 'security', 'impact', 'run_tests', 'review']);
  }

  if (context.kind === 'recommendation') {
    return toActions([
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
  }

  if (context.kind === 'finding') {
    return toActions([
      'explain',
      'open_evidence',
      'review',
      'generate_fix',
      'generate_tests',
      'show_diff',
      'run_tests',
      'ignore',
    ]);
  }

  const filePath = (context.filePath || '').trim();
  if (filePath && looksLikeTestFile(filePath)) {
    return toActions(['explain', 'coverage', 'missing_cases', 'generate_tests', 'run_tests', 'review', 'open_ai_chat']);
  }

  if (filePath && looksLikeDependencyFile(filePath)) {
    return toActions(['dependency_risk', 'security', 'upgrade_impact', 'license', 'generate_upgrade_plan', 'review']);
  }

  return toActions([
    'explain',
    'review',
    'find_bugs',
    'security',
    'performance',
    'architecture',
    'generate_tests',
    'generate_fix',
    'impact',
    'show_diff',
    'run_tests',
    'open_ai_chat',
    'history',
  ]);
}

