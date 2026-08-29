import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
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
            <StatusBadge status={video.status} />
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
            <div className="mt-6 flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
              Processing video... this page will update automatically.
            </div>
          )}

          {video.status === 'done' && (
            <div className="mt-6 flex flex-col gap-4">
              {video.clips.length === 0 && (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  No clips were generated for this video.
                </p>
              )}
              {video.clips.map((clip) => (
                <Card key={clip.id}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="font-medium">{clip.hook_title}</h2>
                    <span className="inline-flex items-center rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                      {CLIP_TYPE_LABELS[clip.type]}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {formatTime(clip.start_time)} &ndash; {formatTime(clip.end_time)}
                  </p>
                  <video
                    controls
                    className="mt-3 w-full rounded-lg bg-black"
                    src={`${import.meta.env.VITE_API_URL}/output/${clip.file_path}`}
                  />
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
