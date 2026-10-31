// Transacción representativa (consulta datos, no estáticos): búsqueda paginada de lotes + listado de hogares.
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: { carga: { executor: 'ramping-vus', startVUs: 0, stages: JSON.parse(__ENV.STAGES), gracefulRampDown: '20s' } },
  thresholds: { http_req_duration: ['p(95)<1000'], http_req_failed: ['rate<0.01'] },   // umbral acordado
  summaryTrendStats: ['avg', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
};
const BASE = __ENV.BASE_URL;
const TERMINOS = ['leche', 'arroz', 'S-001', 'atun', 'pan', 'frijol', 'huevo', ''];

export function setup() {
  const r = http.post(`${BASE}/api/auth/login`, JSON.stringify({ email: 'coordinador@redalimenta.test', password: __ENV.SEED_PASSWORD }),
    { headers: { 'content-type': 'application/json' } });
  check(r, { 'login 200': (x) => x.status === 200 });
  return { cookie: `ra_session=${r.cookies.ra_session[0].value}` };
}

export default function (d) {
  const h = { headers: { cookie: d.cookie } };
  const q = TERMINOS[Math.floor(Math.random() * TERMINOS.length)];
  const p = 1 + Math.floor(Math.random() * 8);
  const r1 = http.get(`${BASE}/api/lotes?q=${q}&page=${p}&size=20`, Object.assign({ tags: { name: 'GET /api/lotes' } }, h));
  const r2 = http.get(`${BASE}/api/hogares?page=${p}&size=20`, Object.assign({ tags: { name: 'GET /api/hogares' } }, h));
  check(r1, { 'lotes 200': (x) => x.status === 200 });
  check(r2, { 'hogares 200': (x) => x.status === 200 });
  sleep(0.5);
}
