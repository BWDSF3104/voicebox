import { Square, Volume2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';
import { useGenerationSettings } from '@/lib/hooks/useSettings';
import { useGenerationStore } from '@/stores/generationStore';

/**
 * Listen to a long-text generation while it is still running by queueing the
 * per-chunk spool files (/audio/{id}/chunk/{i}) in order, then the final audio.
 * The main-player autoplay is suppressed while this is active (see
 * useGenerationProgress + livePlaybackIds) so the audio never doubles.
 *
 * When the user's "autoplay on generate" setting is on, playback starts
 * automatically as soon as the first chunk is spooled — the same experience a
 * finished single-chunk generation gets, applied to each chunk as it lands.
 */
interface LiveListenButtonProps {
  generationId: string;
  total: number;
  completed: number;
  generating: boolean;
}

export function LiveListenButton({
  generationId,
  total,
  completed,
  generating,
}: LiveListenButtonProps) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const retriesRef = useRef(0);
  const generatingRef = useRef(generating);
  const totalRef = useRef(total);
  const autoStartedRef = useRef(false);
  const addLivePlayback = useGenerationStore((s) => s.addLivePlayback);
  const removeLivePlayback = useGenerationStore((s) => s.removeLivePlayback);
  const autoplay = useGenerationSettings().settings?.autoplay_on_generate ?? true;

  generatingRef.current = generating;
  totalRef.current = total;

  const stop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    retriesRef.current = 0;
    setPlaying(false);
    removeLivePlayback(generationId);
  };

  useEffect(
    () => () => {
      audioRef.current?.pause();
      removeLivePlayback(generationId);
    },
    [generationId, removeLivePlayback],
  );

  const playFinal = () => {
    const audio = new Audio(apiClient.getAudioUrl(generationId));
    audio.onended = () => stop();
    audio.onerror = () => stop();
    audioRef.current = audio;
    audio.play().catch(() => stop());
  };

  const playChunk = (index: number) => {
    // Queue exhausted and generation finished → switch to the final file.
    if (index >= totalRef.current && !generatingRef.current) {
      playFinal();
      return;
    }
    const audio = new Audio(apiClient.getGenerationChunkUrl(generationId, index));
    audio.onended = () => {
      retriesRef.current = 0;
      playChunk(index + 1);
    };
    audio.onerror = () => {
      if (!generatingRef.current) {
        // Spool missing but done — the final audio is authoritative.
        playFinal();
        return;
      }
      if (++retriesRef.current > 6) {
        // Spool not appearing (effects profile, old backend) — give up quietly.
        stop();
        return;
      }
      setTimeout(() => playChunk(index), 2500);
    };
    audioRef.current = audio;
    audio.play().catch(() => stop());
  };

  const start = () => {
    addLivePlayback(generationId);
    retriesRef.current = 0;
    setPlaying(true);
    playChunk(0);
  };

  // Autoplay: start as soon as the first chunk is spooled, once.
  useEffect(() => {
    if (autoplay && !autoStartedRef.current && total > 1 && completed >= 1) {
      autoStartedRef.current = true;
      start();
    }
  }, [autoplay, total, completed]);

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-8 w-8"
      title={
        playing
          ? 'Stop listening to the in-progress generation'
          : 'Listen from the start while it generates'
      }
      onClick={(e) => {
        e.stopPropagation();
        if (playing) stop();
        else start();
      }}
    >
      {playing ? <Square className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
    </Button>
  );
}
