import type { VideoStatus } from '../../types';

interface StatusBadgeProps {
  status: VideoStatus;
  percent?: number | null;
}

const STATUS_STYLES: Record<VideoStatus, string> = {
  pending: 'bg-white/10 text-gray-300',
  processing: 'bg-nflix-red/20 text-red-400 animate-pulse',
  done: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
};

const STATUS_LABELS: Record<VideoStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  done: 'Done',
  failed: 'Failed',
};

export const StatusBadge = ({ status, percent }: StatusBadgeProps) => {
  const showPercent = status === 'processing' && typeof percent === 'number';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {showPercent ? `Processing ${percent}%` : STATUS_LABELS[status]}
    </span>
  );
};
