import type { MetadataRoute } from 'next';

export const dynamic = 'force-static';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: '살롱 컨시어지',
    short_name: '컨시어지',
    description: '헤어 디자이너용 고객 관리',
    start_url: '/',
    display: 'standalone',
    background_color: '#F4F1EC',
    theme_color: '#F4F1EC',
    lang: 'ko',
    icons: [
      { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  };
}
