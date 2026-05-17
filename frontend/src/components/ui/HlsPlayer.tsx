"use client";
import { useEffect, useRef, useState } from "react";

interface Props {
  src: string;
  className?: string;
  autoPlay?: boolean;
}

export default function HlsPlayer({ src, className, autoPlay = false }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !src) return;

    setError(false);
    let cancelled = false;
    let hls: any;

    const tryHls = async () => {
      const { default: Hls } = await import("hls.js").catch(() => ({ default: null as any }));
      if (cancelled) return;

      if (!Hls || !Hls.isSupported()) {
        // MSE not supported — try native src (works for Safari HLS and regular video)
        video.src = src;
        if (autoPlay) video.play().catch(() => {});
        return;
      }

      hls = new Hls({
        enableWorker: false,
        // Start at lowest quality for faster initial load in a modal
        startLevel: -1,
      });

      hls.on(Hls.Events.ERROR, (_: unknown, data: any) => {
        if (data.fatal && !cancelled) {
          // Fatal HLS error — fall back to native src
          hls.destroy();
          hls = null;
          video.src = src;
          video.load();
          if (autoPlay) video.play().catch(() => {});
        }
      });

      hls.loadSource(src);
      hls.attachMedia(video);

      if (autoPlay) {
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          if (!cancelled) video.play().catch(() => {});
        });
      }
    };

    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari — native HLS
      video.src = src;
      if (autoPlay) video.play().catch(() => {});
    } else {
      tryHls().catch(() => {
        if (!cancelled) setError(true);
      });
    }

    const onNativeError = () => {
      if (!cancelled && !hls) setError(true);
    };
    video.addEventListener("error", onNativeError);

    return () => {
      cancelled = true;
      video.removeEventListener("error", onNativeError);
      hls?.destroy();
    };
  }, [src, autoPlay]);

  if (error) {
    return (
      <div className={`${className ?? ""} flex flex-col items-center justify-center bg-black gap-2`}>
        <span className="text-gray-500 text-sm">Unable to load stream</span>
        <a href={src} target="_blank" rel="noopener noreferrer"
          className="text-xs text-primary underline opacity-60 hover:opacity-100">
          Open in browser ↗
        </a>
      </div>
    );
  }

  return (
    <video
      ref={videoRef}
      className={className}
      controls
      playsInline
    />
  );
}
