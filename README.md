# 🥀 Ruhi Ji — Telegram Bot

> Savage Queen 👑 | Hinglish Gen-Z | Kimi-K2 via HuggingFace | PostgreSQL Memory

---

## 📁 Files

```
ruhi_ji_bot/
├── bot.py           ← Main bot (all handlers + commands)
├── database.py      ← PostgreSQL helpers (NeonDB)
├── llm.py           ← Kimi-K2 caller via HF Router (openai library)
├── config.py        ← Constants + ASCII UI
├── requirements.txt ← 4 lightweight deps
├── render.yaml      ← Render auto-deploy config
└── .env.example     ← Copy → .env and fill secrets
```

---

## 🚀 Render.com Deploy (Step-by-Step)

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
Render dashboard → **Environment** tab mein yeh 4 variables add karo:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | @BotFather se mila token |
| `OWNER_ID` | Tera numeric Telegram ID (@userinfobot se lo) |
| `HF_TOKEN` | huggingface.co/settings/tokens se lo |
| `DATABASE_URL` | NeonDB connection string |

### Step 4 — Deploy!
**Save Changes** → Render automatically build + deploy karega.

Logs mein yeh dikhega:
```
✅ Database connected successfully.
✅ Bot running as @YourBotUsername
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
| Wake Phrase | "Ruhi Ji" → 10 min group session starts |
| Private DM | Always replies, 50 msg memory |
| Group | Only when woken, 20 msg memory |
| Owner Mode | Cute + obedient for @RUHI_VIG_QNR |
| User Mode | Savage roast queen for everyone else 😏 |
| Rate Limit | 3 sec per user (spam protection) |
| FIFO Trim | Auto-trims context at 12,000 chars |

---

## 📋 All Commands

**User:**
`/start` `/help` `/profile` `/clear` `/reset` `/lang` `/personality` `/usage` `/summary`

**Admin (Owner only by default):**
`/admin` `/addadmin` `/removeadmin` `/broadcast` `/ban` `/unban`
`/totalusers` `/activeusers` `/forceclear` `/badwords` `/addbadword`
`/removebadword` `/setphrase` `/shutdown` `/restart`

---

Made with 💅 by @RUHI_VIG_QNR
