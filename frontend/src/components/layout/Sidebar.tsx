import React, { useState, useEffect } from "react";
import { LayoutDashboard, Film, LineChart, Database, Gamepad2, Plus, Zap, Circle } from "lucide-react";
import { HugeIcon } from "hugeicons-react"; // I'll use Lucide mostly for consistency but add a few HugeIcons if needed
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { api, LiveSessionStatus } from "@/lib/api";

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  const [activeSession, setActiveSession] = useState<LiveSessionStatus | null>(null);
  const [isToggling, setIsToggling] = useState(false);

  useEffect(() => {
    // Initial fetch
    api.getActiveSession().then(setActiveSession);
    
    // Poll every 2 seconds
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
        const newSession = await api.startSession();
        setActiveSession(newSession);
      }
    } finally {
      setIsToggling(false);
    }
  };

  const menuItems = [
    { id: "clips", label: "All Clips", icon: LayoutDashboard },
    { id: "highlights", label: "Highlights", icon: Film },
    { id: "performance", label: "Performance", icon: LineChart },
    { id: "records", label: "Last Records", icon: Database },
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

      <div className="mb-10 px-2">
        <h2 className="text-[2.5rem] leading-none font-bold text-white mb-2 tracking-tight">
          Welcome<br />Back, Agent!
        </h2>
        <p className="text-gray-400 text-sm">Current summary of your gaming sessions</p>
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
              <item.icon className={cn("w-[22px] h-[22px]", isActive ? "text-black" : "text-gray-500 group-hover:text-gray-300")} strokeWidth={isActive ? 2.5 : 2} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="w-full px-2 mt-auto space-y-4">
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
                {activeSession ? `${activeSession.moments_detected} moments` : "Capture gameplay"}
              </p>
            </div>
          </div>
        </button>

        <div className="flex items-center justify-between text-gray-400 mb-2 px-2 mt-6">
          <span className="text-xs font-semibold uppercase tracking-widest">Upgrades</span>
          <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center cursor-pointer hover:scale-110 transition-transform">
            <Plus className="w-4 h-4 text-black" strokeWidth={3} />
          </div>
        </div>
        
        <div className="p-4 rounded-2xl bg-[#121214] border border-[#27272a] hover:border-primary/50 transition-colors cursor-pointer group">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-5 h-5 text-primary" />
            <h4 className="text-white text-sm font-semibold">Pro Version</h4>
          </div>
          <p className="text-xs text-gray-500">Unlock unlimited AI processing & cloud storage.</p>
        </div>
      </div>
    </aside>
  );
}
