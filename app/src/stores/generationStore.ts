import { create } from 'zustand';

export interface GenerationProgress {
  completed: number;
  total: number;
  /** epoch ms when the generation became pending; for client-side ETA */
  startedAt: number;
}

interface GenerationState {
  /** IDs of generations currently in progress */
  pendingGenerationIds: Set<string>;
  /** Whether any generation is in progress (derived from pendingGenerationIds) */
  isGenerating: boolean;
  /** Chunk progress (long text) for in-flight generations; cleared on finish */
  generationProgress: Record<string, GenerationProgress>;
  /** Generations whose incremental (chunk) playback is active; suppresses completion autoplay */
  livePlaybackIds: Set<string>;
  /** When each live playback stopped — completion autoplay stays suppressed for a grace
   *  window after stop, otherwise the final audio doubles-up while chunk playback races */
  livePlaybackEndedAt: Map<string, number>;
  /** Map of generationId → storyId for deferred story additions */
  pendingStoryAdds: Map<string, string>;
  addPendingGeneration: (id: string) => void;
  removePendingGeneration: (id: string) => void;
  setGenerationProgress: (id: string, completed: number, total: number) => void;
  clearGenerationProgress: (id: string) => void;
  addLivePlayback: (id: string) => void;
  removeLivePlayback: (id: string) => void;
  addPendingStoryAdd: (generationId: string, storyId: string) => void;
  removePendingStoryAdd: (generationId: string) => string | undefined;
  setActiveGenerationId: (id: string | null) => void;
  activeGenerationId: string | null;
}

export const useGenerationStore = create<GenerationState>((set, get) => ({
  pendingGenerationIds: new Set(),
  isGenerating: false,
  activeGenerationId: null,
  generationProgress: {},
  livePlaybackIds: new Set(),
  livePlaybackEndedAt: new Map(),
  pendingStoryAdds: new Map(),

  addPendingGeneration: (id) =>
    set((state) => {
      const next = new Set(state.pendingGenerationIds);
      next.add(id);
      const progress =
        id in state.generationProgress
          ? state.generationProgress
          : {
              ...state.generationProgress,
              [id]: { completed: 0, total: 0, startedAt: Date.now() },
            };
      return { pendingGenerationIds: next, isGenerating: true, generationProgress: progress };
    }),

  removePendingGeneration: (id) =>
    set((state) => {
      const next = new Set(state.pendingGenerationIds);
      next.delete(id);
      const { [id]: _removed, ...progress } = state.generationProgress;
      return {
        pendingGenerationIds: next,
        isGenerating: next.size > 0,
        generationProgress: progress,
      };
    }),

  setGenerationProgress: (id, completed, total) =>
    set((state) => ({
      generationProgress: {
        ...state.generationProgress,
        [id]: {
          completed,
          total,
          startedAt: state.generationProgress[id]?.startedAt ?? Date.now(),
        },
      },
    })),

  clearGenerationProgress: (id) =>
    set((state) => {
      if (!(id in state.generationProgress)) return state;
      const { [id]: _removed, ...progress } = state.generationProgress;
      return { generationProgress: progress };
    }),

  addLivePlayback: (id) =>
    set((state) => {
      const next = new Set(state.livePlaybackIds);
      next.add(id);
      return { livePlaybackIds: next };
    }),

  removeLivePlayback: (id) =>
    set((state) => {
      if (!state.livePlaybackIds.has(id)) return state;
      const next = new Set(state.livePlaybackIds);
      next.delete(id);
      const ended = new Map(state.livePlaybackEndedAt);
      ended.set(id, Date.now());
      return { livePlaybackIds: next, livePlaybackEndedAt: ended };
    }),

  addPendingStoryAdd: (generationId, storyId) =>
    set((state) => {
      const next = new Map(state.pendingStoryAdds);
      next.set(generationId, storyId);
      return { pendingStoryAdds: next };
    }),

  removePendingStoryAdd: (generationId) => {
    const storyId = get().pendingStoryAdds.get(generationId);
    if (storyId) {
      set((state) => {
        const next = new Map(state.pendingStoryAdds);
        next.delete(generationId);
        return { pendingStoryAdds: next };
      });
    }
    return storyId;
  },

  setActiveGenerationId: (id) => set({ activeGenerationId: id }),
}));
