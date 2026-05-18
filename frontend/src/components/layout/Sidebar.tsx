import React, { useState, useEffect, useRef } from "react";
import { LayoutDashboard, Film, LineChart, Database, Gamepad2, Circle, Sparkles, Zap, AlertTriangle, Lightbulb, Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { api, LiveSessionStatus, type Suggestion } from "@/lib/api";
import { GENRE_CONFIG, GENRE_KEYS, type GenreKey } from "@/lib/genres";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  genre: GenreKey;
  setGenre: (genre: GenreKey) => void;
  game: string | null;
  setGame: (game: string | null) => void;
}

export function Sidebar({ activeTab, setActiveTab, genre, setGenre, game, setGame }: SidebarProps) {
  const [activeSession, setActiveSession] = useState<LiveSessionStatus | null>(null);
  const [isToggling, setIsToggling] = useState(false);
  const [genreDropdownOpen, setGenreDropdownOpen] = useState(false);
  const [gameDropdownOpen, setGameDropdownOpen] = useState(false);
  const [addingGame, setAddingGame] = useState(false);
  const [newGameInput, setNewGameInput] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [savedGames, setSavedGames] = useState<string[]>([]);
  const sinceMs = useRef(0);

  useEffect(() => {
    api.getActiveSession().then(setActiveSession);
    const interval = setInterval(async () => {
      const session = await api.getActiveSession();
      setActiveSession(session);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Load distinct game names for the current genre
  useEffect(() => {
    api.getGameNames(undefined, genre).then(setSavedGames);
  }, [genre]);

  // Poll for live coaching suggestions while a session is active
  useEffect(() => {
    if (!activeSession) {
      setSuggestions([]);
      sinceMs.current = 0;
      return;
    }
    const interval = setInterval(async () => {
      const fresh = await api.getSuggestions(activeSession.session_id, sinceMs.current);
      if (fresh.length > 0) {
        const rawTs = fresh[fresh.length - 1].created_at;
        const newest = new Date(rawTs.endsWith("Z") ? rawTs : rawTs + "Z").getTime();
        sinceMs.current = newest + 1; // exclusive — skip exact boundary
        setSuggestions(prev => [...prev, ...fresh].slice(-5));
        // Auto-play the most recent cue's voice if available
        const latest = fresh[fresh.length - 1];
        if (latest.audio_url) {
          try {
            new Audio(latest.audio_url).play();
          } catch { /* ignore autoplay policy errors */ }
        }
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [activeSession?.session_id]);

  const handleRecordToggle = async () => {
    if (isToggling) return;
    setIsToggling(true);
    try {
      if (activeSession) {
        await api.stopSession(activeSession.session_id);
        setActiveSession(null);
        // Refresh game list after session ends
        api.getGameNames(undefined, genre).then(setSavedGames);
      } else {
        const newSession = await api.startSession(genre, undefined, game || null);
        setActiveSession(newSession);
      }
    } finally {
      setIsToggling(false);
    }
  };

  const handleAddGame = () => {
    const name = newGameInput.trim();
    if (!name) { setAddingGame(false); return; }
    setGame(name);
    setSavedGames(prev => prev.includes(name) ? prev : [...prev, name].sort());
    setNewGameInput("");
    setAddingGame(false);
  };

  const menuItems = [
    { id: "clips",       label: "All Clips",    icon: LayoutDashboard },
    { id: "highlights",  label: "Highlights",   icon: Film },
    { id: "performance", label: "Performance",  icon: LineChart },
    { id: "wrapped",     label: "Session Wrap", icon: Sparkles },
    { id: "records",     label: "Raw Records",  icon: Database },
  ];

  return (
    <aside className="w-full h-full flex flex-col py-6 pl-2 pr-6 bg-transparent relative z-10">

      {/* Logo — always pinned at top */}
      <div className="flex items-center gap-3 mb-6 w-full px-2 flex-shrink-0">
        <div className="bg-white text-black p-1.5 rounded-lg">
          <Gamepad2 className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-bold tracking-tight text-white">
          GameSense<span className="text-primary">.ai</span>
        </h1>
      </div>

      {/* Scrollable middle — shrinks to give space to bottom section */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-none">

      <div className="mb-8 px-2">
        <h2 className="text-[2.5rem] leading-none font-bold text-white mb-2 tracking-tight">
          Welcome<br />Back, Ash!
        </h2>
        <p className="text-gray-400 text-sm">Current summary of your gaming sessions</p>
      </div>

      {/* Genre selector */}
      <div className="mb-4 px-2 relative">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-widest block mb-2">
          Genre
        </label>
        <button
          disabled={!!activeSession}
          onClick={() => !activeSession && setGenreDropdownOpen(o => !o)}
          className={cn(
            "w-full h-10 bg-[#121214] border border-[#27272a] rounded-xl text-white px-4 text-sm flex items-center justify-between transition-colors",
            activeSession ? "opacity-50 cursor-not-allowed" : "hover:border-[#3f3f46] cursor-pointer"
          )}
        >
          <span className="text-white">{GENRE_CONFIG[genre].label}</span>
          <svg className={cn("w-4 h-4 text-gray-400 transition-transform", genreDropdownOpen && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {genreDropdownOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setGenreDropdownOpen(false)} />
            <div className="absolute top-full mt-1 left-0 right-0 z-20 bg-[#121214] border border-[#27272a] rounded-xl overflow-hidden shadow-xl">
              {GENRE_KEYS.map((key) => (
                <button
                  key={key}
                  onClick={() => { setGenre(key); setGenreDropdownOpen(false); }}
                  className={cn(
                    "w-full px-4 py-2.5 text-sm text-left transition-colors",
                    key === genre ? "text-primary bg-primary/10" : "text-white hover:bg-[#1a1a1f]"
                  )}
                >
                  {GENRE_CONFIG[key].label}
                </button>
              ))}
            </div>
          </>
        )}
        {activeSession && (
          <p className="text-xs text-gray-600 mt-1.5">Stop recording to change genre.</p>
        )}
      </div>

      {/* Game selector */}
      <div className="mb-6 px-2 relative">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-widest block mb-2">
          Game
        </label>

        {addingGame ? (
          <div className="flex gap-2">
            <input
              autoFocus
              type="text"
              value={newGameInput}
              onChange={e => setNewGameInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") handleAddGame(); if (e.key === "Escape") { setAddingGame(false); setNewGameInput(""); } }}
              onBlur={handleAddGame}
              placeholder="e.g. Mario Kart 8"
              className="flex-1 h-10 bg-[#121214] border border-primary/50 rounded-xl text-white px-4 text-sm placeholder:text-gray-600 outline-none"
            />
          </div>
        ) : (
          <button
            disabled={!!activeSession}
            onClick={() => !activeSession && setGameDropdownOpen(o => !o)}
            className={cn(
              "w-full h-10 bg-[#121214] border border-[#27272a] rounded-xl text-white px-4 text-sm flex items-center justify-between transition-colors",
              activeSession ? "opacity-50 cursor-not-allowed" : "hover:border-[#3f3f46] cursor-pointer"
            )}
          >
            <span className={game ? "text-white" : "text-gray-500"}>
              {game ?? "All games"}
            </span>
            <svg className={cn("w-4 h-4 text-gray-400 transition-transform", gameDropdownOpen && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}

        {gameDropdownOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setGameDropdownOpen(false)} />
            <div className="absolute top-full mt-1 left-0 right-0 z-20 bg-[#121214] border border-[#27272a] rounded-xl overflow-hidden shadow-xl">
              <button
                onClick={() => { setGame(null); setGameDropdownOpen(false); }}
                className={cn(
                  "w-full px-4 py-2.5 text-sm text-left transition-colors",
                  !game ? "text-primary bg-primary/10" : "text-gray-400 hover:bg-[#1a1a1f] hover:text-white"
                )}
              >
                All games
              </button>
              {savedGames.map(name => (
                <button
                  key={name}
                  onClick={() => { setGame(name); setGameDropdownOpen(false); }}
                  className={cn(
                    "w-full px-4 py-2.5 text-sm text-left transition-colors",
                    game === name ? "text-primary bg-primary/10" : "text-white hover:bg-[#1a1a1f]"
                  )}
                >
                  {name}
                </button>
              ))}
              <button
                onClick={() => { setGameDropdownOpen(false); setAddingGame(true); }}
                className="w-full px-4 py-2.5 text-sm text-left text-gray-500 hover:bg-[#1a1a1f] hover:text-white transition-colors border-t border-[#27272a]"
              >
                + Add new game…
              </button>
            </div>
          </>
        )}
        {activeSession && (
          <p className="text-xs text-gray-600 mt-1.5">Stop recording to change game.</p>
        )}
      </div>

      <div className="mb-4 px-2">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-widest">Home</span>
      </div>

      <nav className="w-full space-y-1">
        {menuItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                "flex items-center gap-4 w-full px-4 py-3.5 rounded-2xl transition-all duration-300 font-medium text-[15px] relative group",
                isActive
                  ? "bg-white text-black shadow-lg"
                  : "text-gray-400 hover:text-white"
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 bg-white rounded-2xl -z-10"
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
              <item.icon
                className={cn("w-[22px] h-[22px]", isActive ? "text-black" : "text-gray-500 group-hover:text-gray-300")}
                strokeWidth={isActive ? 2.5 : 2}
              />
              {item.label}
            </button>
          );
        })}
      </nav>

      </div>{/* end scrollable middle */}

      {/* Bottom — record button + coaching feed, always visible */}
      <div className="flex-shrink-0 pt-3">
      <div className="w-full px-2">
        <button
          onClick={handleRecordToggle}
          disabled={isToggling}
          className={cn(
            "w-full p-4 rounded-2xl border transition-all flex items-center justify-between group cursor-pointer",
            activeSession
              ? "bg-red-500/10 border-red-500/50 hover:bg-red-500/20"
              : "bg-[#121214] border-[#27272a] hover:border-primary/50 hover:bg-[#1a1a1f]"
          )}
        >
          <div className="flex items-center gap-3">
            <Circle className={cn(
              "w-5 h-5",
              activeSession ? "text-red-500 animate-pulse fill-red-500" : "text-gray-400 group-hover:text-primary"
            )} />
            <div className="text-left">
              <h4 className={cn("text-sm font-semibold", activeSession ? "text-red-500" : "text-white")}>
                {activeSession ? "Recording..." : "Start Recording"}
              </h4>
              <p className="text-xs text-gray-500">
                {activeSession
                  ? `${activeSession.moments_detected} moments · ${activeSession.game_name ?? GENRE_CONFIG[activeSession.genre]?.label ?? activeSession.genre}`
                  : game
                    ? `${GENRE_CONFIG[genre].label} · ${game}`
                    : GENRE_CONFIG[genre].label}
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* Live coaching feed — only visible during a session */}
      <AnimatePresence>
        {activeSession && suggestions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="w-full px-2 mt-3 overflow-hidden"
          >
            <p className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest mb-2">
              Live Coach
            </p>
            <div className="space-y-1.5">
              <AnimatePresence initial={false}>
                {suggestions.slice(-3).map((s) => {
                  const Icon = { hype: Zap, warning: AlertTriangle, tip: Lightbulb, focus: Eye }[s.type] ?? Zap;
                  const color = { hype: "text-green-400", warning: "text-red-400", tip: "text-yellow-400", focus: "text-blue-400" }[s.type] ?? "text-gray-400";
                  return (
                    <motion.div
                      key={s.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.25 }}
                      className="flex items-start gap-2 bg-[#111114] border border-[#1f1f24] rounded-xl px-3 py-2"
                    >
                      <Icon className={cn("w-3 h-3 mt-0.5 flex-shrink-0", color)} />
                      <p className="text-[11px] text-gray-300 leading-tight">{s.text}</p>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>{/* end bottom */}
    </aside>
  );
}
