import { useState } from 'react';
import type { ChatMessage, ReasoningStep, TripRequest, Itinerary, BudgetBreakdown } from './types';
import { sendChat, getExportUrl } from './api';
import ChatPanel from './components/ChatPanel';
import TripSidebar from './components/TripSidebar';
import ItineraryView from './components/ItineraryView';
import BudgetView from './components/BudgetView';
import ReasoningSteps from './components/ReasoningSteps';

type Tab = 'itinerary' | 'budget' | 'weather' | 'checklist';

export default function App() {
  const [tripId, setTripId] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: "Hi! I'm HolidayPilot 🌍 Where would you like to go? Tell me your destination, dates, budget, and travel style!" },
  ]);
  const [tripData, setTripData] = useState<TripRequest | null>(null);
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [budget, setBudget] = useState<BudgetBreakdown | null>(null);
  const [steps, setSteps] = useState<ReasoningStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('itinerary');

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendChat(tripId, text);
      setTripId(res.trip_id);
      const assistantMsgs = res.messages.filter(m => m.role === 'assistant');
      setMessages(prev => [...prev, ...assistantMsgs]);
      if (res.trip_data) setTripData(res.trip_data);
      if (res.reasoning_steps.length) setSteps(res.reasoning_steps);
      if (res.itinerary) setItinerary(res.itinerary);
      if (res.budget) setBudget(res.budget);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: 'itinerary', label: '📅 Itinerary' },
    { key: 'budget', label: '💰 Budget' },
    { key: 'weather', label: '🌤️ Weather' },
    { key: 'checklist', label: '✅ Checklist' },
  ];

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-primary-700 text-white px-6 py-3 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🌍</span>
          <h1 className="text-xl font-bold">HolidayPilot</h1>
        </div>
        <div className="flex items-center gap-3">
          {tripId && (
            <a
              href={getExportUrl(tripId, 'html')}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded text-sm transition"
            >
              📥 Download Itinerary
            </a>
          )}
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat */}
        <div className="w-full lg:w-[420px] flex flex-col border-r border-gray-200 bg-gray-50">
          <ChatPanel messages={messages} onSend={handleSend} loading={loading} />
        </div>

        {/* Middle: Trip sidebar (auto-filled from chat) */}
        <div className="hidden lg:block w-72 border-r border-gray-200 bg-white overflow-y-auto">
          <TripSidebar trip={tripData} />
          {steps.length > 0 && <ReasoningSteps steps={steps} />}
        </div>

        {/* Right: Results */}
        <div className="hidden lg:flex flex-1 flex-col bg-white">
          {/* Tabs */}
          <div className="flex border-b border-gray-200">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-4 py-3 text-sm font-medium transition ${
                  activeTab === t.key
                    ? 'border-b-2 border-primary-600 text-primary-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'itinerary' && (
              itinerary ? (
                <ItineraryView itinerary={itinerary} tripId={tripId} onItineraryUpdated={setItinerary} />
              ) : (
                <EmptyState icon="📅" text="Your itinerary will appear here after planning" />
              )
            )}
            {activeTab === 'budget' && (
              budget ? (
                <BudgetView budget={budget} />
              ) : (
                <EmptyState icon="💰" text="Budget breakdown will appear after planning" />
              )
            )}
            {activeTab === 'weather' && (
              <EmptyState icon="🌤️" text="Weather forecasts will appear after planning" />
            )}
            {activeTab === 'checklist' && (
              itinerary ? (
                <div className="space-y-4">
                  <h3 className="font-semibold text-lg">🎒 Packing List</h3>
                  <ul className="space-y-1">
                    {itinerary.packing_list.map((item, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <input type="checkbox" className="rounded" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  <h3 className="font-semibold text-lg mt-6">✅ Pre-Trip Checklist</h3>
                  <ul className="space-y-1">
                    {itinerary.checklist.map((item, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <input type="checkbox" className="rounded" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <EmptyState icon="✅" text="Checklists will appear after planning" />
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-gray-400">
      <span className="text-5xl mb-4">{icon}</span>
      <p>{text}</p>
    </div>
  );
}
