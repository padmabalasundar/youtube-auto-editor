interface ProgressLoaderProps {
  stage: string | null;
  percent: number | null;
}

const STAGE_LABELS: Record<string, string> = {
  transcribing: 'Transcribing audio',
  segmenting: 'Finding the best moments',
  cutting_clips: 'Cutting & captioning clips',
  done: 'Wrapping up',
};

const STAGE_ORDER = ['transcribing', 'segmenting', 'cutting_clips'];

const describeStage = (stage: string | null): string =>
  (stage && STAGE_LABELS[stage]) ?? 'Getting started';

export const ProgressLoader = ({ stage, percent }: ProgressLoaderProps) => {
  const clamped = Math.min(100, Math.max(0, percent ?? 0));
  const activeIndex = stage ? STAGE_ORDER.indexOf(stage) : -1;

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-4 dark:border-blue-900 dark:bg-blue-950">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-500" />
          </span>
          {describeStage(stage)}&hellip;
        </div>
        <span className="text-sm font-semibold tabular-nums text-blue-700 dark:text-blue-300">
          {clamped}%
        </span>
      </div>

      <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-blue-100 dark:bg-blue-900/60">
        <div
          className="relative h-full overflow-hidden rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-[width] duration-700 ease-out"
          style={{ width: `${clamped}%` }}
        >
          <span className="absolute inset-0 -translate-x-full animate-progress-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent" />
        </div>
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-xs text-blue-600/80 dark:text-blue-400/80">
        {STAGE_ORDER.map((step, index) => (
          <span
            key={step}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-500 ${
              activeIndex === -1
                ? 'bg-blue-200 dark:bg-blue-900'
                : index <= activeIndex
                  ? 'bg-blue-500'
                  : 'bg-blue-200 dark:bg-blue-900'
            }`}
          />
        ))}
      </div>

      <p className="mt-2 text-xs text-blue-600/80 dark:text-blue-400/80">
        This can take a few minutes on CPU &ndash; feel free to leave this page and check back.
      </p>
    </div>
  );
};

export default ProgressLoader;
