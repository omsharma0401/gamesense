import React from "react";
import { HardDrive, PlayCircle, MoreVertical, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function RecordsScreen() {
  const records = [
    { id: 1, title: "Session_20260517_001.mp4", game: "Mortal Kombat Arena", duration: "45:20", date: "Today, 14:30", size: "2.4 GB", status: "Analyzed" },
    { id: 2, title: "Session_20260516_004.mp4", game: "Asphalt 9", duration: "1:12:05", date: "Yesterday, 19:45", size: "3.8 GB", status: "Analyzed" },
    { id: 3, title: "Session_20260515_002.mp4", game: "Mortal Kombat Arena", duration: "22:10", date: "May 15, 2026", size: "1.1 GB", status: "Analyzed" },
    { id: 4, title: "Session_20260514_001.mp4", game: "Asphalt 9", duration: "58:30", date: "May 14, 2026", size: "3.1 GB", status: "Analyzed" },
    { id: 5, title: "Session_20260510_003.mp4", game: "Unknown Game", duration: "15:45", date: "May 10, 2026", size: "850 MB", status: "Pending" },
  ];

  return (
    <div className="w-full space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-2">
        <div>
          <h2 className="text-4xl font-semibold tracking-tight text-white mb-2">
            Raw Recordings
          </h2>
          <div className="flex items-center gap-3 text-sm text-gray-400">
            <span>Storage &gt;</span>
            <span className="text-gray-500">Local captures</span>
          </div>
        </div>

        <div className="flex gap-4">
          <div className="flex items-center gap-3 bg-black border border-[#27272a] rounded-full px-6 py-3 text-sm text-gray-200 shadow-lg">
            <HardDrive className="w-4 h-4 text-primary" />
            <span className="font-semibold text-white">11.25 GB</span> used of 50 GB
          </div>
        </div>
      </div>

      <div className="bg-black border border-[#27272a] rounded-[2rem] overflow-hidden shadow-2xl p-4">
        <div className="overflow-x-auto bg-[#121214] rounded-3xl border border-[#1f1f24]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#27272a] bg-[#1a1a1f] text-gray-400 text-xs uppercase tracking-widest">
                <th className="p-6 font-semibold rounded-tl-3xl">File Name</th>
                <th className="p-6 font-semibold">Game Detected</th>
                <th className="p-6 font-semibold">Duration</th>
                <th className="p-6 font-semibold">Date Recorded</th>
                <th className="p-6 font-semibold">Size</th>
                <th className="p-6 text-right rounded-tr-3xl">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#27272a]">
              {records.map((record) => (
                <tr key={record.id} className="hover:bg-[#1f1f24] transition-colors group">
                  <td className="p-6">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-[#09090b] flex items-center justify-center border border-[#27272a] group-hover:border-primary/50 transition-colors shadow-inner">
                        <PlayCircle className="w-6 h-6 text-gray-400 group-hover:text-primary transition-colors" />
                      </div>
                      <div>
                        <span className="text-gray-200 font-medium block">{record.title}</span>
                        <span className="text-xs text-gray-500 flex items-center gap-2 mt-1">
                          <Badge variant="outline" className={`px-2 py-0 border-transparent text-[10px] ${record.status === 'Analyzed' ? 'bg-primary/10 text-primary' : 'bg-gray-800 text-gray-400'}`}>
                            {record.status}
                          </Badge>
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="p-6 text-gray-400 text-sm font-medium">{record.game}</td>
                  <td className="p-6 text-gray-300 font-mono text-sm">{record.duration}</td>
                  <td className="p-6 text-gray-400 text-sm flex items-center gap-2 h-full py-9">
                    <Calendar className="w-4 h-4 opacity-50 text-gray-500" />
                    {record.date}
                  </td>
                  <td className="p-6 text-gray-400 text-sm font-mono">{record.size}</td>
                  <td className="p-6 text-right">
                    <Button variant="ghost" size="icon" className="text-gray-500 hover:text-white hover:bg-[#27272a] rounded-full">
                      <MoreVertical className="w-5 h-5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
