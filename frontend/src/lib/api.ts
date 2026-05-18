import type { GenreKey } from "./genres";

export const API_BASE_URL = "http://localhost:8000";
export const DEFAULT_PLAYER_ID = "ash";

export interface SessionSummary {
  id: string;
  genre: GenreKey;
  game_name: string | null;
  score: number | null;
  mechanics: number | null;
  decision_making: number | null;
  consistency: number | null;
  moments_detected: number;
  started_at: string;
  ended_at: string | null;
}

export interface Briefing {
  id: string;
  player_id: string;
  coaching_paragraph: string;
  focus_areas: string[];
  session_count: number;
  created_at: string;
}

export interface Score {
  overall: number;
  mechanics: number;
  decision_making: number;
  consistency: number;
}

export interface Clip {
  id: string;
  moment_id: string;
  session_id: string;
  stream_url: string;
  thumbnail_url: string | null;
  start_time: number;
  end_time: number;
  commentary: string;
  type: string;
}

export interface Moment {
  id: string;
  session_id: string;
  type: string;
  timestamp_ms: number;
  description: string;
  significance: number;
  clip_url: string | null;
  commentary: string | null;
  created_at: string;
}

export interface AnalysisResult {
  session_id: string;
  score: Score;
  moments: Moment[];
  clips: Clip[];
  patterns: string[];
  summary: string;
  epic_summary: string | null;
  persona: string | null;
  status: string;
  created_at: string;
}

export interface HighlightReel {
  id: string;
  session_id: string;
  stream_url: string | null;
  vertical_stream_url: string | null;
  duration: number | null;
  status: string;
  created_at: string;
}

export interface Suggestion {
  id: string;
  session_id: string;
  text: string;
  type: "hype" | "warning" | "tip" | "focus";
  trigger: string;
  significance: number;
  audio_url: string | null;
  created_at: string;
}

export interface LiveSessionStatus {
  session_id: string;
  genre: GenreKey;
  game_name: string | null;
  player_id: string;
  status: string;
  moments_detected: number;
  elapsed_seconds: number;
  latest_moment: string | null;
}

export const api = {
  getHistory: async (playerId: string = DEFAULT_PLAYER_ID, limit: number = 10, gameName?: string | null): Promise<SessionSummary[]> => {
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (gameName) params.set("game_name", gameName);
      const res = await fetch(`${API_BASE_URL}/analysis/history/${playerId}?${params}`);
      if (!res.ok) return [];
      return res.json();
    } catch (e) {
      return [];
    }
  },

  getGameNames: async (playerId: string = DEFAULT_PLAYER_ID, genre?: string): Promise<string[]> => {
    try {
      const params = genre ? `?genre=${encodeURIComponent(genre)}` : "";
      const res = await fetch(`${API_BASE_URL}/analysis/games/${playerId}${params}`);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  },

  getBriefing: async (playerId: string = DEFAULT_PLAYER_ID): Promise<Briefing | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/analysis/briefing/${playerId}`);
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  },

  getClips: async (sessionId: string): Promise<Clip[]> => {
    try {
      const res = await fetch(`${API_BASE_URL}/clips/${sessionId}`);
      if (!res.ok || res.status !== 200) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  },

  getHighlightReel: async (sessionId: string): Promise<HighlightReel | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/clips/highlight/${sessionId}`);
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  },
  
  getActiveSession: async (): Promise<LiveSessionStatus | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/session/active`);
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  },

  startSession: async (genre: GenreKey = "arcade-racing", playerId: string = DEFAULT_PLAYER_ID, gameName?: string | null): Promise<LiveSessionStatus | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ genre, player_id: playerId, game_name: gameName || null })
      });
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  },

  getAnalysis: async (sessionId: string): Promise<AnalysisResult | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/analysis/${sessionId}`);
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  },

  triggerVerticalHighlight: async (sessionId: string): Promise<HighlightReel | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/clips/highlight/${sessionId}/vertical`, {
        method: 'POST',
      });
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  },

  getSuggestions: async (sessionId: string, since_ms?: number): Promise<Suggestion[]> => {
    try {
      const url = `${API_BASE_URL}/suggestions/${sessionId}${since_ms ? `?since_ms=${since_ms}` : ""}`;
      const res = await fetch(url);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  },

  stopSession: async (sessionId: string): Promise<any> => {
    try {
      const res = await fetch(`${API_BASE_URL}/session/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
    }
  }
};
