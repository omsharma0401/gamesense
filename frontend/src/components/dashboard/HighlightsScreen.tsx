"use client";
import React, { useEffect, useState } from "react";
import { Play, Sparkles, ArrowUpRight, Film } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { api, type HighlightReel, type SessionSummary } from "@/lib/api";
import { GENRE_CONFIG, type GenreKey } from "@/lib/genres";

interface Props { genre: GenreKey }

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

export default function HighlightsScreen({ genre }: Props) {
  const [items, setItems] = useState<ReelWithSession[]>([]);
  const [loading, setLoading] = useState(true);

  const cfg = GENRE_CONFIG[genre];

  useEffect(() => {
    setLoading(true);
    async function load() {
      const history = await api.getHistory(undefined, 20);
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
  }, [genre]);

  const formatDur = (sec: number | null) => {
    if (!sec) return "—";
    return `${Math.floor(sec / 60)}:${Math.floor(sec % 60).toString().padStart(2, "0")}`;
  };

  return (
    <div className="w-full space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">

      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">Highlight Reels</h2>
          <p className="text-sm text-gray-400">{cfg.label} · {items.length} reel{items.length !== 1 ? "s" : ""}</p>
        </div>
      </div>

      {/* Hero CTA */}
      <div className="bg-black border border-[#27272a] rounded-[2.5rem] p-1 relative overflow-hidden group shadow-2xl">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent opacity-50" />
        <div className="bg-[#121214] rounded-[2.3rem] p-10 flex flex-col md:flex-row items-center justify-between relative z-10">
          <div className="mb-6 md:mb-0">
            <div className="flex items-center gap-2 text-primary font-bold tracking-widest text-xs uppercase mb-3">
              <Sparkles className="w-4 h-4" /> AI Powered
            </div>
            <h3 className="text-3xl font-bold text-white mb-2">Build New Highlight Reel</h3>
            <p className="text-gray-400 max-w-md leading-relaxed">
              Let the agent scan your latest {cfg.label} session and compile the most impactful moments automatically.
            </p>
          </div>
          <Button className="h-14 rounded-full px-8 bg-primary hover:bg-primary/90 text-black font-bold shadow-[0_0_30px_rgba(204,255,0,0.25)] text-base group-hover:scale-105 transition-transform">
            Start Generation <ArrowUpRight className="w-5 h-5 ml-2" />
          </Button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-gray-500 text-sm py-16 text-center">Loading reels…</div>
      )}

      {/* Empty state */}
      {!loading && items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <Film className="w-12 h-12 text-gray-700" />
          <h3 className="text-white font-semibold text-lg">No highlight reels yet</h3>
          <p className="text-gray-500 text-sm max-w-xs">
            Complete a {cfg.label} session — the AI will compile your best moments automatically.
          </p>
        </div>
      )}

      {/* Reels grid */}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {items.map(({ reel, session }, i) => (
            <Dialog key={reel.id}>
              <div className="group cursor-pointer">
                <DialogTrigger asChild>
                  <div className={`aspect-[4/3] rounded-[2rem] bg-gradient-to-br ${GRADIENTS[i % GRADIENTS.length]} border border-[#27272a] group-hover:border-primary/50 transition-all relative flex items-center justify-center overflow-hidden mb-5 shadow-lg`}>
                    {reel.stream_url ? (
                      <iframe
                        src={reel.stream_url}
                        className="absolute inset-0 w-full h-full z-0 border-none pointer-events-none"
                        allow="autoplay; fullscreen"
                      />
                    ) : (
                      <div className="absolute inset-0 bg-black/40 group-hover:bg-black/10 transition-colors duration-500" />
                    )}
                    <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center shadow-[0_0_30px_rgba(0,0,0,0.5)] transform group-hover:scale-110 transition-transform duration-500 z-10 border border-white/20">
                      <Play className="w-7 h-7 text-white ml-1" />
                    </div>
                    <div className="absolute bottom-4 right-4 bg-black/80 backdrop-blur px-3 py-1.5 rounded-full text-xs font-mono text-white z-10 border border-white/10">
                      {reel.status === "generating" ? "Generating…" : formatDur(reel.duration)}
                    </div>
                  </div>
                </DialogTrigger>

                <h3 className="text-white font-semibold text-lg group-hover:text-primary transition-colors px-2">
                  {cfg.label} · Highlight
                </h3>
                <p className="text-gray-500 text-sm mt-1 px-2">
                  {new Date(reel.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
                </p>
              </div>

              <DialogContent className="max-w-3xl w-full bg-[#141523] border-[#202136] text-white p-0 rounded-2xl overflow-hidden">
                <div className="p-5 border-b border-[#202136]">
                  <DialogTitle className="text-white font-semibold">{cfg.label} Highlight Reel</DialogTitle>
                </div>
                <div className="aspect-video w-full bg-black">
                  {reel.stream_url
                    ? <iframe src={reel.stream_url} className="w-full h-full border-none" allow="autoplay; fullscreen" allowFullScreen />
                    : <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                        {reel.status === "generating" ? "Generating reel — check back shortly." : "Stream URL not available."}
                      </div>
                  }
                </div>
              </DialogContent>
            </Dialog>
          ))}
        </div>
      )}
    </div>
  );
}
