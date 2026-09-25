# Just News — frontend

Next.js (App Router) client for Just News. Fully client-rendered:
polls the FastAPI backend (`NEXT_PUBLIC_API_URL`) via SWR every 3 minutes
and re-renders without a full page reload. See the repo root `README.md`
for the full project overview and setup instructions.

```bash
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev
```
