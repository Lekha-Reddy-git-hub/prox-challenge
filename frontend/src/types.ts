export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  images?: ImageData[];
  artifacts?: Artifact[];
  toolCalls?: ToolCall[];
  timestamp: number;
}

export interface ImageData {
  data: string; // base64
  media_type: string;
  preview_url: string;
}

export interface Artifact {
  title: string;
  html_content: string;
  artifact_type: string;
}

export interface ToolCall {
  tool: string;
  input: Record<string, unknown>;
}

export interface StreamChunk {
  type: 'text' | 'artifact' | 'tool_use' | 'done' | 'error';
  content?: string;
  title?: string;
  html_content?: string;
  artifact_type?: string;
  tool?: string;
  input?: Record<string, unknown>;
}
