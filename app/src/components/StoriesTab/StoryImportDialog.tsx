import { Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api/client';
import { useProfiles } from '@/lib/hooks/useProfiles';
import { useCreateStory, useReorderStoryItems } from '@/lib/hooks/useStories';
import { useStoryStore } from '@/stores/storyStore';

type Granularity = 'paragraph' | 'chapter' | 'chars';

export function StoryImportDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const { data: profiles } = useProfiles();
  const createStory = useCreateStory();
  const reorder = useReorderStoryItems();
  const setSelectedStoryId = useStoryStore((s) => s.setSelectedStoryId);

  const [storyName, setStoryName] = useState('');
  const [text, setText] = useState('');
  const [granularity, setGranularity] = useState<Granularity>('paragraph');
  const [segments, setSegments] = useState<string[] | null>(null);
  const [rowProfiles, setRowProfiles] = useState<Record<number, string>>({});
  const [splitting, setSplitting] = useState(false);
  const [importing, setImporting] = useState(false);
  // progress phase
  const [progressStoryId, setProgressStoryId] = useState<string | null>(null);
  const [progress, setProgress] = useState({ total: 0, done: 0, failed: 0 });
  const orderedGenIds = useRef<string[]>([]);
  const reorderedRef = useRef(false);

  const defaultProfileId = profiles?.[0]?.id ?? '';

  const reset = () => {
    setStoryName('');
    setText('');
    setGranularity('paragraph');
    setSegments(null);
    setRowProfiles({});
    setImporting(false);
    setProgressStoryId(null);
    setProgress({ total: 0, done: 0, failed: 0 });
    orderedGenIds.current = [];
    reorderedRef.current = false;
  };

  const handlePreviewSplit = async () => {
    if (!text.trim()) return;
    setSplitting(true);
    try {
      const segs = await apiClient.previewStorySplit({ text, granularity });
      setSegments(segs);
      setRowProfiles(Object.fromEntries(segs.map((_, i) => [i, defaultProfileId])));
    } catch (e) {
      toast({
        title: t('stories.import.toast.splitFailed'),
        description: (e as Error).message,
        variant: 'destructive',
      });
    } finally {
      setSplitting(false);
    }
  };

  const handleStart = () => {
    if (!segments || !segments.length || !storyName.trim()) return;
    const profileFor = (i: number) => rowProfiles[i] || defaultProfileId;
    if (segments.some((_, i) => !profileFor(i))) {
      toast({ title: t('stories.import.toast.noProfile'), variant: 'destructive' });
      return;
    }
    setImporting(true);
    createStory.mutate(
      { name: storyName.trim() },
      {
        onSuccess: async (story) => {
          try {
            const items = await apiClient.importStorySegments(
              story.id,
              segments.map((seg, i) => ({
                profile_id: profileFor(i),
                text: seg,
                language: 'ja' as const,
              })),
            );
            orderedGenIds.current = items.map((it) => it.generation_id);
            reorderedRef.current = false;
            setProgress({ total: items.length, done: 0, failed: 0 });
            setProgressStoryId(story.id);
            // Server-side fan-out is done; generation continues in the
            // backend queue, so the dialog can be closed during progress.
            setImporting(false);
          } catch (e) {
            setImporting(false);
            toast({
              title: t('stories.import.toast.importFailed'),
              description: (e as Error).message,
              variant: 'destructive',
            });
          }
        },
        onError: (error) => {
          setImporting(false);
          toast({
            title: t('stories.import.toast.importFailed'),
            description: error.message,
            variant: 'destructive',
          });
        },
      },
    );
  };

  // Poll the story while its imported segments are generating; when all are
  // settled, re-time items in import order (reorder recalculates timecodes).
  // biome-ignore lint/correctness/useExhaustiveDependencies: polling effect is keyed on story id; callbacks are stable-enough
  useEffect(() => {
    if (!progressStoryId) return;
    let stopped = false;
    const tick = async () => {
      try {
        const story = await apiClient.getStory(progressStoryId);
        const total = story.items.length;
        const done = story.items.filter((i) => i.generation_status === 'completed').length;
        const failed = story.items.filter((i) => i.generation_status === 'error').length;
        if (stopped) return;
        setProgress({ total, done, failed });
        if (total > 0 && done + failed >= total) {
          stopped = true;
          if (!reorderedRef.current && storyName.trim()) {
            reorderedRef.current = true;
            try {
              reorder.mutate({
                storyId: progressStoryId,
                data: { generation_ids: orderedGenIds.current },
              });
            } catch {
              // retime is cosmetic here; user can retime in the editor
            }
          }
          setImporting(false);
          setSelectedStoryId(progressStoryId);
          toast({
            title: t('stories.import.toast.importDone'),
            description: failed
              ? t('stories.import.toast.importDonePartial', { failed })
              : undefined,
            variant: failed ? 'destructive' : 'default',
          });
          onOpenChange(false);
          reset();
        }
      } catch {
        // keep polling; transient backend errors are fine
      }
    };
    const timer = setInterval(tick, 2000);
    tick();
    return () => {
      stopped = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [progressStoryId]);

  const inProgress = progressStoryId !== null;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!importing) onOpenChange(o);
      }}
    >
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('stories.import.title')}</DialogTitle>
        </DialogHeader>

        {inProgress ? (
          <div className="flex flex-col items-center gap-4 py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <div className="text-sm">
              {t('stories.import.generating', {
                done: progress.done + progress.failed,
                total: progress.total,
              })}
            </div>
            <div className="w-full max-w-md h-2 bg-muted rounded overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{
                  width: `${progress.total ? ((progress.done + progress.failed) / progress.total) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="import-name">{t('stories.import.nameLabel')}</Label>
              <Input
                id="import-name"
                value={storyName}
                onChange={(e) => setStoryName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="import-text">{t('stories.import.textLabel')}</Label>
              <Textarea
                id="import-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={8}
              />
            </div>
            <div className="flex items-center gap-4">
              <div className="flex flex-col gap-1">
                <Label>{t('stories.import.granularityLabel')}</Label>
                <Select
                  value={granularity}
                  onValueChange={(v) => {
                    setGranularity(v as Granularity);
                    setSegments(null);
                  }}
                >
                  <SelectTrigger className="w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="paragraph">{t('stories.import.gran.paragraph')}</SelectItem>
                    <SelectItem value="chapter">{t('stories.import.gran.chapter')}</SelectItem>
                    <SelectItem value="chars">{t('stories.import.gran.chars')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant="outline"
                onClick={handlePreviewSplit}
                disabled={splitting || !text.trim()}
              >
                {splitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {t('stories.import.previewButton')}
              </Button>
            </div>

            {segments && (
              <div className="flex flex-col gap-2">
                <Label>{t('stories.import.segmentsFound', { count: segments.length })}</Label>
                <div className="max-h-64 overflow-y-auto border rounded-md">
                  {segments.map((seg, i) => (
                    <div
                      // biome-ignore lint/suspicious/noArrayIndexKey: rows never reorder; whole list is replaced on re-preview
                      key={i}
                      className="flex items-center gap-3 px-3 py-2 border-b last:border-b-0"
                    >
                      <span className="text-xs text-muted-foreground w-8 shrink-0">{i + 1}</span>
                      <span className="flex-1 text-sm truncate" title={seg}>
                        {seg}
                      </span>
                      <Select
                        value={rowProfiles[i] ?? ''}
                        onValueChange={(v) => setRowProfiles((p) => ({ ...p, [i]: v }))}
                      >
                        <SelectTrigger className="w-40 shrink-0">
                          <SelectValue placeholder={t('stories.import.profile')} />
                        </SelectTrigger>
                        <SelectContent>
                          {(profiles ?? []).map((p) => (
                            <SelectItem key={p.id} value={p.id}>
                              {p.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={importing}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleStart} disabled={!segments || !storyName.trim() || importing}>
            {importing ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            {t('stories.import.startButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
