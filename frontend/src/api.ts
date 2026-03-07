const API_BASE = "/api";

let _getAccessToken: (() => Promise<string>) | null = null;

/**
 * Called once from a React component to wire up the Auth0
 * getAccessTokenSilently function so api helpers can attach JWTs.
 */
export function setTokenGetter(fn: () => Promise<string>) {
  _getAccessToken = fn;
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (_getAccessToken) {
    try {
      const token = await _getAccessToken();
      headers["Authorization"] = `Bearer ${token}`;
    } catch (err) {
      console.error("Failed to get access token:", err);
    }
  }

  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

export async function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiFetch("/documents/upload", {
    method: "POST",
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}

export async function listDocuments() {
  const res = await apiFetch("/documents/");
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to fetch documents");
  return data;
}

export async function getDocumentUrl(path: string) {
  const res = await apiFetch(`/documents/url?path=${encodeURIComponent(path)}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to get document URL");
  return data as { url: string };
}

type VoiceSessionResponse = {
  agent_id: string;
  webrtc_token: string;
  connection_type: string;
};

const voiceApiKey = () => {
  const key = import.meta.env.VITE_VOICE_AGENT_API_KEY;
  if (!key) {
    throw new Error("VITE_VOICE_AGENT_API_KEY is not configured in the frontend.");
  }
  return key;
};

export async function createVoiceSession(): Promise<VoiceSessionResponse> {
  const res = await apiFetch("/voice/session", {
    method: "POST",
    headers: {
      "X-API-Key": voiceApiKey(),
    },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to create voice session");
  }

  return data as VoiceSessionResponse;
}

export async function createBackboardThread(name: string): Promise<{ thread_id: string }> {
  const res = await apiFetch("/voice/backboard/thread", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": voiceApiKey(),
    },
    body: JSON.stringify({ name }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to create Backboard thread");
  }

  return data as { thread_id: string };
}

export async function voiceThink(params: {
  thread_id: string;
  user_utterance: string;
  session_id?: string | null;
}): Promise<{ answer: string }> {
  const res = await apiFetch("/voice/think", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": voiceApiKey(),
    },
    body: JSON.stringify({
      thread_id: params.thread_id,
      user_utterance: params.user_utterance,
      session_id: params.session_id ?? null,
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Voice think failed");
  }

  return data as { answer: string };
}
