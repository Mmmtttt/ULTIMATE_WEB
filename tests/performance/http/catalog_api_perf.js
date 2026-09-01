import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 4,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{endpoint:comic_list}': ['p(95)<350'],
    'http_req_duration{endpoint:video_list}': ['p(95)<350'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:5035';

export default function () {
  const common = 'paginate=1&summary=1&page=1&page_size=24&sort_type=score&sort_order=desc&keyword=%E6%80%A7%E8%83%BD';
  const comic = http.get(`${BASE_URL}/api/v1/comic/list?${common}`, { tags: { endpoint: 'comic_list' } });
  check(comic, { 'comic list ok': (res) => res.status === 200 && res.json('code') === 200 });

  const video = http.get(`${BASE_URL}/api/v1/video/list?${common}`, { tags: { endpoint: 'video_list' } });
  check(video, { 'video list ok': (res) => res.status === 200 && res.json('code') === 200 });
  sleep(1);
}
