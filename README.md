# 🥀 Ruhi Ji — Telegram Bot

> Savage Queen 👑 | Hinglish Gen-Z | Kimi-K2 via HuggingFace | PostgreSQL Memory

---

## 📁 Files

```
ruhi_ji_bot/
├── bot.py           ← Main bot (webhook mode + aiohttp server)
├── database.py      ← PostgreSQL helpers (NeonDB)
├── llm.py           ← Kimi-K2 caller via HF Router
├── config.py        ← Constants + ASCII UI
├── requirements.txt ← 5 deps (aiohttp added)
├── render.yaml      ← Render Web Service config
└── .env.example     ← Copy → .env and fill secrets
```

---

## 🚀 Render Free Web Service Deploy

### Step 1 — GitHub pe push karo
```bash
git init
git add .
git commit -m "Ruhi Ji Bot 🥀"
git remote add origin https://github.com/YOUR_USERNAME/ruhi-ji-bot.git
git push -u origin main
```

### Step 2 — Render Dashboard
1. [render.com](https://render.com) pe login karo
2. **New +** → **Web Service** → apna GitHub repo select karo
3. Settings:
   - **Name:** `ruhi-ji-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** `Free`

### Step 3 — Environment Variables
Render dashboard → **Environment** tab mein yeh variables add karo:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | @BotFather se mila token |
| `OWNER_ID` | Tera Telegram numeric ID (@userinfobot se lo) |
| `HF_TOKEN` | huggingface.co/settings/tokens se lo |
| `DATABASE_URL` | NeonDB connection string |

> ⚠️ `RENDER_EXTERNAL_URL` **manually add karne ki zaroorat NAHI** — Render khud set karta hai.

### Step 4 — Deploy!
**Save Changes** → Render build + deploy karega.

Logs mein yeh dikhega:
```
✅ Database connected successfully.
✅ Webhook registered → https://ruhi-ji-bot.onrender.com/webhook/...
✅ Bot ready: @YourBotUsername
✅ Self-ping loop started (every 10 min)
```

---

## 🤖 Model Info

| Setting | Value |
|---------|-------|
| Provider | HuggingFace Router |
| Model | `moonshotai/Kimi-K2-Instruct-0905:groq` |
| Backend | Groq (fast inference) |
| Library | `openai` Python SDK |

---

## 💬 How It Works

| Feature | Detail |
|---------|--------|
| Mode | Webhook (Render Web Service) |
| Wake Phrase | "Ruhi Ji" → 10 min group session |
| Private DM | Always replies, 50 msg memory |
| Group | Only when woken, 20 msg memory |
| Owner Mode | Cute + obedient for @RUHI_VIG_QNR |
| User Mode | Savage roast queen 😏 |
| Rate Limit | 3 sec per user |
| Self-Ping | Every 10 min to keep Render awake |
| Sleep Fix | `/health` endpoint prevents free tier sleep |

---

## 📋 Commands

**User:**
`/start` `/help` `/profile` `/clear` `/reset` `/lang` `/personality` `/usage` `/summary`

**Admin:**
`/admin` `/addadmin` `/removeadmin` `/broadcast` `/ban` `/unban`
`/totalusers` `/activeusers` `/forceclear` `/badwords` `/addbadword`
`/removebadword` `/setphrase` `/shutdown` `/restart`

---

## 🔧 Why Webhook Instead of Polling?

Render Free Web Service **sone lagta hai** jab koi HTTP request nahi aata.
Polling mode mein bot khud requests karta hai — sleep hote hi band ho jaata hai.

Webhook mode mein **Telegram messages directly** Render ke server pe aate hain,
isliye server **always active** rehta hai jab messages aa rahe hain.
Self-ping loop additional guarantee deta hai ki service soye nahi.

---

Made with 💅 by @RUHI_VIG_QNR
