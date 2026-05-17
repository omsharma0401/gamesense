"use client";
import React, { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence, animate } from "framer-motion";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";
import { Play, Share2, TrendingUp, Zap, Target, Trophy, Flame, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { api, type SessionSummary, type AnalysisResult, type Clip, type HighlightReel } from "@/lib/api";
import { GENRE_CONFIG, type GenreKey, type MomentType } from "@/lib/genres";
import HlsPlayer from "@/components/ui/HlsPlayer";

interface Props { genre: GenreKey; game?: string | null }

// ── Animated number counter ──────────────────────────────────────────────────
function AnimatedNumber({ target, duration = 1.2, className }: { target: number; duration?: number; className?: string }) {
  const [display, setDisplay] = useState(0);
  const prevTarget = useRef(0);

  useEffect(() => {
    const from = prevTarget.current;
    prevTarget.current = target;
    const controls = animate(from, target, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return controls.stop;
  }, [target, duration]);

  return <span className={className}>{display}</span>;
}

// ── Persona gradient map ──────────────────────────────────────────────────────
const PERSONA_COLORS: Record<string, { from: string; to: string; accent: string }> = {
  default:  { from: "#1a0533", to: "#2d1065", accent: "#a855f7" },
  clutch:   { from: "#0f1a33", to: "#1e3a8a", accent: "#60a5fa" },
  aggress:  { from: "#330a0a", to: "#7f1d1d", accent: "#f87171" },
  smooth:   { from: "#0a2318", to: "#14532d", accent: "#4ade80" },
  tactical: { from: "#1a1205", to: "#451a03", accent: "#fb923c" },
};

function getPersonaTheme(persona: string | null) {
  if (!persona) return PERSONA_COLORS.default;
  const lower = persona.toLowerCase();
  if (lower.includes("clutch") || lower.includes("pressure")) return PERSONA_COLORS.clutch;
  if (lower.includes("aggress") || lower.includes("frag") || lower.includes("rush")) return PERSONA_COLORS.aggress;
  if (lower.includes("smooth") || lower.includes("consistent") || lower.includes("anchor")) return PERSONA_COLORS.smooth;
  if (lower.includes("tactic") || lower.includes("support") || lower.includes("macro")) return PERSONA_COLORS.tactical;
  return PERSONA_COLORS.default;
}

// ── Pattern icons ─────────────────────────────────────────────────────────────
const PATTERN_ICONS = [Trophy, Flame, Zap, Target, TrendingUp, Trophy];

export default function WrappedScreen({ genre, game }: Props) {
  const [sessions, setSessions]     = useState<SessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [analysis, setAnalysis]     = useState<AnalysisResult | null>(null);
  const [reel, setReel]             = useState<HighlightReel | null>(null);
  const [loading, setLoading]       = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [verticalLoading, setVerticalLoading] = useState(false);

  const cfg = GENRE_CONFIG[genre];

  // Load session list
  useEffect(() => {
    setLoading(true);
    setSelectedId(null);
    api.getHistory(undefined, 20, game).then(h => {
      const analyzed = h.filter(s => s.genre === genre && s.score !== null);
      setSessions(analyzed);
      if (analyzed.length > 0) setSelectedId(analyzed[0].id); // most recent first
      else setLoading(false);
    });
  }, [genre, game]);

  // Load analysis when selected session changes
  useEffect(() => {
    if (!selectedId) return;
    setAnalysisLoading(true);
    setAnalysis(null);
    setReel(null);
    Promise.all([
      api.getAnalysis(selectedId),
      api.getHighlightReel(selectedId),
    ]).then(([a, r]) => {
      setAnalysis(a);
      setReel(r);
      setAnalysisLoading(false);
      setLoading(false);
    });
  }, [selectedId]);

  const selectedSession = sessions.find(s => s.id === selectedId) ?? null;
  const theme           = getPersonaTheme(analysis?.persona ?? null);

  const radarData = analysis ? [
    { subject: "Mechanics",   value: analysis.score.mechanics       },
    { subject: "Decisions",   value: analysis.score.decision_making },
    { subject: "Consistency", value: analysis.score.consistency     },
    { subject: "Overall",     value: analysis.score.overall         },
  ] : [];

  const topClip = analysis?.clips.reduce<Clip | null>(
    (best, c) => {
      const m = analysis.moments.find(mo => mo.id === c.moment_id);
      const bestM = best ? analysis.moments.find(mo => mo.id === best.moment_id) : null;
      return !best || (m?.significance ?? 0) > (bestM?.significance ?? 0) ? c : best;
    },
    null
  );

  const typeCount = (analysis?.moments ?? []).reduce<Record<string, number>>((acc, m) => {
    acc[m.type] = (acc[m.type] ?? 0) + 1;
    return acc;
  }, {});
  const dominantType = Object.entries(typeCount).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

  const handleVertical = async () => {
    if (!selectedId || verticalLoading) return;
    setVerticalLoading(true);
    await api.triggerVerticalHighlight(selectedId);
    // Polling handled by effect below — don't clear loading here
  };

  // Poll for vertical completion while loading
  useEffect(() => {
    if (!verticalLoading || !selectedId) return;
    const interval = setInterval(async () => {
      const updated = await api.getHighlightReel(selectedId);
      if (updated?.vertical_stream_url) {
        setReel(updated);
        setVerticalLoading(false);
      }
    }, 4000);
    const timeout = setTimeout(() => setVerticalLoading(false), 10 * 60 * 1000);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [verticalLoading, selectedId]);

  // ── Empty state ──────────────────────────────────────────────────────────────
  if (!loading && sessions.length === 0) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-24 gap-4 text-center animate-in fade-in duration-500">
        <Trophy className="w-12 h-12 text-gray-700" />
        <h3 className="text-white font-semibold text-lg">No analyzed sessions yet</h3>
        <p className="text-gray-500 text-sm max-w-xs">
          Complete a {cfg.label} session — the AI will break it down Spotify Wrapped style.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

      {/* ── Header + session picker ────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-1">Session Wrap</h2>
          <p className="text-sm text-gray-400">{cfg.label} · Your session in numbers</p>
        </div>

        {sessions.length > 1 && (
          <div className="flex items-center gap-2 flex-wrap">
            {sessions.slice(0, 5).map((s, i) => (
              <button
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-mono transition-all border ${
                  s.id === selectedId
                    ? "bg-white text-black border-white"
                    : "bg-[#121214] text-gray-400 border-[#27272a] hover:border-primary/50"
                }`}
              >
                Session {sessions.length - i}
              </button>
            ))}
          </div>
        )}
      </div>

      {(loading || analysisLoading) && (
        <div className="text-gray-500 text-sm py-16 text-center">Analysing session…</div>
      )}

      {!loading && !analysisLoading && analysis && selectedSession && (
        <AnimatePresence mode="wait">
          <motion.div
            key={selectedId}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="space-y-6"
          >
            {/* ── Hero card ─────────────────────────────────────────────────── */}
            <div
              className="relative rounded-[2.5rem] overflow-hidden p-10 min-h-[240px] flex flex-col justify-between border border-white/10"
              style={{ background: `linear-gradient(135deg, ${theme.from} 0%, ${theme.to} 60%, #0d0d0f 100%)` }}
            >
              {/* Background glow */}
              <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full blur-3xl opacity-30"
                style={{ backgroundColor: theme.accent }} />

              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xs font-bold tracking-widest uppercase px-3 py-1 rounded-full border"
                    style={{ color: theme.accent, borderColor: `${theme.accent}40`, backgroundColor: `${theme.accent}15` }}>
                    {cfg.label}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">
                    {new Date(selectedSession.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                  </span>
                  {selectedSession.game_name && (
                    <span className="text-xs text-gray-400">· {selectedSession.game_name}</span>
                  )}
                </div>

                {analysis.epic_summary && (
                  <p className="text-2xl md:text-3xl font-bold text-white leading-tight mb-1 max-w-lg">
                    {analysis.epic_summary}
                  </p>
                )}
                {analysis.persona && (
                  <p className="text-sm font-semibold mt-2" style={{ color: theme.accent }}>
                    {analysis.persona}
                  </p>
                )}
              </div>

              <div className="relative z-10 flex items-end gap-6">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">Score</p>
                  <p className="text-7xl font-black text-white leading-none">
                    <AnimatedNumber target={analysis.score.overall} />
                  </p>
                </div>
                <div className="pb-2 grid grid-cols-3 gap-4">
                  {[
                    { label: "Mechanics",   value: analysis.score.mechanics       },
                    { label: "Decisions",   value: analysis.score.decision_making },
                    { label: "Consistency", value: analysis.score.consistency     },
                  ].map(({ label, value }) => (
                    <div key={label} className="text-center">
                      <p className="text-2xl font-bold text-white">
                        <AnimatedNumber target={value} duration={1.5} />
                      </p>
                      <p className="text-[10px] text-gray-500 uppercase tracking-widest">{label}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ── Stats row ─────────────────────────────────────────────────── */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Moments",    value: analysis.moments.length,   icon: Zap,        color: "#f97316" },
                { label: "Clips",      value: analysis.clips.length,     icon: Play,       color: "#a855f7" },
                { label: "Patterns",   value: analysis.patterns.length,  icon: Target,     color: "#06b6d4" },
                { label: "Best Type",  value: dominantType ? cfg.momentLabels[dominantType as MomentType] ?? dominantType : "—", icon: Flame, color: "#22c55e", isText: true },
              ].map(({ label, value, icon: Icon, color, isText }) => (
                <div key={label} className="bg-black border border-[#27272a] rounded-[1.5rem] p-5 flex flex-col gap-2">
                  <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${color}20` }}>
                    <Icon className="w-4 h-4" style={{ color }} />
                  </div>
                  <p className="text-2xl font-bold text-white">
                    {isText ? value : <AnimatedNumber target={value as number} duration={1.0} />}
                  </p>
                  <p className="text-[11px] text-gray-500 uppercase tracking-widest">{label}</p>
                </div>
              ))}
            </div>

            {/* ── Skill radar + coach note ───────────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Radar chart */}
              <div className="bg-black border border-[#27272a] rounded-[2rem] p-8">
                <h3 className="text-white font-semibold mb-6 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-gray-400" /> Skill Breakdown
                </h3>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                      <PolarGrid stroke="#27272a" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: "#71717a", fontSize: 11 }} />
                      <Radar
                        name="Score"
                        dataKey="value"
                        stroke={theme.accent}
                        fill={theme.accent}
                        fillOpacity={0.25}
                        strokeWidth={2}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Coach's note */}
              <div className="bg-black border border-[#27272a] rounded-[2rem] p-8 flex flex-col">
                <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-yellow-400" /> Coach's Note
                </h3>
                <p className="text-gray-300 leading-relaxed text-sm flex-1">
                  {analysis.summary}
                </p>
              </div>
            </div>

            {/* ── Patterns ─────────────────────────────────────────────────── */}
            {analysis.patterns.length > 0 && (
              <div className="bg-black border border-[#27272a] rounded-[2rem] p-8">
                <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
                  <Target className="w-4 h-4 text-gray-400" /> What The AI Spotted
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {analysis.patterns.map((pattern, i) => {
                    const Icon = PATTERN_ICONS[i % PATTERN_ICONS.length];
                    return (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.07, duration: 0.3 }}
                        className="flex items-start gap-3 bg-[#0f0f11] border border-[#1f1f24] rounded-2xl p-4"
                      >
                        <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <Icon className="w-3.5 h-3.5 text-primary" />
                        </div>
                        <p className="text-gray-300 text-sm leading-relaxed">{pattern}</p>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Signature moment + highlight reel ─────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Signature clip */}
              {topClip && (
                <div className="bg-black border border-[#27272a] rounded-[2rem] p-6">
                  <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                    <Trophy className="w-4 h-4 text-yellow-400" /> Signature Moment
                  </h3>
                  <div className="space-y-3">
                    {topClip.thumbnail_url && (
                      <div className="aspect-video rounded-2xl overflow-hidden relative">
                        <img src={topClip.thumbnail_url} alt="moment thumbnail" className="w-full h-full object-cover" />
                        <div className="absolute inset-0 bg-black/30" />
                      </div>
                    )}
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className={`${cfg.tagColors[topClip.type as MomentType] ?? "text-gray-400 border-gray-700"} border text-[10px] font-bold px-2 py-0.5`}>
                        {cfg.momentLabels[topClip.type as MomentType] ?? topClip.type.toUpperCase()}
                      </Badge>
                    </div>
                    <p className="text-gray-300 text-sm">{topClip.commentary}</p>
                    <Dialog>
                      <DialogTrigger render={<button className="flex items-center gap-2 text-primary text-sm font-medium hover:underline" />}>
                        <Play className="w-4 h-4" /> Watch clip
                      </DialogTrigger>
                      <DialogContent className="max-w-3xl w-full bg-[#0d0d0f] border-[#27272a] text-white p-0 rounded-2xl overflow-hidden">
                        <div className="p-5 border-b border-[#27272a]">
                          <DialogTitle className="text-white font-semibold">{topClip.commentary}</DialogTitle>
                        </div>
                        <div className="aspect-video w-full bg-black">
                          <HlsPlayer src={topClip.stream_url} className="w-full h-full" autoPlay />
                        </div>
                      </DialogContent>
                    </Dialog>
                  </div>
                </div>
              )}

              {/* Highlight reel */}
              {reel && (
                <div className="bg-black border border-[#27272a] rounded-[2rem] p-6">
                  <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                    <Flame className="w-4 h-4 text-orange-400" /> Highlight Reel
                  </h3>
                  <div className="space-y-3">
                    {reel.status === "complete" && reel.stream_url ? (
                      <>
                        <Dialog>
                          <DialogTrigger render={<div className="aspect-video bg-gradient-to-br from-orange-500/20 to-black rounded-2xl border border-[#27272a] flex items-center justify-center cursor-pointer hover:border-orange-500/50 transition-colors group" />}>
                            <div className="w-14 h-14 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center group-hover:scale-110 transition-transform">
                              <Play className="w-6 h-6 text-white ml-1" />
                            </div>
                          </DialogTrigger>
                          <DialogContent className="max-w-3xl w-full bg-[#0d0d0f] border-[#27272a] text-white p-0 rounded-2xl overflow-hidden">
                            <div className="p-5 border-b border-[#27272a]">
                              <DialogTitle>
                                {selectedSession.game_name ?? cfg.label} Highlight Reel
                                {reel.duration && <span className="text-gray-400 text-sm ml-2 font-normal">
                                  {Math.floor(reel.duration / 60)}:{Math.floor(reel.duration % 60).toString().padStart(2, "0")}
                                </span>}
                              </DialogTitle>
                            </div>
                            <div className="aspect-video w-full bg-black">
                              <HlsPlayer src={reel.stream_url} className="w-full h-full" autoPlay />
                            </div>
                          </DialogContent>
                        </Dialog>

                        <div className="flex gap-2">
                          {reel.vertical_stream_url ? (
                            <Dialog>
                              <DialogTrigger render={<button className="flex-1 py-2 rounded-xl border border-[#27272a] text-xs text-gray-300 hover:border-primary/50 transition-colors flex items-center justify-center gap-1" />}>
                                <Share2 className="w-3 h-3" /> Watch 9:16
                              </DialogTrigger>
                              <DialogContent className="max-w-sm w-full bg-[#0d0d0f] border-[#27272a] text-white p-0 rounded-2xl overflow-hidden">
                                <div className="p-5 border-b border-[#27272a]">
                                  <DialogTitle>Vertical Highlight</DialogTitle>
                                </div>
                                <div className="w-full" style={{ aspectRatio: "9/16" }}>
                                  <HlsPlayer src={reel.vertical_stream_url} className="w-full h-full" autoPlay />
                                </div>
                              </DialogContent>
                            </Dialog>
                          ) : (
                            <button
                              onClick={handleVertical}
                              disabled={verticalLoading}
                              className="flex-1 py-2 rounded-xl border border-[#27272a] text-xs text-gray-400 hover:border-primary/50 hover:text-gray-200 transition-colors flex items-center justify-center gap-1 disabled:opacity-50"
                            >
                              <Share2 className="w-3 h-3" />
                              {verticalLoading ? "Reframing — check back in a min…" : "Make 9:16 for Reels"}
                            </button>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="aspect-video bg-[#0f0f11] rounded-2xl border border-[#1f1f24] flex items-center justify-center">
                        <p className="text-gray-600 text-sm">
                          {reel.status === "generating" ? "Generating reel…" : "Highlight reel not available"}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* ── Clips carousel ────────────────────────────────────────────── */}
            {analysis.clips.length > 0 && (
              <div className="bg-black border border-[#27272a] rounded-[2rem] p-8">
                <h3 className="text-white font-semibold mb-5 flex items-center gap-2">
                  <Play className="w-4 h-4 text-gray-400" /> All Clips
                  <span className="text-xs text-gray-600 font-normal ml-1">{analysis.clips.length} moments captured</span>
                </h3>
                <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-[#27272a] scrollbar-track-transparent">
                  {analysis.clips.map((clip) => {
                    const type     = clip.type as MomentType;
                    const label    = cfg.momentLabels[type] ?? type.toUpperCase();
                    const tagColor = cfg.tagColors[type]    ?? "text-gray-400 border-gray-700";
                    const dur      = Math.max(0, clip.end_time - clip.start_time);
                    const durStr   = `${Math.floor(dur / 60)}:${Math.floor(dur % 60).toString().padStart(2, "0")}`;
                    return (
                      <Dialog key={clip.id}>
                        <DialogTrigger render={<div className="flex-shrink-0 w-48 cursor-pointer group" />}>
                            <div className="aspect-video bg-[#1a1b26] rounded-2xl overflow-hidden relative border border-[#2a2b36] group-hover:border-primary/50 transition-colors mb-2">
                              {clip.thumbnail_url
                                ? <img src={clip.thumbnail_url} alt={label} className="w-full h-full object-cover" />
                                : <div className="w-full h-full bg-[#1a1b26]" />
                              }
                              <div className="absolute inset-0 bg-black/30" />
                              <div className="absolute inset-0 flex items-center justify-center">
                                <div className="w-10 h-10 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center group-hover:scale-110 transition-transform">
                                  <Play className="w-4 h-4 text-white ml-0.5" />
                                </div>
                              </div>
                              <div className="absolute bottom-2 right-2 text-[10px] font-mono bg-black/60 px-1.5 py-0.5 rounded text-white">
                                {durStr}
                              </div>
                              <Badge variant="outline" className={`absolute top-2 left-2 ${tagColor} border text-[9px] font-bold px-1.5 py-0.5 rounded bg-black/60`}>
                                {label}
                              </Badge>
                            </div>
                            <p className="text-gray-400 text-xs line-clamp-2 px-1">{clip.commentary}</p>
                        </DialogTrigger>
                        <DialogContent className="max-w-3xl w-full bg-[#0d0d0f] border-[#27272a] text-white p-0 rounded-2xl overflow-hidden">
                          <div className="p-5 border-b border-[#27272a] flex items-center gap-3">
                            <Badge variant="outline" className={`${tagColor} border text-xs font-bold`}>{label}</Badge>
                            <DialogTitle className="text-white font-semibold">{clip.commentary}</DialogTitle>
                          </div>
                          <div className="aspect-video w-full bg-black">
                            <HlsPlayer src={clip.stream_url} className="w-full h-full" autoPlay />
                          </div>
                        </DialogContent>
                      </Dialog>
                    );
                  })}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  );
}
