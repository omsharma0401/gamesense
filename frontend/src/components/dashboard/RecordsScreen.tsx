"use client";
import React, { useEffect, useState } from "react";
import { HardDrive, PlayCircle, Calendar } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { api, type SessionSummary } from "@/lib/api";
import { GENRE_CONFIG, type GenreKey } from "@/lib/genres";

interface Props { genre: GenreKey }

export default function RecordsScreen({ genre }: Props) {
  const [history, setHistory] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getHistory(undefined, 50).then(h => {
      setHistory(h.filter(s => s.genre === genre));
      setLoading(false);
    });
  }, [genre]);

  const formatDuration = (start: string, end: string | null) => {
    if (!end) return "Live";
    const ms   = new Date(end).getTime() - new Date(start).getTime();
    const mins = Math.floor(ms / 60000);
    const secs = Math.floor((ms % 60000) / 1000);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatDate = (d: string) =>
    new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });

  const cfg = GENRE_CONFIG[genre];

  return (
    <div className="w-full space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">Raw Recordings</h2>
          <p className="text-sm text-gray-400">{cfg.label} · {history.length} session{history.length !== 1 ? "s" : ""}</p>
        </div>

        <div className="flex items-center gap-3 bg-black border border-[#27272a] rounded-full px-6 py-3 text-sm text-gray-200 shadow-lg">
          <HardDrive className="w-4 h-4 text-primary" />
          <span className="font-semibold text-white">{history.length}</span> session{history.length !== 1 ? "s" : ""} stored
        </div>
      </div>

      <div className="bg-black border border-[#27272a] rounded-[2rem] overflow-hidden shadow-2xl p-4">
        <div className="overflow-x-auto bg-[#121214] rounded-3xl border border-[#1f1f24]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#27272a] bg-[#1a1a1f] text-gray-400 text-xs uppercase tracking-widest">
                <th className="p-6 font-semibold rounded-tl-3xl">Session</th>
                <th className="p-6 font-semibold">Genre</th>
                <th className="p-6 font-semibold">Score</th>
                <th className="p-6 font-semibold">Moments</th>
                <th className="p-6 font-semibold">Duration</th>
                <th className="p-6 font-semibold rounded-tr-3xl">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#27272a]">
              {loading && (
                <tr>
                  <td colSpan={6} className="p-10 text-center text-gray-600 text-sm">Loading…</td>
                </tr>
              )}
              {!loading && history.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-10 text-center text-gray-600 text-sm">
                    No {cfg.label} sessions recorded yet.
                  </td>
                </tr>
              )}
              {!loading && history.map((s) => {
                const statusLabel = s.ended_at ? (s.score !== null ? "Analyzed" : "Processing") : "Live";
                const statusStyle = statusLabel === "Analyzed"
                  ? "bg-primary/10 text-primary"
                  : statusLabel === "Live"
                    ? "bg-red-500/10 text-red-400"
                    : "bg-gray-800 text-gray-400";

                return (
                  <tr key={s.id} className="hover:bg-[#1f1f24] transition-colors group">
                    <td className="p-6">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-2xl bg-[#09090b] flex items-center justify-center border border-[#27272a] group-hover:border-primary/50 transition-colors shadow-inner">
                          <PlayCircle className="w-6 h-6 text-gray-400 group-hover:text-primary transition-colors" />
                        </div>
                        <div>
                          <span className="text-gray-200 font-medium block font-mono text-sm">{s.id.substring(0, 8)}…</span>
                          <Badge variant="outline" className={`px-2 py-0 border-transparent text-[10px] mt-1 ${statusStyle}`}>
                            {statusLabel}
                          </Badge>
                        </div>
                      </div>
                    </td>
                    <td className="p-6 text-gray-400 text-sm">{cfg.label}</td>
                    <td className="p-6 text-gray-300 font-mono text-sm">{s.score ?? "—"}</td>
                    <td className="p-6 text-gray-400 text-sm">{s.moments_detected}</td>
                    <td className="p-6 text-gray-300 font-mono text-sm">{formatDuration(s.started_at, s.ended_at ?? null)}</td>
                    <td className="p-6 text-gray-400 text-sm flex items-center gap-2 h-full py-9">
                      <Calendar className="w-4 h-4 opacity-50 text-gray-500" />
                      {formatDate(s.started_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
