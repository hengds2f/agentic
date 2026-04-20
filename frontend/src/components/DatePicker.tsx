import { useState } from 'react';

interface Props {
  onSelect: (startDate: string, endDate: string) => void;
}

export default function DatePicker({ onSelect }: Props) {
  const today = new Date();
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [hoveredDate, setHoveredDate] = useState<Date | null>(null);

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  const dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  function daysInMonth(year: number, month: number) {
    return new Date(year, month + 1, 0).getDate();
  }

  function firstDayOfMonth(year: number, month: number) {
    return new Date(year, month, 1).getDay();
  }

  function formatDate(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function sameDay(a: Date, b: Date): boolean {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }

  function isBefore(a: Date, b: Date): boolean {
    return a.getTime() < b.getTime();
  }

  function isInRange(d: Date): boolean {
    if (!startDate) return false;
    const end = endDate || hoveredDate;
    if (!end) return false;
    const rangeStart = isBefore(startDate, end) ? startDate : end;
    const rangeEnd = isBefore(startDate, end) ? end : startDate;
    return d.getTime() >= rangeStart.getTime() && d.getTime() <= rangeEnd.getTime();
  }

  function handleDayClick(day: number) {
    const clicked = new Date(viewYear, viewMonth, day);
    if (clicked < today) return; // prevent past dates

    if (!startDate || (startDate && endDate)) {
      setStartDate(clicked);
      setEndDate(null);
    } else {
      if (isBefore(clicked, startDate)) {
        setEndDate(startDate);
        setStartDate(clicked);
      } else {
        setEndDate(clicked);
      }
    }
  }

  function handleConfirm() {
    if (startDate && endDate) {
      onSelect(formatDate(startDate), formatDate(endDate));
    }
  }

  function prevMonth() {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear(viewYear - 1);
    } else {
      setViewMonth(viewMonth - 1);
    }
  }

  function nextMonth() {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear(viewYear + 1);
    } else {
      setViewMonth(viewMonth + 1);
    }
  }

  const totalDays = daysInMonth(viewYear, viewMonth);
  const startDay = firstDayOfMonth(viewYear, viewMonth);

  // Build calendar grid
  const cells: (number | null)[] = [];
  for (let i = 0; i < startDay; i++) cells.push(null);
  for (let d = 1; d <= totalDays; d++) cells.push(d);

  // Also render next month side by side
  const nextM = viewMonth === 11 ? 0 : viewMonth + 1;
  const nextY = viewMonth === 11 ? viewYear + 1 : viewYear;
  const totalDays2 = daysInMonth(nextY, nextM);
  const startDay2 = firstDayOfMonth(nextY, nextM);
  const cells2: (number | null)[] = [];
  for (let i = 0; i < startDay2; i++) cells2.push(null);
  for (let d = 1; d <= totalDays2; d++) cells2.push(d);

  function renderMonth(year: number, month: number, dayCells: (number | null)[], label: string) {
    return (
      <div className="flex-1 min-w-0">
        <div className="text-center text-sm font-semibold text-gray-700 mb-2">{label}</div>
        <div className="grid grid-cols-7 gap-0.5 text-center">
          {dayNames.map(d => (
            <div key={d} className="text-[10px] font-medium text-gray-400 py-0.5">{d}</div>
          ))}
          {dayCells.map((day, i) => {
            if (day === null) return <div key={`e${i}`} />;
            const date = new Date(year, month, day);
            const isPast = date < today && !sameDay(date, today);
            const isStart = startDate ? sameDay(date, startDate) : false;
            const isEnd = endDate ? sameDay(date, endDate) : false;
            const inRange = isInRange(date);

            let cls = 'w-7 h-7 mx-auto rounded-full text-xs flex items-center justify-center cursor-pointer transition-colors ';
            if (isPast) {
              cls += 'text-gray-300 cursor-not-allowed';
            } else if (isStart || isEnd) {
              cls += 'bg-primary-600 text-white font-bold';
            } else if (inRange) {
              cls += 'bg-primary-100 text-primary-800';
            } else {
              cls += 'hover:bg-gray-100 text-gray-700';
            }

            return (
              <div
                key={`d${day}`}
                className={cls}
                onClick={() => !isPast && handleDayClick(day)}
                onMouseEnter={() => !isPast && setHoveredDate(date)}
              >
                {day}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-3 mx-2 mb-2 max-w-sm">
      <div className="flex items-center justify-between mb-2 px-1">
        <button
          onClick={prevMonth}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-500"
        >
          ‹
        </button>
        <span className="text-xs text-gray-500 font-medium">Select your travel dates</span>
        <button
          onClick={nextMonth}
          className="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-500"
        >
          ›
        </button>
      </div>

      <div className="flex gap-3">
        {renderMonth(viewYear, viewMonth, cells, `${monthNames[viewMonth]} ${viewYear}`)}
        {renderMonth(nextY, nextM, cells2, `${monthNames[nextM]} ${nextY}`)}
      </div>

      {/* Selection display + confirm */}
      <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-2">
        <div className="text-xs text-gray-500">
          {startDate && !endDate && <span>Start: <strong>{formatDate(startDate)}</strong> → pick end date</span>}
          {startDate && endDate && (
            <span><strong>{formatDate(startDate)}</strong> → <strong>{formatDate(endDate)}</strong></span>
          )}
          {!startDate && <span>Click a start date</span>}
        </div>
        <button
          onClick={handleConfirm}
          disabled={!startDate || !endDate}
          className="bg-primary-600 text-white text-xs px-3 py-1.5 rounded-lg font-medium hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          Confirm dates
        </button>
      </div>
    </div>
  );
}
