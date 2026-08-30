# Hook Generator — AI Viral Hook Writer for Short-Form Video

Input your niche, platform, topic, and tone. Get 10 scroll-stopping hooks ranked by viral potential — with type labels and one-click copy.

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
1. Import repo into vercel.com — set **Root Directory** to `hook-generator`
2. Add environment variable: `VITE_DASHSCOPE_API_KEY` = your key
3. Deploy

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "VITE_DASHSCOPE_API_KEY is not configured" | Rename `.env.example` to `.env` and add your key |
| 401 Unauthorized | Key expired — regenerate at dashscope.aliyuncs.com |
| Fewer than 10 hooks returned | Rare model issue — generate again |

## How it works
Sends your 4-field input to Alibaba Cloud's Qwen model. The model generates 10 hooks across different psychological types (curiosity gap, controversy, social proof, etc.) and scores them by likely scroll-stop rate. All client-side — no backend, no data stored.

## Hook types generated
Curiosity gap · Controversy · Social proof · Number/list · Pain point · Bold claim · Story opener · Question · Direct value · Pattern interrupt

## Stack
React 18 · TypeScript · Vite · Tailwind CSS · DashScope (qwen-plus)
