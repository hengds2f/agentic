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
  const pct = budget.total_budget > 0 ? (budget.total_estimated / budget.total_budget) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Budget meter */}
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-semibold">Budget Overview</h3>
          <span className={`text-sm font-medium ${budget.within_budget ? 'text-green-600' : 'text-red-600'}`}>
            {budget.within_budget ? '✅ Within Budget' : '⚠️ Over Budget'}
          </span>
        </div>
        <div className="flex justify-between text-sm mb-2">
          <span>Estimated: ${budget.total_estimated.toLocaleString()}</span>
          <span>Budget: ${budget.total_budget.toLocaleString()}</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all ${pct > 100 ? 'bg-red-500' : 'bg-green-500'}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
      </div>

      {/* Category breakdown */}
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
