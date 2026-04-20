import type { BudgetBreakdown } from '../types';

interface Props {
  budget: BudgetBreakdown;
}

const categoryColors: Record<string, string> = {
  Flights: 'bg-red-400',
  Accommodation: 'bg-blue-400',
  Activities: 'bg-green-400',
  Food: 'bg-yellow-400',
  Transport: 'bg-purple-400',
};

export default function BudgetView({ budget }: Props) {
  return (
    <div className="space-y-6">
      {/* Cost overview */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h3 className="font-semibold mb-3">Cost Overview</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-primary-50 rounded-lg p-4 text-center">
            <div className="text-sm text-gray-500">Total Estimated</div>
            <div className="text-2xl font-bold text-primary-700">
              ${budget.total_estimated.toLocaleString()}
            </div>
            <div className="text-xs text-gray-400">{budget.currency}</div>
          </div>
          <div className="bg-accent-50 rounded-lg p-4 text-center">
            <div className="text-sm text-gray-500">Per Person</div>
            <div className="text-2xl font-bold text-accent-700">
              ${budget.cost_per_person.toLocaleString()}
            </div>
            <div className="text-xs text-gray-400">
              {budget.num_travelers} traveler{budget.num_travelers !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      </div>

      {/* Category breakdown */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <h3 className="font-semibold mb-3">Cost Breakdown</h3>
        <div className="space-y-3">
          {budget.categories.map(cat => (
            <div key={cat.category} className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${categoryColors[cat.category] || 'bg-gray-400'}`} />
              <div className="flex-1">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{cat.category}</span>
                  <span>${cat.allocated.toLocaleString()}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-1.5 mt-1">
                  <div
                    className={`h-1.5 rounded-full ${categoryColors[cat.category] || 'bg-gray-400'}`}
                    style={{ width: `${budget.total_estimated > 0 ? (cat.allocated / budget.total_estimated) * 100 : 0}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Savings tips */}
      {budget.savings_tips.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <h4 className="font-medium text-amber-800 mb-2">💡 Savings Tips</h4>
          <ul className="text-sm text-amber-700 space-y-1">
            {budget.savings_tips.map((tip, i) => (
              <li key={i}>• {tip}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
