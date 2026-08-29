export type VideoStatus = 'pending' | 'processing' | 'done' | 'failed';

export type ClipType = 'summary' | 'main_idea' | 'pain_point_solution';

export interface Clip {
  id: number;
  video_id: number;
  type: ClipType;
  hook_title: string;
  start_time: number;
  end_time: number;
  file_path: string;
  created_at: string;
}

export interface Video {
  id: number;
  youtube_url: string;
  youtube_id: string;
  title: string | null;
  status: VideoStatus;
  error_message: string | null;
  language: string | null;
  created_at: string;
  clips: Clip[];
}
