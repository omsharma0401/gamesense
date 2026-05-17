"use client";
import React, { useState, useEffect, useMemo } from "react";
import { Play, MonitorPlay } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, type Clip } from "@/lib/api";
import HlsPlayer from "@/components/ui/HlsPlayer";
import { GENRE_CONFIG, type GenreKey, type MomentType } from "@/lib/genres";

interface Props { genre: GenreKey }

export default function AllClipsScreen({ genre }: Props) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<MomentType | "all">("all");

  const cfg = GENRE_CONFIG[genre];

  useEffect(() => {
    setActiveFilter("all");
    setLoading(true);
    async function load() {
      const history = await api.getHistory();
      const genreHistory = history.filter(h => h.genre === genre);

      const allClips: Clip[] = [];
      await Promise.all(
        genreHistory.map(async (s) => {
          const c = await api.getClips(s.id);
          allClips.push(...c);
        })
      );
      // Sort newest first (by start_time descending — proxy for recency within session)
      setClips(allClips);
      setLoading(false);
    }
    load();
  }, [genre]);

  // Count per type for showing/hiding filter badges
  const typeCounts = useMemo(() => {
    const counts: Partial<Record<MomentType, number>> = {};
    for (const c of clips) {
      counts[c.type as MomentType] = (counts[c.type as MomentType] ?? 0) + 1;
    }
    return counts;
  }, [clips]);

  const filtered = activeFilter === "all" ? clips : clips.filter(c => c.type === activeFilter);

  return (
    <div className="w-full space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">

      {/* Header */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">All Clips</h2>
          <p className="text-sm text-gray-400">{cfg.label} · {clips.length} clip{clips.length !== 1 ? "s" : ""} across all sessions</p>
        </div>
      </div>

      {/* Filter badges — hidden when count = 0 */}
      <div className="flex gap-3 flex-wrap">
        <button
          onClick={() => setActiveFilter("all")}
          className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors border ${
            activeFilter === "all"
              ? "bg-white text-black border-white"
              : "bg-[#1a1a1f] text-white border-[#27272a] hover:bg-[#27272a]"
          }`}
        >
          All Moments <span className="ml-1 opacity-60">{clips.length}</span>
        </button>

        {cfg.filters.map((type) => {
          const count = typeCounts[type] ?? 0;
          if (count === 0) return null;
          const isActive = activeFilter === type;
          const colorClass = cfg.tagColors[type] ?? "text-gray-400 border-gray-700";
          return (
            <button
              key={type}
              onClick={() => setActiveFilter(type)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors border ${
                isActive
                  ? "bg-white text-black border-white"
                  : `bg-[#1a1a1f] ${colorClass} hover:bg-[#27272a]`
              }`}
            >
              {cfg.momentLabels[type]} <span className="ml-1 opacity-60">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-gray-500 text-sm py-16 text-center">Loading clips…</div>
      )}

      {/* Empty state */}
      {!loading && clips.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
          <MonitorPlay className="w-12 h-12 text-gray-700" />
          <h3 className="text-white font-semibold text-lg">No clips yet</h3>
          <p className="text-gray-500 text-sm max-w-xs">
            Play a {cfg.label} session and moments will be captured automatically.
          </p>
        </div>
      )}

      {/* Clips grid */}
      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filtered.map((clip) => {
            const type = clip.type as MomentType;
            const label    = cfg.momentLabels[type] ?? type.toUpperCase();
            const tagColor = cfg.tagColors[type]    ?? "text-gray-400 border-gray-700";
            const pts      = cfg.skillPts[type]     ?? 10;
            const dur      = Math.max(0, clip.end_time - clip.start_time);
            const durStr   = `${Math.floor(dur / 60)}:${Math.floor(dur % 60).toString().padStart(2, "0")}`;

            return (
              <div key={clip.id} className="bg-[#0f1015] rounded-[1.5rem] p-4 group border border-[#1f2029]">
                {/* Thumbnail / preview area */}
                <div className="aspect-video rounded-[1rem] relative flex items-center justify-center cursor-pointer overflow-hidden mb-4 border border-[#2a2b36]">
                  {clip.thumbnail_url
                    ? <img src={clip.thumbnail_url} alt={label} className="absolute inset-0 w-full h-full object-cover" />
                    : <div className="absolute inset-0 bg-[#1a1b26]" />
                  }
                  <div className="absolute inset-0 bg-black/40" />
                  <div className="absolute top-4 left-4 z-10">
                    <Badge variant="outline" className={`${tagColor} border px-2 py-0.5 text-[10px] font-bold tracking-widest rounded-md bg-black/60`}>
                      {label}
                    </Badge>
                  </div>
                  <div className="absolute bottom-4 right-4 text-xs font-mono bg-black/60 px-2 py-1 rounded-md text-white z-10">
                    {durStr}
                  </div>

                  {/* Play button / watch dialog */}
                  <Dialog>
                    <DialogTrigger render={<button className="w-14 h-14 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 hover:bg-white/20 transition-all z-10" />}>
                      <Play className="w-6 h-6 text-white ml-0.5" />
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl w-full bg-[#141523] border-[#202136] text-white p-0 rounded-2xl overflow-hidden">
                      <div className="p-5 border-b border-[#202136] flex items-center gap-3">
                        <Badge variant="outline" className={`${tagColor} border px-2 py-0.5 text-xs font-bold rounded-md`}>{label}</Badge>
                        <DialogTitle className="text-white font-semibold">{clip.commentary}</DialogTitle>
                      </div>
                      <div className="aspect-video w-full bg-black">
                        {clip.stream_url
                          ? <HlsPlayer src={clip.stream_url} className="w-full h-full" autoPlay />
                          : <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">Stream URL not available</div>
                        }
                      </div>
                      <div className="p-5 text-sm text-gray-400">{clip.commentary}</div>
                    </DialogContent>
                  </Dialog>
                </div>

                <div className="px-2 pb-2">
                  <h3 className="text-white font-bold text-lg mb-1">{label}</h3>
                  <p className="text-gray-400 text-sm mb-4 line-clamp-2">{clip.commentary}</p>
                  <div className="flex justify-between items-center text-xs">
                    <span className={`font-bold ${pts >= 0 ? "text-primary" : "text-destructive"}`}>
                      {pts >= 0 ? "▲" : "▼"} {Math.abs(pts)} skill pts
                    </span>
                    <span className="text-gray-600 font-mono">{durStr}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Filtered empty state */}
      {!loading && clips.length > 0 && filtered.length === 0 && (
        <div className="text-gray-500 text-sm py-16 text-center">
          No {cfg.momentLabels[activeFilter as MomentType]} clips in this genre yet.
        </div>
      )}
    </div>
  );
}
