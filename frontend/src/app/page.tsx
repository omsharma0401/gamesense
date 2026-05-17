"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import AllClipsScreen from "@/components/dashboard/AllClipsScreen";
import HighlightsScreen from "@/components/dashboard/HighlightsScreen";
import PerformanceScreen from "@/components/dashboard/PerformanceScreen";
import RecordsScreen from "@/components/dashboard/RecordsScreen";
import { AnimatePresence, motion } from "framer-motion";
import type { GenreKey } from "@/lib/genres";

export default function DashboardLayout() {
  const [activeTab, setActiveTab] = useState("clips");
  const [genre, setGenre] = useState<GenreKey>("arcade-racing");

  return (
    <div className="flex h-screen overflow-hidden bg-[#09090b] text-white p-4 font-sans selection:bg-primary/30 selection:text-primary">
      <div className="w-72 flex-shrink-0 mr-4 h-full">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          genre={genre}
          setGenre={setGenre}
        />
      </div>

      <main className="flex-1 overflow-y-auto bg-[#121214] rounded-[2.5rem] p-10 border border-[#27272a]/50 shadow-2xl relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 15, filter: "blur(5px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -15, filter: "blur(5px)" }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="h-full"
          >
            {activeTab === "clips"       && <AllClipsScreen genre={genre} />}
            {activeTab === "highlights"  && <HighlightsScreen genre={genre} />}
            {activeTab === "performance" && <PerformanceScreen genre={genre} />}
            {activeTab === "records"     && <RecordsScreen genre={genre} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
