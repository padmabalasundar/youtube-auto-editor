import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useCreateVideo, useCreateVideoFromUrl, useVideos } from '../hooks/useVideos';

const ACCEPTED_EXTENSIONS = '.mp4,.mov,.mkv,.webm,.avi';
// Must match the backend's MAX_VIDEO_DURATION_SECONDS (backend/app/config.py).
const MAX_VIDEO_MINUTES = 30;

type InputMode = 'upload' | 'url';

export const HomePage = () => {
  const [inputMode, setInputMode] = useState<InputMode>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: videos, isLoading: isVideosLoading } = useVideos();
  const createVideo = useCreateVideo();
  const createVideoFromUrl = useCreateVideoFromUrl();
  const navigate = useNavigate();

  const activeMutation = inputMode === 'upload' ? createVideo : createVideoFromUrl;

  const handleUploadSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile || createVideo.isPending) return;

    createVideo.mutate(selectedFile, {
      onSuccess: (video) => {
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        navigate(`/videos/${video.id}`);
      },
    });
  };

  const handleUrlSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!youtubeUrl.trim() || createVideoFromUrl.isPending) return;

    createVideoFromUrl.mutate(youtubeUrl.trim(), {
      onSuccess: (video) => {
        setYoutubeUrl('');
        navigate(`/videos/${video.id}`);
      },
    });
  };

  return (
    <div>
      <section className="-mx-4 -mt-4 rounded-b-lg bg-gradient-to-b from-black/60 via-black/40 to-nflix-black bg-nflix-red/10 px-4 py-16 text-center sm:-mx-8 sm:px-8">
        <h1 className="mx-auto max-w-2xl text-3xl font-black tracking-tight sm:text-5xl">
          Turn long videos into scroll-stopping clips
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-gray-300">
          Upload a file or paste a YouTube link. Get shareable, captioned shorts &mdash; automatically.
        </p>
        <p className="mx-auto mt-1 max-w-xl text-xs text-gray-400">
          Works with videos up to {MAX_VIDEO_MINUTES} minutes long.
        </p>

        <div className="mx-auto mt-6 flex max-w-xl justify-center gap-2">
          <button
            type="button"
            onClick={() => setInputMode('upload')}
            className={`rounded px-4 py-1.5 text-sm font-semibold transition-colors ${
              inputMode === 'upload' ? 'bg-nflix-red text-white' : 'bg-white/10 text-gray-300 hover:bg-white/15'
            }`}
          >
            Upload Video
          </button>
          <button
            type="button"
            onClick={() => setInputMode('url')}
            className={`rounded px-4 py-1.5 text-sm font-semibold transition-colors ${
              inputMode === 'url' ? 'bg-nflix-red text-white' : 'bg-white/10 text-gray-300 hover:bg-white/15'
            }`}
          >
            YouTube URL
          </button>
        </div>

        {inputMode === 'upload' ? (
          <form
            onSubmit={handleUploadSubmit}
            className="mx-auto mt-4 flex max-w-xl flex-col gap-3 sm:flex-row"
          >
            <input
              ref={fileInputRef}
              type="file"
              required
              accept={ACCEPTED_EXTENSIONS}
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              disabled={createVideo.isPending}
              className="flex-1 rounded border border-white/20 bg-black/40 px-4 py-3 text-sm text-white file:mr-3 file:rounded file:border-0 file:bg-white/15 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white disabled:cursor-not-allowed disabled:opacity-50"
            />
            <Button type="submit" disabled={!selectedFile || createVideo.isPending} className="px-8 py-3 text-base">
              {createVideo.isPending ? 'Processing...' : 'Generate Clips'}
            </Button>
          </form>
        ) : (
          <form
            onSubmit={handleUrlSubmit}
            className="mx-auto mt-4 flex max-w-xl flex-col gap-3 sm:flex-row"
          >
            <input
              type="url"
              required
              placeholder="https://www.youtube.com/watch?v=..."
              value={youtubeUrl}
              onChange={(event) => setYoutubeUrl(event.target.value)}
              disabled={createVideoFromUrl.isPending}
              className="flex-1 rounded border border-white/20 bg-black/40 px-4 py-3 text-sm text-white placeholder:text-gray-500 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <Button
              type="submit"
              disabled={!youtubeUrl.trim() || createVideoFromUrl.isPending}
              className="px-8 py-3 text-base"
            >
              {createVideoFromUrl.isPending ? 'Processing...' : 'Generate Clips'}
            </Button>
          </form>
        )}
        {inputMode === 'url' && (
          <p className="mx-auto mt-2 max-w-xl text-xs text-gray-400">
            YouTube videos longer than {MAX_VIDEO_MINUTES} minutes are rejected before downloading.
          </p>
        )}

        {activeMutation.isPending && (
          <p className="mt-3 text-sm text-red-400">
            {inputMode === 'upload' ? 'Uploading' : 'Fetching'}&hellip; you&apos;ll be taken to the
            video&apos;s page to watch progress live.
          </p>
        )}

        {activeMutation.isError && (
          <div role="alert" className="mx-auto mt-3 max-w-xl rounded bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {activeMutation.error.message}
          </div>
        )}
      </section>

      <h2 className="mt-10 text-xl font-bold">Your Videos</h2>

      {isVideosLoading && <p className="mt-3 text-sm text-gray-400">Loading videos...</p>}

      {!isVideosLoading && videos && videos.length === 0 && (
        <p className="mt-3 text-sm text-gray-400">No videos yet. Upload one above to get started.</p>
      )}

      {!isVideosLoading && videos && videos.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {videos.map((video) => (
            <Link key={video.id} to={`/videos/${video.id}`}>
              <Card className="flex flex-col">
                <div className="flex aspect-video items-center justify-center rounded bg-gradient-to-br from-nflix-red/30 to-black text-3xl">
                  ▶
                </div>
                <p className="mt-3 truncate text-sm font-medium">
                  {video.title ?? video.original_filename}
                </p>
                <div className="mt-2 flex items-center justify-between gap-2">
                  {video.status === 'done' && (
                    <span className="text-xs text-gray-400">
                      {video.clips.length} clip{video.clips.length === 1 ? '' : 's'}
                    </span>
                  )}
                  <StatusBadge status={video.status} percent={video.progress_percent} />
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
