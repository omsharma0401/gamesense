"use client";
import React, { useEffect, useRef, useState } from "react";
import { Play, Film, Share2, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { api, type HighlightReel, type SessionSummary } from "@/lib/api";
import { GENRE_CONFIG, type GenreKey } from "@/lib/genres";
import HlsPlayer from "@/components/ui/HlsPlayer";

interface Props { genre: GenreKey; game?: string | null }

interface ReelWithSession {
  reel: HighlightReel;
  session: SessionSummary;
}

const GRADIENTS = [
  "from-[#a855f7]/40 to-black",
  "from-primary/30 to-black",
  "from-red-500/30 to-black",
  "from-blue-500/30 to-black",
];

export default function HighlightsScreen({ genre, game }: Props) {
  const [items, setItems]       = useState<ReelWithSession[]>([]);
  const [loading, setLoading]   = useState(true);
  const [reelUpdates, setReelUpdates] = useState<Record<string, HighlightReel>>({});
  const [verticalProcessing, setVerticalProcessing] = useState<Set<string>>(new Set());
  const processingRef = useRef<Set<string>>(new Set());

  const cfg = GENRE_CONFIG[genre];

  useEffect(() => {
    setLoading(true);
    setReelUpdates({});
    setVerticalProcessing(new Set());
    async function load() {
      const history = await api.getHistory(undefined, 20, game);
      const genreHistory = history.filter(h => h.genre === genre);
      const results = await Promise.all(
        genreHistory.map(async (s) => {
          const reel = await api.getHighlightReel(s.id);
          return reel ? { reel, session: s } : null;
        })
      );
      setItems(results.filter(Boolean) as ReelWithSession[]);
      setLoading(false);
    }
    load();
  }, [genre, game]);

  // Poll for vertical completion on all currently-processing sessions
  useEffect(() => {
    processingRef.current = verticalProcessing;
    if (verticalProcessing.size === 0) return;

    const interval = setInterval(async () => {
      const ids = [...processingRef.current];
      await Promise.all(ids.map(async (sessionId) => {
        const updated = await api.getHighlightReel(sessionId);
        if (updated?.vertical_stream_url) {
          setReelUpdates(prev => ({ ...prev, [sessionId]: updated }));
          setVerticalProcessing(prev => {
            const next = new Set(prev);
            next.delete(sessionId);
            return next;
          });
        }
      }));
    }, 4000);

    return () => clearInterval(interval);
  }, [verticalProcessing]);

  const handleMakeVertical = async (sessionId: string) => {
    setVerticalProcessing(prev => new Set([...prev, sessionId]));
    await api.triggerVerticalHighlight(sessionId);
  };

  const visibleItems = items;

  const getEffectiveReel = (reel: HighlightReel, sessionId: string): HighlightReel =>
    reelUpdates[sessionId] ?? reel;

  const formatDur = (sec: number | null) => {
    if (!sec) return "—";
    return `${Math.floor(sec / 60)}:${Math.floor(sec % 60).toString().padStart(2, "0")}`;
  };

  return (
    <div className="w-full space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">Highlight Reels</h2>
          <p className="text-sm text-gray-400">
            {cfg.label}{game ? ` · ${game}` : ""} · {visibleItems.length} reel{visibleItems.length !== 1 ? "s" : ""} · Generated automatically after each session
          </p>
        </div>
      </div>

      {loading && (
        <div className="text-gray-500 text-sm py-16 text-center">Loading reels…</div>
      )}

      {!loading && visibleItems.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <Film className="w-12 h-12 text-gray-700" />
          <h3 className="text-white font-semibold text-lg">No highlight reels yet</h3>
          <p className="text-gray-500 text-sm max-w-xs">
            Complete a {cfg.label} session — the AI will compile your best moments automatically.
          </p>
        </div>
      )}

      {!loading && visibleItems.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {visibleItems.map(({ reel: originalReel, session }, i) => {
            const reel       = getEffectiveReel(originalReel, session.id);
            const processing = verticalProcessing.has(session.id);

            return (
              <div key={reel.id} className="flex flex-col gap-3">
                {/* Landscape reel card */}
                <Dialog>
                  <div className="group cursor-pointer">
                    <DialogTrigger nativeButton={false} render={<div className={`aspect-[4/3] rounded-[2rem] bg-gradient-to-br ${GRADIENTS[i % GRADIENTS.length]} border border-[#27272a] group-hover:border-primary/50 transition-all relative flex items-center justify-center overflow-hidden mb-5 shadow-lg`} />}>
                        {reel.thumbnail_url
                          ? <img src={reel.thumbnail_url} alt="Highlight thumbnail" className="absolute inset-0 w-full h-full object-cover" />
                          : null
                        }
                        <div className="absolute inset-0 bg-black/40 group-hover:bg-black/20 transition-colors duration-500" />
                        <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center shadow-[0_0_30px_rgba(0,0,0,0.5)] transform group-hover:scale-110 transition-transform duration-500 z-10 border border-white/20">
                          <Play className="w-7 h-7 text-white ml-1" />
                        </div>
                        <div className="absolute bottom-4 right-4 bg-black/80 backdrop-blur px-3 py-1.5 rounded-full text-xs font-mono text-white z-10 border border-white/10">
                          {reel.status === "generating" ? "Generating…" : formatDur(reel.duration)}
                        </div>
                    </DialogTrigger>

                    <h3 className="text-white font-semibold text-lg group-hover:text-primary transition-colors px-2">
                      {session.game_name ?? cfg.label} · Highlight
                    </h3>
                    <p className="text-gray-500 text-sm mt-1 px-2">
                      {new Date(reel.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                    </p>
                  </div>

                  <DialogContent className="max-w-3xl w-full bg-[#0d0d0f] border-[#27272a] text-white p-0 rounded-2xl overflow-hidden">
                    <div className="p-5 border-b border-[#27272a] flex items-center justify-between">
                      <DialogTitle className="text-white font-semibold">
                        {session.game_name ?? cfg.label} Highlight Reel
                        {reel.duration && (
                          <span className="text-gray-500 text-sm font-normal ml-2">
                            {Math.floor(reel.duration / 60)}:{Math.floor(reel.duration % 60).toString().padStart(2, "0")}
                          </span>
                        )}
                      </DialogTitle>
                    </div>
                    <div className="aspect-video w-full bg-black">
                      {reel.stream_url
                        ? <HlsPlayer src={reel.stream_url} className="w-full h-full" autoPlay />
                        : <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                            {reel.status === "generating" ? "Generating reel — check back shortly." : "Stream URL not available."}
                          </div>
                      }
                    </div>
                  </DialogContent>
                </Dialog>

                {/* Vertical reel actions — only show when landscape reel is complete */}
                {reel.status === "complete" && (
                  <div className="px-2">
                    {reel.vertical_stream_url ? (
                      /* Watch 9:16 */
                      <Dialog>
                        <DialogTrigger render={<button className="flex items-center gap-1.5 text-xs text-primary font-medium hover:underline" />}>
                          <Share2 className="w-3 h-3" /> Watch 9:16 vertical
                        </DialogTrigger>
                        <DialogContent className="max-w-xs w-full bg-[#0d0d0f] border-[#27272a] text-white p-0 rounded-2xl overflow-hidden">
                          <div className="p-4 border-b border-[#27272a]">
                            <DialogTitle className="text-white font-semibold text-sm">
                              {session.game_name ?? cfg.label} · 9:16 Vertical
                            </DialogTitle>
                          </div>
                          <div className="w-full" style={{ aspectRatio: "9/16" }}>
                            <HlsPlayer src={reel.vertical_stream_url} className="w-full h-full" autoPlay />
                          </div>
                        </DialogContent>
                      </Dialog>
                    ) : processing ? (
                      /* Generating indicator */
                      <span className="flex items-center gap-1.5 text-xs text-gray-500">
                        <Loader2 className="w-3 h-3 animate-spin" /> Reframing to 9:16…
                      </span>
                    ) : (
                      /* Make 9:16 trigger */
                      <button
                        onClick={() => handleMakeVertical(session.id)}
                        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors font-medium"
                      >
                        <Share2 className="w-3 h-3" /> Make 9:16 for Reels
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
