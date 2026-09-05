import axios from 'axios';

// Client for the Business-SK affiliate API (separate service on :8100),
// proxied via Vite under /sk-api. No admin token — the affiliate has no auth.
const sk = axios.create({ baseURL: '/sk-api/api', timeout: 0 });
const data = (r) => r.data;

// Every user-facing affiliate endpoint is wired below. Endpoints intentionally NOT exposed
// (legacy/internal, superseded by the current Amazon→Instagram flow): /api/run (old
// Pinterest LangGraph posting — replaced by IG /api/sk/carousel), /api/pipeline (old node
// viz), /api/history (dedup ledger log — post history comes from /api/posts).
export default {
  health:     () => sk.get('/health').then(data),          // liveness + whether a run is active
  config:     () => sk.get('/config').then(data),          // model, tag, readiness
  categories: () => sk.get('/categories').then(data),      // base categories + commission rates
  stats:      () => sk.get('/stats').then(data),           // RAG dedup flywheel (products remembered)

  // Content service. opts may include: q, marketplace, min_rating, min_reviews, price_min, price_max.
  generate: (categories, productsPerRun, opts = {}) =>
    sk.get('/generate', {
      params: {
        ...(opts.q ? { q: opts.q } : { categories: categories.join(',') }),
        products_per_run: productsPerRun,
        ...(opts.marketplace ? { marketplace: opts.marketplace } : {}),
        ...(opts.min_rating != null ? { min_rating: opts.min_rating } : {}),
        ...(opts.min_reviews != null ? { min_reviews: opts.min_reviews } : {}),
        ...(opts.price_min != null ? { price_min: opts.price_min } : {}),
        ...(opts.price_max != null ? { price_max: opts.price_max } : {}),
      },
    }).then(data),

  // Posting history (the IG backend does the actual publishing; the affiliate records it).
  recordPost:  (body) => sk.post('/posts', body).then(data),
  posts:       (limit = 50) => sk.get('/posts', { params: { limit } }).then(data),

  // Link hub — all posted products with your affiliate tag (one page).
  hub:         (category) => sk.get('/hub', { params: category ? { category } : {} }).then(data),

  // Discovery — taxonomy (families/subcategories/angles) + collections (price bands + bundles).
  taxonomy:    () => sk.get('/taxonomy').then(data),
  collections: (category) => sk.get('/collections', { params: category ? { category } : {} }).then(data),
};
