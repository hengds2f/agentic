import { useState, useRef, useEffect } from 'react';
import type { ChatMessage } from '../types';
import DatePicker from './DatePicker';

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
}

function needsDatePicker(messages: ChatMessage[]): boolean {
  if (messages.length === 0) return false;
  const last = messages[messages.length - 1];
  if (last.role !== 'assistant') return false;
  const lower = last.content.toLowerCase();
  return (
    (lower.includes('date') || lower.includes('when')) &&
    (lower.includes('travel') || lower.includes('start') || lower.includes('trip') || lower.includes('return'))
  );
}

export default function ChatPanel({ messages, onSend, loading }: Props) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showDatePicker, setShowDatePicker] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!loading && needsDatePicker(messages)) {
      setShowDatePicker(true);
    }
  }, [messages, loading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    onSend(text);
  };

  const handleDateSelect = (startDate: string, endDate: string) => {
    setShowDatePicker(false);
    onSend(`My travel dates are ${startDate} to ${endDate}`);
  };

  return (
    <>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}>
              <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
              {msg.agent && (
                <div className="text-xs mt-1 opacity-60">via {msg.agent} agent</div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="chat-bubble-assistant">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        {showDatePicker && !loading && (
          <DatePicker onSelect={handleDateSelect} />
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-3 border-t border-gray-200 bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Tell me about your dream trip..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="bg-primary-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Send
          </button>
        </div>
      </form>
    </>
  );
}
