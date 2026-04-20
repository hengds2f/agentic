import type { ReasoningStep } from '../types';

interface Props {
  steps: ReasoningStep[];
}

const agentIcons: Record<string, string> = {
  planner: '🧠',
  flights: '✈️',
  hotels: '🏨',
  activities: '🎯',
  food: '🍽️',
  route: '🗺️',
  weather: '🌤️',
  budget: '💰',
  calendar: '📅',
  monitoring: '🔔',
};

export default function ReasoningSteps({ steps }: Props) {
  return (
    <div className="p-4 border-t border-gray-200">
      <h3 className="font-semibold text-sm text-gray-500 uppercase tracking-wider mb-3">Agent Activity</h3>
      <div className="space-y-2">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span>{agentIcons[step.agent] || '⚙️'}</span>
            <div className="flex-1 min-w-0">
              <div className="font-medium capitalize">{step.agent}</div>
              <div className="text-gray-500 truncate">{step.result_summary}</div>
            </div>
            <span className="text-gray-400 whitespace-nowrap">{step.duration_ms}ms</span>
          </div>
        ))}
      </div>
    </div>
  );
}
