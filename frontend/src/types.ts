export interface TravelerProfile {
  name: string;
  age?: number;
  dietary_restrictions: string[];
  accessibility_needs: string[];
  interests: string[];
}

export interface TripRequest {
  trip_id: string;
  destination: string;
  origin: string;
  start_date: string | null;
  end_date: string | null;
  budget_total: number | null;
  budget_currency: string;
  num_adults: number;
  num_children: number;
  travelers: TravelerProfile[];
  mood: string;
  interests: string[];
  constraints: string[];
  notes: string;
}

export interface ChatMessage {
  role: string;
  content: string;
  agent?: string;
  metadata?: Record<string, unknown>;
  timestamp?: string;
}

export interface ReasoningStep {
  agent: string;
  action: string;
  result_summary: string;
  duration_ms: number;
}

export interface ChatResponse {
  trip_id: string;
  messages: ChatMessage[];
  trip_data: TripRequest | null;
  reasoning_steps: ReasoningStep[];
  itinerary: Itinerary | null;
  budget: BudgetBreakdown | null;
}

export interface ItineraryItem {
  id: string;
  day: number;
  start_time: string | null;
  end_time: string | null;
  title: string;
  category: string;
  description: string;
  location: string;
  cost: number;
  currency: string;
  reasoning: string;
  weather_note: string;
  confirmed: boolean;
  backup: ItineraryItem | null;
}

export interface WeatherForecast {
  date: string;
  high_temp_c: number;
  low_temp_c: number;
  condition: string;
  precipitation_pct: number;
  recommendation: string;
}

export interface DayPlan {
  day: number;
  date: string;
  title: string;
  items: ItineraryItem[];
  weather: WeatherForecast | null;
  daily_spend: number;
}

export interface Itinerary {
  trip_id: string;
  days: DayPlan[];
  total_cost: number;
  currency: string;
  flexibility_score: number;
  travel_time_hours: number;
  packing_list: string[];
  checklist: string[];
}

export interface BudgetCategory {
  category: string;
  allocated: number;
  spent: number;
  items: string[];
}

export interface BudgetBreakdown {
  total_budget: number;
  total_estimated: number;
  currency: string;
  categories: BudgetCategory[];
  within_budget: boolean;
  savings_tips: string[];
}

export interface PlanResult {
  trip_id: string;
  plan_summary: string;
  itinerary: Itinerary;
  budget: BudgetBreakdown;
  reasoning_steps: ReasoningStep[];
}
