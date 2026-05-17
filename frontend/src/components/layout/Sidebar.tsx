import React, { useState, useEffect } from "react";
import { LayoutDashboard, Film, LineChart, Database, Gamepad2, Circle, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { api, LiveSessionStatus } from "@/lib/api";
import { GENRE_CONFIG, GENRE_KEYS, type GenreKey } from "@/lib/genres";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  genre: GenreKey;
  setGenre: (genre: GenreKey) => void;
}

export function Sidebar({ activeTab, setActiveTab, genre, setGenre }: SidebarProps) {
  const [activeSession, setActiveSession] = useState<LiveSessionStatus | null>(null);
  const [isToggling, setIsToggling] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [gameName, setGameName] = useState("");

  useEffect(() => {
    api.getActiveSession().then(setActiveSession);
    const interval = setInterval(async () => {
      const session = await api.getActiveSession();
      setActiveSession(session);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleRecordToggle = async () => {
    if (isToggling) return;
    setIsToggling(true);
    try {
      if (activeSession) {
        await api.stopSession(activeSession.session_id);
        setActiveSession(null);
      } else {
        const newSession = await api.startSession(genre, undefined, gameName || null);
        setActiveSession(newSession);
      }
    } finally {
      setIsToggling(false);
    }
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
      <div className="flex items-center gap-3 mb-10 w-full px-2">
        <div className="bg-white text-black p-1.5 rounded-lg">
          <Gamepad2 className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-bold tracking-tight text-white">
          GameSense<span className="text-primary">.ai</span>
        </h1>
      </div>

      <div className="mb-8 px-2">
        <h2 className="text-[2.5rem] leading-none font-bold text-white mb-2 tracking-tight">
          Welcome<br />Back, Ash!
        </h2>
        <p className="text-gray-400 text-sm">Current summary of your gaming sessions</p>
      </div>

      {/* Genre selector — custom dropdown to avoid shadcn SelectValue glitch */}
      <div className="mb-6 px-2 relative">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-widest block mb-2">
          Genre
        </label>
        <button
          disabled={!!activeSession}
          onClick={() => !activeSession && setDropdownOpen(o => !o)}
          className={cn(
            "w-full h-10 bg-[#121214] border border-[#27272a] rounded-xl text-white px-4 text-sm flex items-center justify-between transition-colors",
            activeSession ? "opacity-50 cursor-not-allowed" : "hover:border-[#3f3f46] cursor-pointer"
          )}
        >
          <span className="text-white">{GENRE_CONFIG[genre].label}</span>
          <svg className={cn("w-4 h-4 text-gray-400 transition-transform", dropdownOpen && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {dropdownOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setDropdownOpen(false)} />
            <div className="absolute top-full mt-1 left-0 right-0 z-20 bg-[#121214] border border-[#27272a] rounded-xl overflow-hidden shadow-xl">
              {GENRE_KEYS.map((key) => (
                <button
                  key={key}
                  onClick={() => { setGenre(key); setDropdownOpen(false); }}
                  className={cn(
                    "w-full px-4 py-2.5 text-sm text-left transition-colors",
                    key === genre
                      ? "text-primary bg-primary/10"
                      : "text-white hover:bg-[#1a1a1f]"
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

      {/* Game name input */}
      <div className="mb-6 px-2">
        <label className="text-xs font-semibold text-gray-500 uppercase tracking-widest block mb-2">
          Game
        </label>
        <input
          type="text"
          disabled={!!activeSession}
          value={gameName}
          onChange={e => setGameName(e.target.value)}
          placeholder="e.g. Mario Kart 8"
          className={cn(
            "w-full h-10 bg-[#121214] border border-[#27272a] rounded-xl text-white px-4 text-sm placeholder:text-gray-600 transition-colors outline-none",
            activeSession
              ? "opacity-50 cursor-not-allowed"
              : "hover:border-[#3f3f46] focus:border-primary/50"
          )}
        />
      </div>

      <div className="mb-4 px-2">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-widest">Home</span>
      </div>

      <nav className="flex-1 w-full space-y-1">
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

      <div className="w-full px-2 mt-auto">
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
                  : gameName
                    ? `${GENRE_CONFIG[genre].label} · ${gameName}`
                    : GENRE_CONFIG[genre].label}
              </p>
            </div>
          </div>
        </button>
      </div>
    </aside>
  );
}
