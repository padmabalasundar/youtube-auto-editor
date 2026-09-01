import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useCreateVideo, useVideos } from '../hooks/useVideos';

const ACCEPTED_EXTENSIONS = '.mp4,.mov,.mkv,.webm,.avi';

export const HomePage = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: videos, isLoading: isVideosLoading } = useVideos();
  const createVideo = useCreateVideo();
  const navigate = useNavigate();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
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

  return (
    <div>
      <section className="-mx-4 -mt-4 rounded-b-lg bg-gradient-to-b from-black/60 via-black/40 to-nflix-black bg-nflix-red/10 px-4 py-16 text-center sm:-mx-8 sm:px-8">
        <h1 className="mx-auto max-w-2xl text-3xl font-black tracking-tight sm:text-5xl">
          Turn long videos into scroll-stopping clips
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-gray-300">
          Upload once. Get shareable, captioned shorts &mdash; automatically.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mx-auto mt-8 flex max-w-xl flex-col gap-3 sm:flex-row"
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

        {createVideo.isPending && (
          <p className="mt-3 text-sm text-red-400">
            Uploading&hellip; you&apos;ll be taken to the video&apos;s page to watch progress live.
          </p>
        )}

        {createVideo.isError && (
          <div role="alert" className="mx-auto mt-3 max-w-xl rounded bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {createVideo.error.message}
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
