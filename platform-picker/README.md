# Platform Picker — AI Short-Form Video Platform Recommender

Tell the AI about your content. Get a ranked list of TikTok, YouTube Shorts, Instagram Reels, and Snapchat Spotlight — with scores and reasons tailored to your niche.

## Setup (3 steps)

### 1. Get a DashScope API key (free tier available)
1. Go to dashscope.aliyuncs.com and sign up
2. Navigate to **API Keys** → **Create API Key**
3. Copy the key (starts with `sk-`)

### 2. Configure your key
Rename `.env.example` to `.env` and paste your key:
```
VITE_DASHSCOPE_API_KEY=sk-your-key-here
```

### 3. Run the app
```bash
npm install
npm run dev
```
Open http://localhost:5173

## Deploy to Vercel
1. Import repo into vercel.com — set **Root Directory** to `platform-picker`
2. Add environment variable: `VITE_DASHSCOPE_API_KEY` = your key
3. Deploy

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "VITE_DASHSCOPE_API_KEY is not configured" | Rename `.env.example` to `.env` and add your key |
| 401 Unauthorized | Key is invalid or expired — regenerate at dashscope.aliyuncs.com |
| Blank results / parse error | Rare model issue — hit "Try another profile" and retry |
| CORS error in browser | Expected — DashScope supports direct browser calls |

## How it works
Sends your creator profile to Alibaba Cloud's Qwen model via DashScope API. The model scores and ranks the 4 platforms based on your niche, style, and goals. All AI calls are client-side — no backend, no data stored. Buyer supplies their own API key.

## Stack
React 18 · TypeScript · Vite · Tailwind CSS · DashScope (qwen-plus)
