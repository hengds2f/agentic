import { useState } from 'react';
import type { Itinerary, DayPlan, ItineraryItem } from '../types';
import { optimizeDay } from '../api';

interface Props {
  itinerary: Itinerary;
  tripId: string;
  onItineraryUpdated: (itinerary: Itinerary) => void;
}

const categoryIcons: Record<string, string> = {
  flight: '✈️',
  hotel: '🏨',
  activity: '🎯',
  food: '🍽️',
  transport: '🚗',
};

export default function ItineraryView({ itinerary, tripId, onItineraryUpdated }: Props) {
  const [error, setError] = useState('');

  const handleRegenerate = async (day: number) => {
    setError('');
    try {
      const res = await optimizeDay(tripId, day);
      if (res.itinerary) {
        onItineraryUpdated(res.itinerary);
      }
    } catch (err) {
      console.error('Regenerate failed:', err);
      setError(`Failed to regenerate Day ${day}. Please try again.`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary card */}
      <div className="bg-gradient-to-r from-primary-50 to-accent-50 rounded-xl p-5 border border-primary-100">
        <h2 className="font-bold text-lg text-primary-900 mb-2">Trip Summary</h2>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-gray-500">Total Cost</div>
            <div className="font-bold text-lg">${itinerary.total_cost.toLocaleString()}</div>
          </div>
          <div>
            <div className="text-gray-500">Travel Time</div>
            <div className="font-bold text-lg">{itinerary.travel_time_hours}h</div>
          </div>
          <div>
            <div className="text-gray-500">Flexibility</div>
            <div className="font-bold text-lg">{Math.round(itinerary.flexibility_score * 100)}%</div>
          </div>
        </div>
      </div>

      {/* Day plans */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
          {error}
        </div>
      )}
      {itinerary.days.map(day => (
        <DayCard key={day.day} day={day} onRegenerate={() => handleRegenerate(day.day)} />
      ))}
    </div>
  );
}

function DayCard({ day, onRegenerate }: { day: DayPlan; onRegenerate: () => Promise<void> }) {
  const [loading, setLoading] = useState(false);
  const handleClick = async () => {
    setLoading(true);
    try { await onRegenerate(); } finally { setLoading(false); }
  };
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="bg-gray-50 px-5 py-3 flex items-center justify-between">
        <div>
          <h3 className="font-semibold">Day {day.day} — {day.title || day.date}</h3>
          {day.weather && (
            <span className="text-xs text-gray-500">
              {day.weather.condition} · {day.weather.high_temp_c}°/{day.weather.low_temp_c}°C
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">${day.daily_spend.toFixed(0)}</span>
          <button
            onClick={handleClick}
            disabled={loading}
            className="text-xs bg-primary-100 text-primary-700 px-2 py-1 rounded hover:bg-primary-200 transition disabled:opacity-50"
          >
            {loading ? '⏳ Regenerating...' : '🔄 Regenerate'}
          </button>
        </div>
      </div>
      <div className="divide-y divide-gray-100">
        {day.items.map(item => (
          <ItemRow key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}

function ItemRow({ item }: { item: ItineraryItem }) {
  return (
    <div className="px-5 py-3 hover:bg-gray-50 transition">
      <div className="flex items-start gap-3">
        <span className="text-lg mt-0.5">{categoryIcons[item.category] || '📌'}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            {item.booking_url ? (
              <a
                href={item.booking_url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-sm text-blue-600 hover:text-blue-800 hover:underline"
              >
                {item.title} ↗
              </a>
            ) : (
              <span className="font-medium text-sm">{item.title}</span>
            )}
            {item.cost > 0 && (
              <span className="text-sm text-gray-500">${item.cost.toFixed(0)}</span>
            )}
          </div>
          {item.start_time && (
            <div className="text-xs text-gray-400">
              {item.start_time} — {item.end_time}
              {item.location && <span className="ml-2 text-gray-500">📍 {item.location}</span>}
            </div>
          )}
          {item.description && (
            <div className="text-xs text-gray-500 mt-0.5">{item.description}</div>
          )}
          {item.reasoning && (
            <div className="text-xs text-primary-600 mt-1 italic">Why: {item.reasoning}</div>
          )}
          {item.weather_note && (
            <div className="text-xs text-amber-600 mt-0.5">⚠️ {item.weather_note}</div>
          )}
          {item.backup && (
            <div className="text-xs text-gray-400 mt-0.5">
              Backup: {item.backup.title}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
