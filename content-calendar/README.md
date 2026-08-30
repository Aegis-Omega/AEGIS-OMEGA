# Content Calendar — AI 4-Week Content Plan Generator

Enter your niche, platforms, posting frequency, and 3 content pillars. Get a full 4-week content calendar with daily post ideas, viral hooks, formats, and production notes — downloadable as .txt.

## Setup (3 steps)

### 1. Get a DashScope API key (free tier available)
1. Go to dashscope.aliyuncs.com and sign up
2. **API Keys** → **Create API Key** → copy the `sk-` key

### 2. Configure your key
Rename `.env.example` to `.env`:
```
VITE_DASHSCOPE_API_KEY=sk-your-key-here
```

### 3. Run
```bash
npm install
npm run dev
```

## Deploy to Vercel
Import repo → Root Directory: `content-calendar` → add `VITE_DASHSCOPE_API_KEY` env var → Deploy.

## What you get
- 4 weeks × N posts per week (based on your frequency)
- Each post: day, platform, content pillar, hook, format, production note
- Week themes to keep content cohesive
- Download as .txt for easy scheduling

## Stack
React 18 · TypeScript · Vite · Tailwind CSS · DashScope (qwen-plus)
