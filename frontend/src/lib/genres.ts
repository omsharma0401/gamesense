export type MomentType = "kill" | "death" | "clutch" | "error" | "strategy_break" | "highlight" | "blunder";
export type GenreKey = "arcade-racing" | "tactical-shooter" | "rts" | "turn-based-tactics";

interface GenreConfig {
  label: string;
  color: string;
  momentLabels: Record<MomentType, string>;
  filters: MomentType[];
  skillPts: Partial<Record<MomentType, number>>;
  tagColors: Partial<Record<MomentType, string>>;
}

export const GENRE_CONFIG: Record<GenreKey, GenreConfig> = {
  "arcade-racing": {
    label: "Arcade Racing",
    color: "#ccff00",
    momentLabels: {
      kill:           "Overtake",
      death:          "Crashed Out",
      clutch:         "Clutch Recovery",
      error:          "Missed Apex",
      strategy_break: "Pit Strategy",
      highlight:      "Best Lap",
      blunder:        "Crash",
    },
    filters: ["highlight", "clutch", "blunder", "error"],
    skillPts: { clutch: 20, highlight: 15, kill: 10, error: -8, death: -10, blunder: -15, strategy_break: 5 },
    tagColors: {
      highlight: "text-primary border-primary/30",
      clutch:    "text-white border-white/20",
      blunder:   "text-destructive border-destructive/30",
      error:     "text-yellow-400 border-yellow-500/30",
      death:     "text-destructive border-destructive/30",
      kill:      "text-primary border-primary/30",
      strategy_break: "text-blue-400 border-blue-500/30",
    },
  },
  "tactical-shooter": {
    label: "Tactical Shooter (FPS)",
    color: "#a855f7",
    momentLabels: {
      kill:           "Kill",
      death:          "Death",
      clutch:         "Clutch",
      error:          "Mistake",
      strategy_break: "Strat Break",
      highlight:      "Highlight",
      blunder:        "Blunder",
    },
    filters: ["kill", "clutch", "highlight", "death", "blunder"],
    skillPts: { kill: 10, clutch: 20, highlight: 15, error: -8, death: -5, blunder: -15, strategy_break: 5 },
    tagColors: {
      kill:      "text-primary border-primary/30",
      clutch:    "text-white border-white/20",
      highlight: "text-primary border-primary/30",
      death:     "text-destructive border-destructive/30",
      blunder:   "text-destructive border-destructive/30",
      error:     "text-yellow-400 border-yellow-500/30",
      strategy_break: "text-blue-400 border-blue-500/30",
    },
  },
  "rts": {
    label: "Real-Time Strategy (RTS)",
    color: "#3b82f6",
    momentLabels: {
      kill:           "Unit Trade",
      death:          "Base Raid",
      clutch:         "Clutch Defense",
      error:          "Eco Error",
      strategy_break: "Tech Switch",
      highlight:      "Key Battle",
      blunder:        "Blunder",
    },
    filters: ["highlight", "clutch", "strategy_break", "blunder", "error"],
    skillPts: { highlight: 15, clutch: 20, strategy_break: 10, kill: 8, error: -8, death: -10, blunder: -15 },
    tagColors: {
      highlight: "text-primary border-primary/30",
      clutch:    "text-white border-white/20",
      strategy_break: "text-blue-400 border-blue-500/30",
      blunder:   "text-destructive border-destructive/30",
      error:     "text-yellow-400 border-yellow-500/30",
      kill:      "text-primary border-primary/30",
      death:     "text-destructive border-destructive/30",
    },
  },
  "turn-based-tactics": {
    label: "Turn-Based Tactics",
    color: "#f97316",
    momentLabels: {
      kill:           "Elimination",
      death:          "Unit Lost",
      clutch:         "Clutch Move",
      error:          "Tactical Error",
      strategy_break: "Pivot",
      highlight:      "Perfect Turn",
      blunder:        "Blunder",
    },
    filters: ["highlight", "clutch", "strategy_break", "blunder", "error"],
    skillPts: { highlight: 15, clutch: 20, strategy_break: 10, kill: 8, error: -8, death: -5, blunder: -15 },
    tagColors: {
      highlight: "text-primary border-primary/30",
      clutch:    "text-white border-white/20",
      strategy_break: "text-blue-400 border-blue-500/30",
      blunder:   "text-destructive border-destructive/30",
      error:     "text-yellow-400 border-yellow-500/30",
      kill:      "text-primary border-primary/30",
      death:     "text-yellow-400 border-yellow-500/30",
    },
  },
};

export const GENRE_KEYS = Object.keys(GENRE_CONFIG) as GenreKey[];
