import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useCreateVideo, useVideos } from '../hooks/useVideos';

export const HomePage = () => {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const { data: videos, isLoading: isVideosLoading } = useVideos();
  const createVideo = useCreateVideo();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!youtubeUrl.trim() || createVideo.isPending) return;

    createVideo.mutate(
      { youtube_url: youtubeUrl.trim() },
      {
        onSuccess: () => setYoutubeUrl(''),
      }
    );
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold">YouTube Auto Editor</h1>
      <p className="mt-2 text-gray-500 dark:text-gray-400">
        Paste a YouTube URL to automatically generate short clips.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row">
        <input
          type="url"
          required
          placeholder="https://www.youtube.com/watch?v=..."
          value={youtubeUrl}
          onChange={(event) => setYoutubeUrl(event.target.value)}
          disabled={createVideo.isPending}
          className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-900 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        />
        <Button type="submit" disabled={createVideo.isPending}>
          {createVideo.isPending ? 'Processing...' : 'Generate Clips'}
        </Button>
      </form>

      {createVideo.isPending && (
        <p className="mt-3 text-sm text-blue-600 dark:text-blue-400">
          Processing... this may take a minute. Please don&apos;t close this page.
        </p>
      )}

      {createVideo.isError && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
        >
          {createVideo.error.message}
        </div>
      )}

      <h2 className="mt-10 text-lg font-semibold">Videos</h2>

      {isVideosLoading && (
        <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">Loading videos...</p>
      )}

      {!isVideosLoading && videos && videos.length === 0 && (
        <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
          No videos yet. Submit a YouTube URL above to get started.
        </p>
      )}

      {!isVideosLoading && videos && videos.length > 0 && (
        <div className="mt-4 flex flex-col gap-3">
          {videos.map((video) => (
            <Link key={video.id} to={`/videos/${video.id}`}>
              <Card className="transition-colors hover:border-indigo-400 dark:hover:border-indigo-600">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{video.title ?? video.youtube_url}</p>
                    {video.status === 'done' && (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {video.clips.length} clip{video.clips.length === 1 ? '' : 's'}
                      </p>
                    )}
                  </div>
                  <StatusBadge status={video.status} />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default HomePage;
