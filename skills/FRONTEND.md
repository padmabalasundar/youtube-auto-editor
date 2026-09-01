# Frontend Skill

> React + TypeScript + Vite + Tailwind + React Query

No Chakra UI, no Framer Motion, no auth context - this build has no login.
UI is a fixed dark, Netflix-inspired theme (no light/dark toggle).

---

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/          # Button, Card, StatusBadge, ProgressLoader
│   │   └── layout/       # Layout (header + page shell)
│   ├── pages/            # HomePage (upload + list), VideoDetailPage
│   ├── hooks/             # useVideos.ts - all React Query hooks
│   ├── services/          # api.ts - the one axios instance
│   ├── types/             # Video, Clip, VideoStatus, ClipType
│   └── App.tsx
└── package.json
```

---

## App Router

```typescript
// App.tsx
const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/videos/:id" element={<VideoDetailPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

---

## API Client

```typescript
// services/api.ts
export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api`,
});
```

No auth interceptor, no token refresh - there's nothing to authenticate.
`VITE_API_URL` is baked in at build time; the frontend appends `/api` (via
`api.ts`) and `/output` (directly, for clip video `src` URLs) itself.

---

## React Query Hooks Pattern

```typescript
// hooks/useVideos.ts
const isVideoInFlight = (video: Video | undefined): boolean =>
  video?.status === 'pending' || video?.status === 'processing';

export const useVideos = () =>
  useQuery({
    queryKey: ['videos'],
    queryFn: async (): Promise<Video[]> => (await api.get<Video[]>('/videos')).data,
    // Pipeline runs server-side in the background - poll while anything is in flight.
    refetchInterval: (query) => (query.state.data?.some(isVideoInFlight) ? 3000 : false),
  });

export const useCreateVideo = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<Video> => {
      const formData = new FormData();
      formData.append('file', file);
      const { data } = await api.post<Video>('/videos', formData);
      return data;
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['videos'] }),
  });
};
```

Errors are normalized once via a shared `extractErrorMessage(error)` helper
that pulls FastAPI's `{ detail: string }` out of an Axios error, so every
mutation's `.error.message` is already a user-displayable string.

---

## UI Components (Netflix-dark theme)

```typescript
// components/ui/Button.tsx
const variantStyles = {
  primary: 'bg-nflix-red text-white hover:bg-nflix-red-dark',
  secondary: 'bg-white/15 text-white hover:bg-white/25',
};
```

```typescript
// components/ui/Card.tsx - hover-scale "poster tile"
className={`rounded-md bg-nflix-surface p-4 transition-transform duration-200
  hover:scale-[1.03] hover:shadow-xl hover:shadow-black/50 ${className}`}
```

Color tokens (`nflix-red`, `nflix-black`, `nflix-surface`) are defined once
via Tailwind v4's `@theme` block in `index.css` - there's no
`tailwind.config.js` in this build (Tailwind v4 + `@tailwindcss/vite`).

The whole app is a single fixed dark palette - **no `dark:` variant classes**
anywhere, since Netflix has no light mode and it keeps the shipped CSS
smaller. If you're tempted to add a light theme, that's a deliberate design
change, not a bug fix.

---

## UI Rules (this build)

| Element | Use This Component |
|---------|--------------------|
| Any card/tile | `Card` (hover-scale) |
| Primary actions | `Button variant="primary"` (red) |
| Secondary actions | `Button variant="secondary"` (translucent white) |
| Video status | `StatusBadge` |
| In-progress pipeline state | `ProgressLoader` (per-stage progress bar) |

No `PageWrapper`/`GlassCard`/`GradientButton`/`MeshBackground` - those were
template components for a different, marketing-heavy multi-tenant SaaS and
don't exist in this codebase.
