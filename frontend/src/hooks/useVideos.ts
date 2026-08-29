import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { api } from '../services/api';
import type { Video } from '../types';

const isVideoInFlight = (video: Video | undefined): boolean =>
  video?.status === 'pending' || video?.status === 'processing';

export const useVideos = () => {
  return useQuery({
    queryKey: ['videos'],
    queryFn: async (): Promise<Video[]> => {
      const { data } = await api.get<Video[]>('/videos');
      return data;
    },
  });
};

export const useVideo = (id: number) => {
  return useQuery({
    queryKey: ['videos', id],
    queryFn: async (): Promise<Video> => {
      const { data } = await api.get<Video>(`/videos/${id}`);
      return data;
    },
    refetchInterval: (query) => (isVideoInFlight(query.state.data) ? 3000 : false),
  });
};

const extractErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    if (detail) return detail;
    if (error.message) return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'Something went wrong. Please try again.';
};

export const useCreateVideo = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File): Promise<Video> => {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const { data } = await api.post<Video>('/videos', formData);
        return data;
      } catch (error) {
        throw new Error(extractErrorMessage(error));
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['videos'] });
    },
  });
};

export const useRetryVideo = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (videoId: number): Promise<Video> => {
      try {
        const { data } = await api.post<Video>(`/videos/${videoId}/retry`);
        return data;
      } catch (error) {
        throw new Error(extractErrorMessage(error));
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['videos'] });
    },
  });
};
