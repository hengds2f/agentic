import type { TripRequest } from '../types';

interface Props {
  trip: TripRequest | null;
}

export default function TripSidebar({ trip }: Props) {
  return (
    <div className="p-4 space-y-4">
      <h2 className="font-semibold text-sm text-gray-500 uppercase tracking-wider">Trip Details</h2>
      <div className="space-y-3 text-sm">
        <Field label="Destination" value={trip?.destination} />
        <Field label="Origin" value={trip?.origin} />
        <Field label="Dates" value={trip?.start_date && trip?.end_date ? `${trip.start_date} → ${trip.end_date}` : undefined} />
        <Field label="Budget" value={trip?.budget_total ? `$${trip.budget_total.toLocaleString()} ${trip.budget_currency}` : undefined} />
        <Field label="Mood" value={trip?.mood} />
        <Field label="Travelers" value={trip?.travelers?.length ? `${trip.travelers.length} traveler(s)` : undefined} />
        {trip?.interests && trip.interests.length > 0 && (
          <div>
            <span className="text-gray-500 text-xs">Interests</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {trip.interests.map((i, idx) => (
                <span key={idx} className="bg-primary-50 text-primary-700 px-2 py-0.5 rounded text-xs">{i}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <span className="text-gray-500 text-xs">{label}</span>
      <div className={value ? 'text-gray-900 font-medium' : 'text-gray-300 italic'}>
        {value || 'Not set'}
      </div>
    </div>
  );
}
