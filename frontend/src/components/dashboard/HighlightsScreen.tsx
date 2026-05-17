import React from "react";
import { Play, Sparkles, Share2, Download, ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
export default function HighlightsScreen() {
  const [highlights, setHighlights] = React.useState<any[]>([]);

  React.useEffect(() => {
    async function loadHighlights() {
      const history = await api.getHistory();
      const recent = history.slice(0, 4); // get up to 4
      
      const reelsData = await Promise.all(
        recent.map(s => api.getHighlightReel(s.id))
      );
      
      const mapped = reelsData
        .map((r, i) => {
          if (!r) return null;
          const s = recent[i];
          const dur = r.duration || 0;
          const mins = Math.floor(dur / 60);
          const secs = Math.floor(dur % 60);
          const gradients = ["from-[#a855f7]/40 to-black", "from-primary/30 to-black", "from-red-500/30 to-black", "from-blue-500/30 to-black"];
          return {
            id: r.id,
            title: `${s.game} • Highlight`,
            time: new Date(r.created_at).toLocaleDateString(),
            duration: `${mins}:${secs.toString().padStart(2, '0')}`,
            gradient: gradients[i % gradients.length],
            stream_url: r.stream_url
          };
        })
        .filter(Boolean);
        
      setHighlights(mapped as any[]);
    }
    loadHighlights();
  }, []);

  return (
    <div className="w-full space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">
            Highlight Reels
          </h2>
          <div className="flex items-center gap-3 text-sm text-gray-400">
            <span>Editor &gt;</span>
            <span className="text-gray-500">Generated Collections</span>
          </div>
        </div>

        <div className="flex gap-4">
          <Button variant="outline" className="h-12 rounded-full px-6 bg-black border-[#27272a] text-white hover:bg-[#1a1a1f] focus:ring-0 shadow-lg">
            <Download className="w-4 h-4 mr-2" /> Export Raw
          </Button>
          <Button variant="outline" className="h-12 rounded-full px-6 bg-black border-[#27272a] text-white hover:bg-[#1a1a1f] focus:ring-0 shadow-lg">
            <Share2 className="w-4 h-4 mr-2" /> Share
          </Button>
        </div>
      </div>

      {/* Big Hero CTA */}
      <div className="bg-black border border-[#27272a] rounded-[2.5rem] p-1 relative overflow-hidden group shadow-2xl">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent opacity-50" />
        <div className="bg-[#121214] rounded-[2.3rem] p-10 flex flex-col md:flex-row items-center justify-between relative z-10">
          <div className="mb-6 md:mb-0">
            <div className="flex items-center gap-2 text-primary font-bold tracking-widest text-xs uppercase mb-3">
              <Sparkles className="w-4 h-4" /> AI Powered
            </div>
            <h3 className="text-3xl font-bold text-white mb-2">Build New Highlight Reel</h3>
            <p className="text-gray-400 max-w-md leading-relaxed">Let the agent scan your latest session and compile the most impactful moments automatically.</p>
          </div>
          
          <Button className="h-14 rounded-full px-8 bg-primary hover:bg-primary/90 text-black font-bold shadow-[0_0_30px_rgba(204,255,0,0.25)] text-base group-hover:scale-105 transition-transform">
            Start Generation <ArrowUpRight className="w-5 h-5 ml-2" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {highlights.map((reel) => (
          <div key={reel.id} className="group cursor-pointer">
            <div className={`aspect-[4/3] rounded-[2rem] bg-gradient-to-br ${reel.gradient} border border-[#27272a] group-hover:border-primary/50 transition-all relative flex items-center justify-center overflow-hidden mb-5 shadow-lg`}>
              {reel.stream_url ? (
                <iframe src={reel.stream_url} className="absolute inset-0 w-full h-full z-0 border-none pointer-events-none" allow="autoplay; fullscreen" />
              ) : (
                <div className="absolute inset-0 bg-black/40 group-hover:bg-black/10 transition-colors duration-500" />
              )}
              
              <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center shadow-[0_0_30px_rgba(0,0,0,0.5)] transform group-hover:scale-110 transition-transform duration-500 z-10 border border-white/20">
                <Play className="w-7 h-7 text-white ml-1" />
              </div>
              
              <div className="absolute bottom-4 right-4 bg-black/80 backdrop-blur px-3 py-1.5 rounded-full text-xs font-mono text-white z-10 border border-white/10">
                {reel.duration}
              </div>
            </div>
            
            <h3 className="text-white font-semibold text-lg group-hover:text-primary transition-colors px-2">{reel.title}</h3>
            <p className="text-gray-500 text-sm mt-1 px-2">{reel.time}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
