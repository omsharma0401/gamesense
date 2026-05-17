export const API_BASE_URL = "http://localhost:8000";
export const DEFAULT_PLAYER_ID = "player-001";

export interface SessionSummary {
  id: string;
  game: string;
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
  start_time: number;
  end_time: number;
  commentary: string;
  type: string;
}

export interface HighlightReel {
  id: string;
  session_id: string;
  stream_url: string | null;
  duration: number | null;
  status: string;
  created_at: string;
}

export interface LiveSessionStatus {
  session_id: string;
  game: string;
  player_id: string;
  status: string;
  moments_detected: number;
  elapsed_seconds: number;
  latest_moment: string | null;
}

export const api = {
  getHistory: async (playerId: string = DEFAULT_PLAYER_ID, limit: number = 10): Promise<SessionSummary[]> => {
    try {
      const res = await fetch(`${API_BASE_URL}/analysis/history/${playerId}?limit=${limit}`);
      if (!res.ok) return [];
      return res.json();
    } catch (e) {
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
      if (!res.ok) return [];
      return res.json();
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

  startSession: async (game: string = "Asphalt 9", playerId: string = DEFAULT_PLAYER_ID): Promise<LiveSessionStatus | null> => {
    try {
      const res = await fetch(`${API_BASE_URL}/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game, player_id: playerId })
      });
      if (!res.ok) return null;
      return res.json();
    } catch (e) {
      return null;
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
