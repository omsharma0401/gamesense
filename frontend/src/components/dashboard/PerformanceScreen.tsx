"use client";
import React, { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, Zap, Target, Flame } from "lucide-react";
import { api, type SessionSummary, type Briefing } from "@/lib/api";
import { GENRE_CONFIG, type GenreKey } from "@/lib/genres";

interface Props { genre: GenreKey; game?: string | null }

interface ChartPoint {
  date: string;
  overall: number;
  mechanics: number;
  decisions: number;
  consistency: number;
}

export default function PerformanceScreen({ genre, game }: Props) {
  const [history, setHistory] = useState<SessionSummary[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const cfg = GENRE_CONFIG[genre];

  useEffect(() => {
    setLoading(true);
    async function load() {
      const [hist, brief] = await Promise.all([api.getHistory(undefined, 50, game), api.getBriefing()]);
      setHistory(hist.filter(h => h.genre === genre).reverse()); // oldest first for chart
      setBriefing(brief);
      setLoading(false);
    }
    load();
  }, [genre, game]);

  const filteredHistory = history;

  // Only use sessions that have completed analysis (score != null)
  const analyzedHistory = filteredHistory.filter(s => s.score !== null);
  const latestSession   = analyzedHistory.length > 0 ? analyzedHistory[analyzedHistory.length - 1] : null;

  const chartData: ChartPoint[] = analyzedHistory.map((s) => ({
    date:        new Date(s.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    overall:     s.score            ?? 0,
    mechanics:   s.mechanics        ?? 0,
    decisions:   s.decision_making  ?? 0,
    consistency: s.consistency      ?? 0,
  }));

  const overallScore  = latestSession?.score ?? null;
  const focusAreas    = briefing?.focus_areas?.length ? briefing.focus_areas : [];
  const coachingText  = briefing?.coaching_paragraph ?? null;

  const totalMoments  = filteredHistory.reduce((acc, s) => acc + s.moments_detected, 0);
  const avgScore      = analyzedHistory.length > 0
    ? Math.round(analyzedHistory.reduce((acc, s) => acc + (s.score ?? 0), 0) / analyzedHistory.length)
    : null;

  return (
    <div className="w-full space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">Performance Overview</h2>
          <p className="text-sm text-gray-400">
            {cfg.label}{game ? ` · ${game}` : ""} · {filteredHistory.length} session{filteredHistory.length !== 1 ? "s" : ""} recorded
            {filteredHistory.length > analyzedHistory.length && ` · ${analyzedHistory.length} analyzed`}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 bg-black border border-[#27272a] rounded-[2.5rem] p-10 flex flex-col justify-between">
          <div className="flex justify-between items-start mb-8">
            <div>
              <h3 className="text-xl text-white font-semibold mb-6">Overall Skill Rating</h3>
              <div className="flex items-end gap-4">
                <span className="text-6xl font-bold tracking-tighter text-white">
                  {overallScore ?? "—"}
                </span>
                {overallScore !== null && (
                  <Badge className="bg-primary/20 text-primary hover:bg-primary/30 border-transparent rounded-full px-3 py-1 mb-2">
                    Latest session
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {chartData.length === 0 && (
            <div className="h-[250px] flex items-center justify-center text-gray-600 text-sm">
              No session data yet — play a {cfg.label} session to see your trend.
            </div>
          )}
          {chartData.length > 0 && (
            <div className="h-[250px] w-full" style={{ minWidth: 0, minHeight: 250 }} suppressHydrationWarning>
              {mounted && (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gOverall" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={cfg.color} stopOpacity={0.5} />
                        <stop offset="95%" stopColor={cfg.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" stroke="#3f3f46" tick={{ fill: "#71717a", fontSize: 12 }} axisLine={false} tickLine={false} dy={10} />
                    <Tooltip contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", borderRadius: "1rem", color: "#fff", padding: "12px" }} />
                    <Legend wrapperStyle={{ color: "#71717a", fontSize: 12, paddingTop: 12 }} />
                    <Area type="monotone" dataKey="overall" name="Overall" stroke={cfg.color} strokeWidth={3} fillOpacity={1} fill="url(#gOverall)" />
                    <Area type="monotone" dataKey="mechanics" name="Mechanics" stroke="#3b82f6" strokeWidth={2} fill="none" />
                    <Area type="monotone" dataKey="decisions" name="Decisions" stroke="#a855f7" strokeWidth={2} fill="none" />
                    <Area type="monotone" dataKey="consistency" name="Consistency" stroke="#f97316" strokeWidth={2} fill="none" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Genre summary card — replaces dead "Find Coach" CTA */}
          <div className="bg-black border border-[#27272a] rounded-[2.5rem] p-8 relative overflow-hidden">
            <div className="absolute inset-0 opacity-20 pointer-events-none" style={{ backgroundImage: "radial-gradient(circle at center, #ccff00 1px, transparent 1px)", backgroundSize: "16px 16px" }} />
            <div className="absolute -right-10 -top-10 w-40 h-40 blur-3xl rounded-full" style={{ backgroundColor: `${cfg.color}33` }} />
            <div className="relative z-10 flex flex-col gap-6 min-h-[180px] justify-between">
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Flame className="w-4 h-4" style={{ color: cfg.color }} />
                  <span className="text-xs font-bold tracking-widest uppercase" style={{ color: cfg.color }}>{cfg.label}</span>
                </div>
                <h3 className="text-2xl font-bold text-white leading-tight mb-1">
                  {filteredHistory.length === 0 ? "No sessions yet" : `${filteredHistory.length} session${filteredHistory.length !== 1 ? "s" : ""} played`}
                </h3>
                <p className="text-sm text-gray-400">
                  {totalMoments > 0
                    ? `${totalMoments} moment${totalMoments !== 1 ? "s" : ""} detected · avg score ${avgScore ?? "—"}`
                    : `${game ? `No ${game} sessions yet.` : "Start recording to build your performance history."}`}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white/5 rounded-2xl p-3 text-center">
                  <p className="text-2xl font-bold text-white">{avgScore ?? "—"}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">Avg score</p>
                </div>
                <div className="bg-white/5 rounded-2xl p-3 text-center">
                  <p className="text-2xl font-bold text-white">{totalMoments}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5">Moments</p>
                </div>
              </div>
            </div>
          </div>

          {focusAreas.length > 0 && (
            <div className="bg-black border border-[#27272a] rounded-[2rem] p-8">
              <div className="flex justify-between items-center mb-6">
                <h4 className="text-white font-semibold flex items-center gap-2">
                  <Target className="w-5 h-5 text-gray-400" /> Focus Areas
                </h4>
                <span className="text-xs text-gray-500 font-mono">{focusAreas.length} areas</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {focusAreas.map((area, i) => (
                  <div key={i} className="bg-[#121214] border border-[#27272a] text-gray-300 px-4 py-2 rounded-xl text-sm hover:border-primary/50 transition-colors cursor-default shadow-inner">
                    {area}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-[#121214] rounded-[2rem] p-8 border border-[#27272a]">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-3">
            <div className="p-2 rounded-full bg-blue-500/10 text-blue-400"><TrendingUp className="w-5 h-5" /></div>
            AI Coaching Brief
          </h3>
          <p className="text-gray-400 leading-relaxed text-[15px]">
            {coachingText ?? (
              history.length === 0
                ? `Play your first ${cfg.label} session and GameSense will build a personalised coaching brief.`
                : "Generating coaching insights from your session history…"
            )}
          </p>
        </div>

        <div className="bg-[#121214] rounded-[2rem] p-8 border border-[#27272a]">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-3">
            <div className="p-2 rounded-full bg-red-500/10 text-red-500"><Zap className="w-5 h-5" /></div>
            Latest Session Stats
          </h3>
          {latestSession ? (
            <div className="space-y-3">
              {[
                { label: "Overall",     sub: "Combined score",                    value: latestSession.score },
                { label: "Mechanics",   sub: "Aim, movement, execution",          value: latestSession.mechanics },
                { label: "Decisions",   sub: "Positioning, timing, strategy",     value: latestSession.decision_making },
                { label: "Consistency", sub: "How stable your performance was",   value: latestSession.consistency },
              ].map(({ label, sub, value }) => (
                <div key={label} className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <span className="text-gray-300 text-sm font-medium">{label}</span>
                    <p className="text-gray-600 text-[11px] leading-tight">{sub}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-1.5 bg-[#27272a] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${value ?? 0}%`, backgroundColor: cfg.color }}
                      />
                    </div>
                    <span className="text-white font-mono text-sm w-8 text-right">{value ?? "—"}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No completed sessions for {cfg.label} yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
