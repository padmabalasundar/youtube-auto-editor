import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { ProgressLoader } from '../components/ui/ProgressLoader';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useRetryVideo, useVideo } from '../hooks/useVideos';
import type { Clip } from '../types';

const CLIP_TYPE_LABELS: Record<Clip['type'], string> = {
  summary: 'Summary',
  main_idea: 'Main Idea',
  pain_point_solution: 'Pain Point & Solution',
};

const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export const VideoDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const videoId = Number(id);
  const { data: video, isLoading, isError } = useVideo(videoId);
  const navigate = useNavigate();
  const retryVideo = useRetryVideo();

  const handleRetry = () => {
    if (!video || retryVideo.isPending) return;
    retryVideo.mutate(video.id, {
      onSuccess: (newVideo) => navigate(`/videos/${newVideo.id}`),
    });
  };

  return (
    <div>
      <Link to="/" className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
        &larr; Back to list
      </Link>

      {isLoading && (
        <p className="mt-6 text-sm text-gray-500 dark:text-gray-400">Loading video...</p>
      )}

      {isError && (
        <div
          role="alert"
          className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
        >
          Could not load this video. It may not exist.
        </div>
      )}

      {video && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold">{video.title ?? video.original_filename}</h1>
            <StatusBadge status={video.status} percent={video.progress_percent} />
          </div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Created {new Date(video.created_at).toLocaleString()}
          </p>

          {video.status === 'failed' && (
            <div
              role="alert"
              className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
            >
              <p>{video.error_message ?? 'Processing failed for an unknown reason.'}</p>
              <Button
                type="button"
                variant="secondary"
                onClick={handleRetry}
                disabled={retryVideo.isPending}
                className="mt-3"
              >
                {retryVideo.isPending ? 'Retrying...' : 'Try again'}
              </Button>
              {retryVideo.isError && (
                <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                  {retryVideo.error.message}
                </p>
              )}
            </div>
          )}

          {(video.status === 'pending' || video.status === 'processing') && (
            <div className="mt-6">
              <ProgressLoader stage={video.progress_stage} percent={video.progress_percent} />
            </div>
          )}

          {video.status === 'done' && (
            <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {video.clips.length === 0 && (
                <p className="col-span-full text-sm text-gray-500 dark:text-gray-400">
                  No clips were generated for this video.
                </p>
              )}
              {video.clips.map((clip) => (
                <Card key={clip.id} className="flex flex-col">
                  <video
                    controls
                    className="aspect-[9/16] w-full rounded-lg bg-black object-cover"
                    src={`${import.meta.env.VITE_API_URL}/output/${clip.file_path}`}
                  />
                  <div className="mt-2 flex items-start justify-between gap-1">
                    <h2 className="truncate text-sm font-medium">{clip.hook_title}</h2>
                  </div>
                  <span className="mt-1 inline-flex w-fit items-center rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                    {CLIP_TYPE_LABELS[clip.type]}
                  </span>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {formatTime(clip.start_time)} &ndash; {formatTime(clip.end_time)}
                  </p>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VideoDetailPage;
