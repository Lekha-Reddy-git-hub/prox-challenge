import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage, Artifact, StreamChunk, ImageData } from './types';

const SUGGESTED_QUESTIONS = [
  "Help me set up for my first MIG weld",
  "What's the duty cycle at 200A on 240V?",
  "I'm getting porosity — what should I check?",
  "Show me the polarity setup for TIG welding",
];

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('');
  const [activeArtifact, setActiveArtifact] = useState<Artifact | null>(null);
  const [sessionId] = useState(() => generateId());
  const [pendingImages, setPendingImages] = useState<ImageData[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendMessage = async (text: string) => {
    if ((!text.trim() && pendingImages.length === 0) || isLoading) return;

    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
      images: pendingImages.length > 0 ? [...pendingImages] : undefined,
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setPendingImages([]);
    setIsLoading(true);
    setLoadingStatus('Thinking...');

    const assistantId = generateId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      artifacts: [],
      toolCalls: [],
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, assistantMessage]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text.trim(),
          session_id: sessionId,
          images: pendingImages.map(img => ({
            data: img.data,
            media_type: img.media_type,
          })),
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) throw new Error('No response body');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const chunk: StreamChunk = JSON.parse(jsonStr);

            if (chunk.type === 'text') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: m.content + (chunk.content || '') }
                    : m
                )
              );
              setLoadingStatus('');
            } else if (chunk.type === 'artifact') {
              const artifact: Artifact = {
                title: chunk.title || 'Artifact',
                html_content: chunk.html_content || '',
                artifact_type: chunk.artifact_type || 'diagram',
              };
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, artifacts: [...(m.artifacts || []), artifact] }
                    : m
                )
              );
              setActiveArtifact(artifact);
            } else if (chunk.type === 'tool_use') {
              const toolName = chunk.tool || 'unknown';
              const statusMap: Record<string, string> = {
                search_manual: 'Searching manual...',
                get_duty_cycle: 'Looking up duty cycle...',
                get_troubleshooting: 'Checking troubleshooting guide...',
                get_polarity: 'Getting polarity setup...',
                get_manual_page: 'Reading manual page...',
                get_specifications: 'Checking specifications...',
                get_selection_chart: 'Loading selection chart...',
                render_artifact: 'Generating visual...',
              };
              setLoadingStatus(statusMap[toolName] || `Using ${toolName}...`);
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? {
                        ...m,
                        toolCalls: [
                          ...(m.toolCalls || []),
                          { tool: chunk.tool || '', input: chunk.input || {} },
                        ],
                      }
                    : m
                )
              );
            } else if (chunk.type === 'error') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: `**Error:** ${chunk.content}` }
                    : m
                )
              );
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    } catch (err) {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? {
                ...m,
                content: `**Connection Error:** Could not reach the backend. Make sure the server is running on port 8000.`,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      setLoadingStatus('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach(file => {
      if (file.size > 10 * 1024 * 1024) {
        alert('Image must be under 10MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        const base64 = result.split(',')[1];
        const mediaType = file.type || 'image/jpeg';
        setPendingImages(prev => [
          ...prev,
          { data: base64, media_type: mediaType, preview_url: result },
        ]);
      };
      reader.readAsDataURL(file);
    });
    e.target.value = '';
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (!file) continue;
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as string;
          const base64 = result.split(',')[1];
          setPendingImages(prev => [
            ...prev,
            { data: base64, media_type: file.type, preview_url: result },
          ]);
        };
        reader.readAsDataURL(file);
      }
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-screen bg-vulcan-darker">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 bg-vulcan-dark border-b border-vulcan-border shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-vulcan-red flex items-center justify-center font-bold text-white text-sm">
            V
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white leading-tight">
              Vulcan OmniPro 220
            </h1>
            <p className="text-xs text-vulcan-muted">Expert Assistant</p>
          </div>
        </div>
        {hasMessages && (
          <button
            onClick={() => {
              setMessages([]);
              setActiveArtifact(null);
              fetch('/api/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId }),
              });
            }}
            className="text-xs text-vulcan-muted hover:text-white px-3 py-1.5 rounded border border-vulcan-border hover:border-vulcan-red transition-colors"
          >
            New Chat
          </button>
        )}
      </header>

      {/* Main Content */}
      <div className="flex flex-1 min-h-0">
        {/* Chat Panel */}
        <div
          className={`flex flex-col ${activeArtifact ? 'w-1/2 border-r border-vulcan-border' : 'w-full max-w-3xl mx-auto'} transition-all duration-300`}
        >
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {!hasMessages ? (
              /* Onboarding */
              <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto">
                <div className="w-20 h-20 rounded-2xl bg-vulcan-red/20 border border-vulcan-red/30 flex items-center justify-center mb-6">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#CC0000" strokeWidth="1.5">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  Vulcan OmniPro 220 Assistant
                </h2>
                <p className="text-vulcan-muted text-sm text-center mb-8 leading-relaxed">
                  I know every page of your welder's manual. Ask me about setup,
                  settings, troubleshooting, or anything else — I'll show you
                  diagrams and interactive tools when they help.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full">
                  {SUGGESTED_QUESTIONS.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(q)}
                      className="text-left text-sm px-4 py-3 rounded-lg bg-vulcan-surface border border-vulcan-border hover:border-vulcan-red/50 hover:bg-vulcan-surface/80 text-vulcan-text transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Message List */
              <div className="space-y-4 max-w-2xl mx-auto">
                {messages.map(msg => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] rounded-xl px-4 py-3 ${
                        msg.role === 'user'
                          ? 'bg-vulcan-red/15 border border-vulcan-red/20 text-vulcan-text'
                          : 'bg-vulcan-surface border border-vulcan-border text-vulcan-text'
                      }`}
                    >
                      {/* User images */}
                      {msg.images && msg.images.length > 0 && (
                        <div className="flex gap-2 mb-2 flex-wrap">
                          {msg.images.map((img, i) => (
                            <img
                              key={i}
                              src={img.preview_url}
                              alt="Uploaded"
                              className="w-24 h-24 object-cover rounded-lg border border-vulcan-border"
                            />
                          ))}
                        </div>
                      )}
                      {/* Message content */}
                      {msg.content ? (
                        msg.role === 'assistant' ? (
                          <div className="markdown-content text-sm">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        ) : (
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        )
                      ) : msg.role === 'assistant' && isLoading ? (
                        <div className="flex items-center gap-2 text-sm text-vulcan-muted">
                          <div className="flex gap-1">
                            <span className="w-1.5 h-1.5 bg-vulcan-red rounded-full animate-bounce [animation-delay:0ms]" />
                            <span className="w-1.5 h-1.5 bg-vulcan-red rounded-full animate-bounce [animation-delay:150ms]" />
                            <span className="w-1.5 h-1.5 bg-vulcan-red rounded-full animate-bounce [animation-delay:300ms]" />
                          </div>
                          {loadingStatus && <span>{loadingStatus}</span>}
                        </div>
                      ) : null}
                      {/* Artifact indicators */}
                      {msg.artifacts && msg.artifacts.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {msg.artifacts.map((art, i) => (
                            <button
                              key={i}
                              onClick={() => setActiveArtifact(art)}
                              className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-vulcan-red/10 border border-vulcan-red/20 text-vulcan-red hover:bg-vulcan-red/20 transition-colors"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <rect x="3" y="3" width="18" height="18" rx="2" />
                                <path d="M3 9h18" />
                              </svg>
                              {art.title}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="shrink-0 border-t border-vulcan-border p-3">
            {/* Pending images preview */}
            {pendingImages.length > 0 && (
              <div className="flex gap-2 mb-2 px-1">
                {pendingImages.map((img, i) => (
                  <div key={i} className="relative">
                    <img
                      src={img.preview_url}
                      alt="To upload"
                      className="w-16 h-16 object-cover rounded-lg border border-vulcan-border"
                    />
                    <button
                      onClick={() => setPendingImages(prev => prev.filter((_, idx) => idx !== i))}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-vulcan-dark border border-vulcan-border text-vulcan-muted hover:text-white flex items-center justify-center text-xs"
                    >
                      x
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-end gap-2 max-w-2xl mx-auto">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={handleImageUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="shrink-0 w-9 h-9 rounded-lg bg-vulcan-surface border border-vulcan-border hover:border-vulcan-red/50 flex items-center justify-center text-vulcan-muted hover:text-vulcan-red transition-colors"
                title="Upload image"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <path d="M21 15l-5-5L5 21" />
                </svg>
              </button>
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder="Ask about your OmniPro 220..."
                rows={1}
                className="flex-1 resize-none rounded-lg bg-vulcan-surface border border-vulcan-border focus:border-vulcan-red/50 focus:outline-none px-3 py-2 text-sm text-vulcan-text placeholder:text-vulcan-muted"
                style={{ maxHeight: '120px' }}
                onInput={e => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = 'auto';
                  target.style.height = Math.min(target.scrollHeight, 120) + 'px';
                }}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={isLoading || (!input.trim() && pendingImages.length === 0)}
                className="shrink-0 w-9 h-9 rounded-lg bg-vulcan-red hover:bg-vulcan-red/80 disabled:bg-vulcan-surface disabled:text-vulcan-muted text-white flex items-center justify-center transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Artifact Panel */}
        {activeArtifact && (
          <div className="w-1/2 flex flex-col bg-vulcan-dark">
            {/* Artifact Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-vulcan-border shrink-0">
              <div className="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#CC0000" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M3 9h18" />
                </svg>
                <span className="text-sm font-medium text-white">
                  {activeArtifact.title}
                </span>
                <span className="text-xs text-vulcan-muted px-1.5 py-0.5 rounded bg-vulcan-surface">
                  {activeArtifact.artifact_type}
                </span>
              </div>
              <button
                onClick={() => setActiveArtifact(null)}
                className="text-vulcan-muted hover:text-white text-sm px-2 py-1 rounded hover:bg-vulcan-surface transition-colors"
              >
                Close
              </button>
            </div>
            {/* Artifact Content */}
            <div className="flex-1 p-0">
              <iframe
                srcDoc={activeArtifact.html_content}
                sandbox="allow-scripts"
                className="w-full h-full border-0"
                title={activeArtifact.title}
                style={{ background: 'white' }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
