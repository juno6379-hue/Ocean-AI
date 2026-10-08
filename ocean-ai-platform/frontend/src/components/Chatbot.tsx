// 파일 역할: 사용자 질문과 근거 기반 답변을 표시합니다.
import { apiFetch } from '../api/client';
import { API_BASE_URL } from '../api/client';
import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, Bot, User, Loader2, Link2 } from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  source?: string;
  timestamp: string;
}

const Chatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'ai',
      text: '안녕하세요! 해양관측 지식 검색 AI입니다. 매뉴얼, 장애 이력, 운영 가이드 등에 대해 궁금한 점을 물어보세요.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: inputValue,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await apiFetch(`${API_BASE_URL}/rag/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg.text })
      });
      const data = await res.json();

      if (data.success) {
        const aiMsg: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          text: data.answer,
          source: data.source,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, aiMsg]);
      } else {
        throw new Error(data.detail || "API Error");
      }
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        text: '서버에 연결할 수 없거나 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={`fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-xl flex items-center justify-center transition-transform duration-300 z-50 ${isOpen ? 'scale-0' : 'scale-100'}`}
      >
        <MessageSquare className="w-6 h-6" />
        <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full border-2 border-white">
          AI
        </span>
      </button>

      {/* Chat Window */}
      <div
        className={`fixed bottom-6 right-6 w-80 md:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50 transition-all duration-300 transform origin-bottom-right ${
          isOpen ? 'scale-100 opacity-100' : 'scale-0 opacity-0 pointer-events-none'
        }`}
        style={{ height: '500px', maxHeight: 'calc(100vh - 48px)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-blue-600 text-white rounded-t-2xl shrink-0">
          <div className="flex items-center gap-2">
            <div className="bg-white/20 p-1.5 rounded-lg">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm">Ocean AI 통합 챗봇</h3>
              <p className="text-[10px] text-blue-100">지식 검색 및 데이터 추출 지원</p>
            </div>
          </div>
          <button onClick={() => setIsOpen(false)} className="p-1 hover:bg-white/20 rounded-md transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 custom-scrollbar">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`flex gap-2 max-w-[85%] ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className="shrink-0 mt-1">
                  {msg.sender === 'ai' ? (
                    <div className="w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center">
                      <Bot className="w-4 h-4" />
                    </div>
                  ) : (
                    <div className="w-7 h-7 bg-slate-200 text-slate-600 rounded-full flex items-center justify-center">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
                <div className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                  <div
                    className={`px-3 py-2 text-sm rounded-2xl ${
                      msg.sender === 'user'
                        ? 'bg-blue-600 text-white rounded-tr-sm'
                        : 'bg-white text-slate-700 border border-slate-200 shadow-sm rounded-tl-sm'
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {msg.text.split(/(\[.+?\]\(.+?\))/g).map((part, i) => {
                        const linkMatch = part.match(/\[(.+?)\]\((.+?)\)/);
                        if (linkMatch) {
                          const linkColor = msg.sender === 'user' ? 'text-blue-200 hover:text-white' : 'text-blue-600 hover:text-blue-800';
                          return (
                            <a key={i} href={linkMatch[2]} target="_blank" rel="noopener noreferrer" className={`${linkColor} underline font-semibold`}>
                              {linkMatch[1]}
                            </a>
                          );
                        }
                        return <span key={i}>{part}</span>;
                      })}
                    </p>
                    {msg.source && (
                      <div className="mt-2 pt-2 border-t border-slate-100">
                        <p className="text-[10px] font-bold text-slate-400 flex items-center gap-1">
                          <Link2 className="w-3 h-3" /> 참고 출처
                        </p>
                        <p className="text-[11px] text-blue-600 font-medium hover:underline cursor-pointer mt-0.5">
                          {msg.source}
                        </p>
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 px-1">{msg.timestamp}</span>
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="flex gap-2 max-w-[85%]">
                <div className="shrink-0 mt-1">
                  <div className="w-7 h-7 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                </div>
                <div className="bg-white text-slate-700 border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm px-4 py-2">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-3 bg-white border-t border-slate-200 rounded-b-2xl shrink-0">
          <form onSubmit={handleSendMessage} className="flex items-center gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="궁금한 내용을 입력하세요..."
              disabled={isLoading}
              className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="w-9 h-9 bg-blue-600 text-white rounded-full flex items-center justify-center shrink-0 disabled:opacity-50 disabled:bg-slate-300 transition-colors"
            >
              <Send className="w-4 h-4 ml-0.5" />
            </button>
          </form>
        </div>
      </div>
    </>
  );
};

export default Chatbot;
