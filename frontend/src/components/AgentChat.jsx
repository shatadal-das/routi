import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const SUGGESTED_PROMPTS = [
  { label: '🍽️ Remove Restaurant', text: 'Remove the restaurant from my itinerary.' },
  { label: '🌿 Add Nature Stop', text: 'Add another scenic nature or viewpoint spot.' },
  { label: '☕ Add a Cafe', text: 'Add a cafe stop if time permits.' },
  { label: '⏱️ Make It Shorter', text: 'Make this route shorter.' },
  { label: '🧘 Relaxed Pacing', text: 'Give me a relaxed trip with fewer destinations and longer visits.' },
  { label: '❓ Not Enough Places?', text: "There aren't enough places. What can I do?" },
];

export default function AgentChat({
  currentItinerary,
  startLocation,
  onUpdateRoute,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: "Hello! I'm your RoamAround Concierge. How can I adjust your day trip? You can ask me to add places, remove dining, shorten the schedule, or change the pacing.",
      delta: null,
      adviceActions: null,
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  // Focus input when opening chat
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  const handleSendMessage = async (textToSend) => {
    const text = (textToSend || inputValue).trim();
    if (!text || isSending) return;

    const userMessage = { role: 'user', text };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsSending(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/agent/chat`, {
        message: text,
        conversation_history: messages.map((m) => ({
          role: m.role,
          content: m.text,
        })),
        current_itinerary: currentItinerary || undefined,
        start_location: startLocation || undefined,
      });

      const data = response.data;
      console.log('Agent Chat Response:', data);

      if (data.status === 'success') {
        const assistantMessage = {
          role: 'assistant',
          text: data.message || 'Itinerary successfully updated!',
          modification: data.modification_applied,
          delta: data.delta,
        };
        setMessages((prev) => [...prev, assistantMessage]);

        // If updated route result is returned, update the main app state (map, timeline, polyline)
        if (data.route_result && onUpdateRoute) {
          onUpdateRoute(data.route_result);
        }
      } else if (data.status === 'advisory') {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: data.message,
            adviceActions: data.advice_actions,
          },
        ]);
      } else if (data.status === 'clarification_needed') {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: data.message,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            text: data.message || "I processed your request, but wasn't able to modify the route.",
          },
        ]);
      }
    } catch (err) {
      console.error('Failed to chat with agent:', err);
      const detail = err.response?.data?.detail || err.message || 'Failed to connect with agent.';
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Sorry, I encountered an issue: ${detail}`,
          isError: true,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <>
      {/* Floating Launcher Button */}
      <div className="fixed bottom-6 right-6 z-40 flex flex-col items-end">
        {!isOpen && (
          <button
            id="agent-chat-open-button"
            type="button"
            onClick={() => setIsOpen(true)}
            className="group relative flex items-center space-x-2.5 px-4 py-3 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white rounded-full shadow-2xl shadow-indigo-500/40 hover:shadow-indigo-500/60 transition-all duration-300 transform hover:-translate-y-0.5 cursor-pointer border border-indigo-300/30 backdrop-blur-md"
          >
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400"></span>
            </span>
            <span className="text-xs font-bold tracking-wide">Trip Concierge</span>
            <svg
              className="w-4 h-4 text-white/90 group-hover:scale-110 transition-transform"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Slide-out Drawer / Chat Window */}
      {isOpen && (
        <div
          id="agent-chat-panel"
          className="fixed bottom-6 right-6 z-50 w-[92vw] sm:w-[420px] h-[580px] max-h-[85vh] bg-slate-900/98 backdrop-blur-2xl border border-slate-700/80 rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-fadeIn"
        >
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-800 bg-gradient-to-r from-slate-900 via-slate-800/80 to-indigo-950/60 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                  <span>RoamAround Concierge</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                </h3>
                <p className="text-[11px] text-indigo-300/80 font-medium">
                  Interactive Trip Assistant
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
              title="Close chat"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Quick Action Suggestion Chips */}
          <div className="px-4 py-2.5 bg-slate-950/60 border-b border-slate-800/60 overflow-x-auto scrollbar-none flex items-center space-x-2">
            {SUGGESTED_PROMPTS.map((p, idx) => (
              <button
                key={`prompt-${idx}`}
                type="button"
                onClick={() => handleSendMessage(p.text)}
                disabled={isSending}
                className="whitespace-nowrap text-[11px] font-semibold px-2.5 py-1 rounded-full bg-slate-800/90 hover:bg-indigo-900/60 text-slate-300 hover:text-indigo-200 border border-slate-700/60 transition cursor-pointer shrink-0 disabled:opacity-50"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Messages Feed */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs">
            {messages.map((m, idx) => {
              const isUser = m.role === 'user';
              return (
                <div
                  key={`msg-${idx}`}
                  className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-[88%] rounded-2xl px-4 py-3 leading-relaxed shadow-sm ${
                      isUser
                        ? 'bg-indigo-600 text-white rounded-br-sm'
                        : m.isError
                        ? 'bg-rose-950/60 border border-rose-800/60 text-rose-200 rounded-bl-sm'
                        : 'bg-slate-800/90 border border-slate-700/70 text-slate-200 rounded-bl-sm'
                    }`}
                  >
                    {/* Message Body */}
                    <div className="whitespace-pre-line">{m.text}</div>

                    {/* Modification Applied Tag */}
                    {m.modification && (
                      <div className="mt-2 text-[10px] font-bold text-emerald-400 bg-emerald-950/50 border border-emerald-800/40 px-2 py-0.5 rounded-md inline-block">
                        ✨ {m.modification}
                      </div>
                    )}

                    {/* Delta details badge */}
                    {m.delta && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/60 space-y-1 text-[11px]">
                        {m.delta.stops_removed?.length > 0 && (
                          <p className="text-rose-300 font-medium">
                            <span className="font-bold">Removed:</span> {m.delta.stops_removed.join(', ')}
                          </p>
                        )}
                        {m.delta.stops_added?.length > 0 && (
                          <p className="text-emerald-300 font-medium">
                            <span className="font-bold">Added:</span> {m.delta.stops_added.join(', ')}
                          </p>
                        )}
                        {m.delta.new_duration_minutes && (
                          <p className="text-indigo-300 font-medium">
                            <span className="font-bold">Total Duration:</span> {m.delta.new_duration_minutes} mins
                          </p>
                        )}
                      </div>
                    )}

                    {/* Advisory actions chips */}
                    {m.adviceActions && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/60 flex flex-wrap gap-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 w-full">
                          Suggested Actions:
                        </span>
                        {m.adviceActions.map((act) => (
                          <span
                            key={act}
                            className="text-[10px] px-2 py-0.5 rounded-md bg-indigo-950/70 border border-indigo-800/50 text-indigo-300 font-medium"
                          >
                            {act.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {isSending && (
              <div className="flex items-center space-x-2 text-indigo-400 bg-slate-800/70 border border-slate-700/50 px-3.5 py-2.5 rounded-2xl w-fit shadow-sm">
                <div className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-xs font-medium text-slate-300">
                  Agent is optimizing route...
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-3 border-t border-slate-800 bg-slate-950/90">
            <div className="relative flex items-center">
              <input
                id="agent-chat-input"
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isSending}
                placeholder={
                  currentItinerary
                    ? "e.g., 'Remove restaurant', 'Make it shorter'..."
                    : "Plan a trip starting from..."
                }
                className="w-full pl-3.5 pr-11 py-2.5 bg-slate-900 border border-slate-700/80 rounded-2xl text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/80 focus:border-transparent text-xs transition"
              />
              <button
                id="agent-chat-send-button"
                type="button"
                onClick={() => handleSendMessage()}
                disabled={!inputValue.trim() || isSending}
                className="absolute right-1.5 p-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white rounded-xl transition cursor-pointer shadow-sm"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
