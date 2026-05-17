import React, { useState } from "react";
import { Play, UploadCloud, MonitorPlay, Filter, Youtube, X } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

const CLIPS_DATA = {
  "asphalt-9": [
    { id: 1, title: "Perfect Nitro Timing", duration: "1:24", skillPts: 18, tag: "TOP PLAY", tagColor: "text-primary border-primary/30", time: "04:36 - 0:22", desc: "Held draft until the very last second before full nitro." },
    { id: 2, title: "Missed the Ramp", duration: "0:14", skillPts: -14, tag: "BLUNDER", tagColor: "text-destructive border-destructive/30", time: "07:51 - 0:14", desc: "Took the wrong route and crashed." },
    { id: 3, title: "Clutch Finish", duration: "0:18", skillPts: 12, tag: "CLUTCH", tagColor: "text-white border-white/20", time: "02:14 - 0:18", desc: "Overtook in the last millisecond." },
    { id: 8, title: "Missed Nitro Bottle", duration: "0:06", skillPts: -5, tag: "MISSED", tagColor: "text-yellow-400 border-yellow-500/30", time: "05:12 - 0:06", desc: "Just barely missed the double nitro bottle on the ramp." },
  ],
  "mortal-kombat": [
    { id: 5, title: "Flawless Block Punish", duration: "0:12", skillPts: 20, tag: "TOP PLAY", tagColor: "text-primary border-primary/30", time: "01:10 - 0:12", desc: "Blocked the fatal blow and punished." },
    { id: 6, title: "Dropped Combo", duration: "0:08", skillPts: -10, tag: "MISSED", tagColor: "text-yellow-400 border-yellow-500/30", time: "02:45 - 0:08", desc: "Dropped the optimal corner combo." },
    { id: 7, title: "Corner Trap Setup", duration: "0:20", skillPts: 15, tag: "TEACHING", tagColor: "text-orange-400 border-orange-500/30", time: "03:15 - 0:20", desc: "Good frame trap in the corner." },
  ]
};

export default function AllClipsScreen() {
  const [game, setGame] = useState("asphalt-9");
  const [clips, setClips] = React.useState<any[]>([]);

  React.useEffect(() => {
    async function loadClips() {
      const history = await api.getHistory();
      const gameHistory = history.filter(h => h.game.toLowerCase().includes(game.replace("-", " ")));
      if (gameHistory.length > 0) {
        const latestSessionId = gameHistory[gameHistory.length - 1].id;
        const bClips = await api.getClips(latestSessionId);
        
        const mapped = bClips.map((c) => {
          const dur = Math.max(0, c.end_time - c.start_time);
          const mins = Math.floor(dur / 60);
          const secs = Math.floor(dur % 60);
          
          let skillPts = 10;
          let tagColor = "text-primary border-primary/30";
          if (c.type === "blunder" || c.type === "error" || c.type === "death") {
             skillPts = -10;
             tagColor = "text-destructive border-destructive/30";
          } else if (c.type === "clutch") {
             skillPts = 20;
             tagColor = "text-white border-white/20";
          }
          
          return {
            id: c.id,
            title: `Moment: ${c.type.toUpperCase()}`,
            duration: `${mins}:${secs.toString().padStart(2, '0')}`,
            skillPts,
            tag: c.type.toUpperCase(),
            tagColor,
            time: `00:${Math.floor(c.start_time).toString().padStart(2, '0')} - ${dur.toFixed(0)}s`,
            desc: c.commentary || "Detected by GameSense AI",
            stream_url: c.stream_url
          };
        });
        setClips(mapped);
      } else {
        setClips([]);
      }
    }
    loadClips();
  }, [game]);

  return (
    <div className="w-full space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Top Bar */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">
            All Clips
          </h2>
          <div className="flex items-center gap-3 text-sm text-gray-400 font-medium">
            <span className="hover:text-white cursor-pointer transition-colors">Editor</span> 
            <span>&gt;</span>
            <span className="text-gray-500">Auto-detected moments</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Select value={game} onValueChange={setGame}>
            <SelectTrigger className="w-[200px] h-10 bg-[#121214] border border-[#27272a] rounded-full text-white px-5 focus:ring-0">
              <SelectValue placeholder="Select Game" />
            </SelectTrigger>
            <SelectContent className="bg-[#121214] border-[#27272a] text-white rounded-xl">
              <SelectItem value="asphalt-9">Asphalt 9</SelectItem>
              <SelectItem value="mortal-kombat">Mortal Kombat Arena</SelectItem>
            </SelectContent>
          </Select>
          
          <Button variant="outline" className="h-10 rounded-full px-6 bg-[#121214] border border-[#27272a] text-white">
            <Filter className="w-4 h-4 mr-2" />
            Filter
          </Button>

          <Button className="h-10 rounded-full px-6 bg-primary hover:bg-primary/90 text-black font-bold">
            <UploadCloud className="w-4 h-4 mr-2" />
            Build Highlight Reel
          </Button>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap mb-2">
        <Badge className="bg-black text-white border-transparent rounded-full px-4 py-1.5 text-sm">all moments <span className="ml-2 text-gray-500">{clips.length}</span></Badge>
        <Badge variant="outline" className="bg-[#1a1a1f] text-primary border-transparent rounded-full px-4 py-1.5 text-sm">• top play</Badge>
        <Badge variant="outline" className="bg-[#1a1a1f] text-white border-transparent rounded-full px-4 py-1.5 text-sm">• clutch</Badge>
        <Badge variant="outline" className="bg-[#1a1a1f] text-destructive border-transparent rounded-full px-4 py-1.5 text-sm">• blunder</Badge>
        <Badge variant="outline" className="bg-[#1a1a1f] text-yellow-500 border-transparent rounded-full px-4 py-1.5 text-sm">• missed</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {clips.map((clip) => (
          <div key={clip.id} className="bg-[#0f1015] rounded-[1.5rem] p-4 group border border-[#1f2029]">
            <div className="aspect-video bg-[#1a1b26] rounded-[1rem] relative flex items-center justify-center cursor-pointer overflow-hidden mb-4 border border-[#2a2b36]">
              <div className="absolute top-4 left-4">
                <Badge variant="outline" className={`${clip.tagColor} border px-2 py-0.5 text-[10px] font-bold tracking-widest rounded-md bg-black/40`}>
                  {clip.tag}
                </Badge>
              </div>
              <div className="absolute bottom-4 right-4 text-xs font-mono bg-black/60 px-2 py-1 rounded-md text-white">
                {clip.time}
              </div>
              
              <Dialog>
                <DialogTrigger asChild>
                  <Button className="absolute top-4 right-4 bg-primary text-black text-xs font-bold h-8 rounded-full px-4 opacity-0 group-hover:opacity-100 transition-all z-10">
                    <MonitorPlay className="w-3 h-3 mr-1.5" />
                    Upload
                  </Button>
                </DialogTrigger>
                
                {/* Fixed the max-w by explicitly overriding Tailwind's sm breakpoint which causes the phone-like box */}
                <DialogContent className="max-w-[1000px] w-[1000px] sm:max-w-[1000px] md:max-w-[1000px] lg:max-w-[1000px] bg-[#141523] border-[#202136] text-white p-0 rounded-[1rem] overflow-hidden shadow-2xl flex flex-col h-[700px]">
                  {/* Header */}
                  <div className="flex items-center justify-between p-6 pb-4 border-b border-[#202136]">
                    <div className="flex items-center gap-4">
                      <div className="w-8 h-8 rounded-md bg-red-500 flex items-center justify-center text-white">
                        <MonitorPlay className="w-5 h-5" />
                      </div>
                      <DialogTitle className="text-xl font-semibold text-white">Upload to YouTube</DialogTitle>
                      <span className="text-xs text-gray-400 font-mono tracking-wide ml-4 pt-1">Highlight Reel • 1m 24s</span>
                    </div>
                  </div>

                  {/* Body */}
                  <div className="flex-1 flex overflow-hidden">
                    {/* Left Column */}
                    <div className="w-[400px] shrink-0 p-6 pr-4 flex flex-col gap-6 overflow-y-auto">
                      {/* Video Preview */}
                      <div className="aspect-[16/10] bg-[#0c0d16] rounded-xl border border-[#202136] p-0 flex flex-col justify-end relative overflow-hidden group/preview">
                         {clip.stream_url ? (
                           <iframe src={clip.stream_url} className="w-full h-full border-none" allow="autoplay; fullscreen" />
                         ) : (
                           <div className="absolute inset-0 flex items-center justify-center text-gray-500">No Stream URL</div>
                         )}
                         <div className="absolute top-3 left-3 bg-red-500/10 text-red-400 text-[10px] font-bold px-2 py-1 rounded flex items-center gap-1.5 pointer-events-none">
                           <div className="w-2 h-2 bg-red-500 rounded-sm"></div>
                           1080p • 16:9
                         </div>
                         <div className="absolute bottom-4 left-4 pointer-events-none">
                           <h4 className="text-xl font-bold text-white mb-1 leading-tight drop-shadow-md">{clip.title}</h4>
                           <p className="text-xs text-gray-300 font-mono drop-shadow-md">{clip.duration} • Highlight reel</p>
                         </div>
                      </div>

                      {/* AI Suggestions */}
                      <div>
                        <h5 className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-4">AI SUGGESTIONS</h5>
                        <div className="space-y-4">
                          <div className="flex items-start gap-3">
                            <span className="text-[#9d72ff] text-[10px] mt-1">♦</span>
                            <div>
                              <p className="font-semibold text-gray-200 text-sm mb-0.5">Best posting time: today, 18:30 PT</p>
                              <p className="text-[11px] text-gray-500 font-mono">Your subs are most active in next 4h</p>
                            </div>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="text-[#9d72ff] text-[10px] mt-1">♦</span>
                            <div>
                              <p className="font-semibold text-gray-200 text-sm mb-0.5">Title hook score: 82/100</p>
                              <p className="text-[11px] text-gray-500 font-mono">Number + outcome in first 3 words is strong</p>
                            </div>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="text-[#9d72ff] text-[10px] mt-1">♦</span>
                            <div>
                              <p className="font-semibold text-gray-200 text-sm mb-0.5">Thumbnail: use frame at 0:36</p>
                              <p className="text-[11px] text-gray-500 font-mono">Highest face-detection contrast</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Right Column */}
                    <div className="flex-1 p-6 pl-4 flex flex-col gap-5 overflow-y-auto custom-scrollbar">
                      {/* Title */}
                      <div>
                        <label className="text-[10px] text-gray-500 font-mono uppercase tracking-widest block mb-2">TITLE</label>
                        <Input 
                          defaultValue={`${clip.title} • ${game === 'asphalt-9' ? 'Asphalt 9 Highlights' : 'MK Arena Moments'}`} 
                          className="bg-[#1c1d2e] border-none text-gray-200 h-11 rounded-lg px-4 text-sm focus-visible:ring-1 focus-visible:ring-[#9d72ff]" 
                        />
                        <div className="text-right mt-1.5">
                          <span className="text-[10px] text-gray-500 font-mono">63/100</span>
                        </div>
                      </div>

                      {/* Description */}
                      <div>
                        <label className="text-[10px] text-gray-500 font-mono uppercase tracking-widest block mb-2">DESCRIPTION</label>
                        <Textarea 
                          defaultValue={`Full highlight reel from Match #047 on Bastion — 6 moments cut by AI.\n\n00:00 Cold open • 1v2 retake on B-Site\n00:12 3-tap thru smoke\n00:24 Solo push mid (oof)\n00:42 Wallbang molly + 2\n00:58 Spray transfer down hallway`} 
                          className="bg-[#1c1d2e] border-none text-gray-200 min-h-[160px] rounded-lg p-4 text-sm focus-visible:ring-1 focus-visible:ring-[#9d72ff] resize-none leading-relaxed" 
                        />
                      </div>

                      {/* Tags */}
                      <div>
                        <label className="text-[10px] text-gray-500 font-mono uppercase tracking-widest block mb-2">TAGS</label>
                        <div className="bg-[#1c1d2e] rounded-lg p-3 min-h-[90px] flex flex-wrap gap-2">
                          {["echo-protocol", "fps", "ranked", "clutch", "bastion", "gamesense", "highlights", "tactical-shooter"].map(t => (
                            <Badge key={t} className="bg-[#2a2b42] hover:bg-[#343552] text-[#9d72ff] border-none rounded-md px-3 py-1.5 text-xs font-medium cursor-pointer flex items-center gap-1.5">
                              #{t} <span className="text-gray-400 hover:text-white font-bold ml-1">×</span>
                            </Badge>
                          ))}
                        </div>
                      </div>

                      {/* Vis / Cat */}
                      <div className="grid grid-cols-2 gap-6">
                        <div>
                          <label className="text-[10px] text-gray-500 font-mono uppercase tracking-widest block mb-2">VISIBILITY</label>
                          <Select defaultValue="public">
                            <SelectTrigger className="bg-[#1c1d2e] border-none h-11 rounded-lg px-4 text-sm text-gray-200 focus:ring-[#9d72ff]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#1c1d2e] border-[#2a2b42] text-gray-200 rounded-lg">
                              <SelectItem value="public">Public</SelectItem>
                              <SelectItem value="unlisted">Unlisted</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <label className="text-[10px] text-gray-500 font-mono uppercase tracking-widest block mb-2">CATEGORY</label>
                          <Select defaultValue="gaming">
                            <SelectTrigger className="bg-[#1c1d2e] border-none h-11 rounded-lg px-4 text-sm text-gray-200 focus:ring-[#9d72ff]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-[#1c1d2e] border-[#2a2b42] text-gray-200 rounded-lg">
                              <SelectItem value="gaming">Gaming</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between p-5 px-6 border-t border-[#202136]">
                    <div className="text-[11px] text-gray-500 font-mono">
                      Connected as <span className="text-gray-300 font-semibold">@kp-gameplay</span> • 1,284 subs
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <Button variant="ghost" className="h-10 rounded-md px-4 text-gray-400 hover:text-white hover:bg-[#202136] text-sm">Cancel</Button>
                      <Button variant="ghost" className="h-10 rounded-md px-4 text-gray-300 hover:text-white hover:bg-[#202136] text-sm">Save as draft</Button>
                      <Button className="h-10 rounded-md px-6 bg-[#8a5df5] hover:bg-[#9d72ff] text-white text-sm font-semibold flex items-center gap-2 shadow-lg">
                        <MonitorPlay className="w-4 h-4" />
                        Publish
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
            
            <div className="px-2 pb-2">
              <h3 className="text-white font-bold text-lg mb-1">{clip.title}</h3>
              <p className="text-gray-400 text-sm mb-4 line-clamp-1">{clip.desc}</p>
              <div className="flex justify-between items-center text-xs">
                <span className={`font-bold ${clip.skillPts > 0 ? 'text-primary' : 'text-destructive'}`}>
                  {clip.skillPts > 0 ? '▲' : '▼'} {Math.abs(clip.skillPts)} skill pts
                </span>
                <span className="text-gray-600 font-mono">ID {clip.id.toString().padStart(4, '0')}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
