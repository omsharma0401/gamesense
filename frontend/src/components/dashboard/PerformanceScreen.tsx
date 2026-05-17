import React, { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { HugeIcon } from "hugeicons-react";
import { Zap, Target, TrendingUp, Crosshair, ChevronDown, Award } from "lucide-react";
import { motion } from "framer-motion";
import { api, SessionSummary, Briefing } from "@/lib/api";

const GAME_DATA = {
  "asphalt-9": {
    name: "Asphalt 9",
    tags: ["Drafting", "Nitro Timing", "Route Choice", "Wreck Avoidance", "Perfect Run"],
    summary: "Your handling in tight corners has improved by 15% this week. You're maintaining top speed much better on straightaways.",
    detailedOverview: "Previously, your nitro management was sporadic. Recently, you've shown a stark improvement in conserving nitro for drafting and utilizing perfect runs. However, your route choices on Cairo tracks remain sub-optimal. Focus on taking the higher ramps to maintain aerial speed advantage.",
    score: "87",
    scoreChange: "+12%",
    chartData: [
      { time: "00:00", score: 50 }, { time: "01:30", score: 85 }, { time: "02:45", score: 30 },
      { time: "04:00", score: 95 }, { time: "05:15", score: 70 }, { time: "06:30", score: 80 },
    ],
    color: "#ccff00" // Neon Green
  },
  "mortal-kombat": {
    name: "Mortal Kombat Arena",
    tags: ["Combo Breaker", "Flawless Block", "Fatal Blow Setup", "Punish Timing", "Corner Trap"],
    summary: "Incredible defensive performance. You successfully executed Flawless Blocks 40% more often than your running average.",
    detailedOverview: "Your spacing in the neutral game is solidifying. Last month, you struggled against projectile zoning, but your dash-block technique has improved tremendously. The AI noticed a slight weakness when you're pushed into the corner yourself. Work on patient wake-ups.",
    score: "92",
    scoreChange: "+18%",
    chartData: [
      { time: "00:00", score: 40 }, { time: "00:45", score: 20 }, { time: "01:30", score: 90 },
      { time: "02:15", score: 85 }, { time: "03:00", score: 45 }, { time: "04:10", score: 100 },
    ],
    color: "#a855f7" // Neon Purple
  }
};

export default function PerformanceScreen() {
  const [game, setGame] = useState("asphalt-9");
  const [history, setHistory] = React.useState<SessionSummary[]>([]);
  const [briefing, setBriefing] = React.useState<Briefing | null>(null);

  React.useEffect(() => {
    async function loadData() {
      const [histData, briefData] = await Promise.all([
        api.getHistory(),
        api.getBriefing()
      ]);
      setHistory(histData.reverse()); // Oldest first
      setBriefing(briefData);
    }
    loadData();
  }, []);

  const gameHistory = history.filter(h => h.game.toLowerCase().includes(game.replace("-", " ")));
  const latestSession = gameHistory.length > 0 ? gameHistory[gameHistory.length - 1] : null;

  const data = {
    name: game === "asphalt-9" ? "Asphalt 9" : "Mortal Kombat Arena",
    tags: briefing?.focus_areas?.length ? briefing.focus_areas : GAME_DATA[game as keyof typeof GAME_DATA].tags,
    summary: GAME_DATA[game as keyof typeof GAME_DATA].summary,
    detailedOverview: briefing?.coaching_paragraph || GAME_DATA[game as keyof typeof GAME_DATA].detailedOverview,
    score: latestSession?.score?.toString() || GAME_DATA[game as keyof typeof GAME_DATA].score,
    scoreChange: "+12%", // Hardcoded for now
    chartData: gameHistory.length > 0 
      ? gameHistory.map((s, i) => ({ time: `S${i+1}`, score: s.score || 0 }))
      : GAME_DATA[game as keyof typeof GAME_DATA].chartData,
    color: GAME_DATA[game as keyof typeof GAME_DATA].color
  };

  return (
    <div className="w-full space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header matching screenshot's Portfolio Overview */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">
            Performance Overview
          </h2>
          <div className="flex items-center gap-3 text-sm text-gray-400">
            <span>Overview &gt;</span>
            <span className="text-gray-500">All Metrics</span>
          </div>
        </div>

        <div className="flex items-center gap-4 bg-black rounded-full p-1.5 border border-[#27272a]">
          <Select value={game} onValueChange={setGame}>
            <SelectTrigger className="w-[200px] h-10 bg-transparent border-transparent text-white px-4 hover:bg-[#1a1a1f] rounded-full focus:ring-0">
              <SelectValue placeholder="Select Game" />
            </SelectTrigger>
            <SelectContent className="bg-[#121214] border-[#27272a] text-white rounded-2xl">
              <SelectItem value="asphalt-9" className="rounded-xl focus:bg-[#1a1a1f] focus:text-white cursor-pointer py-2">Asphalt 9</SelectItem>
              <SelectItem value="mortal-kombat" className="rounded-xl focus:bg-[#1a1a1f] focus:text-white cursor-pointer py-2">Mortal Kombat</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Big Analytics Card (Asset Allocation equivalent) */}
        <div className="lg:col-span-2 bg-black border border-[#27272a] rounded-[2.5rem] p-10 flex flex-col justify-between">
          <div className="flex justify-between items-start mb-8">
            <div>
              <h3 className="text-xl text-white font-semibold mb-6">Overall Skill Rating</h3>
              <div className="flex items-end gap-4">
                <span className="text-6xl font-bold tracking-tighter text-white">{data.score}</span>
                <Badge className="bg-primary/20 text-primary hover:bg-primary/30 border-transparent rounded-full px-3 py-1 mb-2">
                  {data.scoreChange} Improvement
                </Badge>
              </div>
            </div>
            
            <div className="bg-[#121214] border border-[#27272a] rounded-full px-4 py-2 flex items-center gap-2 cursor-pointer hover:bg-[#1a1a1f] transition-colors">
              <span className="text-sm text-white">This Week</span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </div>
          </div>

          <div className="h-[250px] w-full mt-auto">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.chartData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={data.color} stopOpacity={0.6} />
                    <stop offset="95%" stopColor={data.color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#3f3f46" tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} dy={10} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#09090b', borderColor: '#27272a', borderRadius: '1rem', color: '#fff', padding: '12px' }}
                  itemStyle={{ color: data.color, fontWeight: 'bold' }}
                />
                <Area type="monotone" dataKey="score" stroke={data.color} strokeWidth={4} fillOpacity={1} fill="url(#colorScore)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right Column Stack */}
        <div className="space-y-6">
          {/* Neon Hero Card */}
          <div className="bg-black border border-[#27272a] rounded-[2.5rem] p-8 relative overflow-hidden group">
            {/* Cool background wavy lines simulation */}
            <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at center, #ccff00 1px, transparent 1px)', backgroundSize: '16px 16px' }} />
            <div className="absolute -right-10 -top-10 w-40 h-40 bg-primary/20 blur-3xl rounded-full" />
            
            <div className="relative z-10 flex flex-col h-full justify-between min-h-[220px]">
              <div>
                <h3 className="text-2xl font-bold text-white mb-2 leading-tight">Master <br />Your Strategy</h3>
                <p className="text-sm text-gray-400 max-w-[80%]">Get 1-on-1 coaching with top players based on your stats.</p>
              </div>
              <button className="bg-primary text-black font-bold py-3 px-6 rounded-full w-max flex items-center gap-2 hover:bg-primary/90 hover:scale-105 transition-all">
                Find Coach <Award className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Strategy Tags Card styled like the dots */}
          <div className="bg-black border border-[#27272a] rounded-[2rem] p-8">
            <div className="flex justify-between items-center mb-6">
               <h4 className="text-white font-semibold flex items-center gap-2">
                 <Target className="w-5 h-5 text-gray-400" />
                 Strategy Focus
               </h4>
               <span className="text-xs text-gray-500 font-mono">Top 5</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.tags.map((tag, i) => (
                <div key={i} className="bg-[#121214] border border-[#27272a] text-gray-300 px-4 py-2 rounded-xl text-sm hover:border-primary/50 transition-colors cursor-default shadow-inner">
                  {tag}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-[#121214] rounded-[2rem] p-8 border border-[#27272a]">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-3">
            <div className="p-2 rounded-full bg-blue-500/10 text-blue-400"><TrendingUp className="w-5 h-5" /></div>
            Detailed AI Overview
          </h3>
          <p className="text-gray-400 leading-relaxed text-[15px]">
            {data.detailedOverview}
          </p>
        </div>

        <div className="bg-[#121214] rounded-[2rem] p-8 border border-[#27272a]">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-3">
            <div className="p-2 rounded-full bg-red-500/10 text-red-500"><Zap className="w-5 h-5" /></div>
            Agent Summary
          </h3>
          <p className="text-gray-400 leading-relaxed text-[15px]">
            {data.summary}
            <br /><br />
            <span className="text-white font-semibold">Key Weakness: </span>
            {game === "asphalt-9" ? "You lose speed significantly when attempting 360s off low ramps. Stick to barrel rolls." : "You are highly susceptible to low attacks on wake-up. Block low immediately."}
          </p>
        </div>
      </div>

    </div>
  );
}
