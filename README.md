# SchoolBrain.ai — Backend Setup Guide

## What's in this folder

```
schoolbrain/
├── main.py              ← FastAPI app entry point
├── database.py          ← SQLite models (User, School, UsageLog)
├── auth_utils.py        ← JWT auth, bcrypt passwords
├── memory_system.py     ← 4-layer memory (Working/Episodic/Semantic/Procedural)
├── ai_helper.py         ← Ollama wrapper, RAG, JSON generation with retry
├── seed_data.py         ← Insert 20 fake students for demo
├── requirements.txt     ← All Python dependencies
├── Dockerfile           ← Container build
├── docker-compose.yml   ← Full stack (API + Redis + Worker)
├── nginx.conf           ← Reverse proxy config
├── models/
│   └── schemas.py       ← All Pydantic request/response models
└── routers/
    ├── auth.py          ← POST /auth/login, /auth/register
    ├── chat.py          ← POST /chat (RAG-augmented)
    ├── students.py      ← POST /students/weak, GET /students/list
    ├── quiz.py          ← POST /quiz/generate
    ├── plans.py         ← POST /intervention/plan, /lesson/plan
    ├── analytics.py     ← GET /analytics/overview
    ├── reports.py       ← GET /reports/pdf
    ├── memory_routes.py ← POST /memory/index, /memory/events/bulk
    └── admin.py         ← GET /admin/schools (superadmin only)
```

---

## Day 1 — Buy server & install Ollama

```bash
# On your Hetzner CX21 VPS (Ubuntu 22.04):
apt update && apt install -y docker.io docker-compose git curl nginx certbot python3-certbot-nginx
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable ollama && systemctl start ollama

# Test Ollama is running:
curl http://localhost:11434/api/tags
```

## Day 2 — Pull AI model

```bash
ollama pull qwen2.5:1.5b          # 900MB, ~5 min
ollama pull bge-m3                 # Embedding model for RAG
ollama run qwen2.5:1.5b           # Quick test — type a message
```

## Day 3 — Deploy this backend

```bash
git clone https://github.com/YOUR_USERNAME/schoolbrain /opt/schoolbrain
cd /opt/schoolbrain

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Seed demo data:
python seed_data.py demo

# Start API:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Test:
curl http://localhost:8000/health
```

## Day 4 — First superadmin account

```bash
curl -X POST http://localhost:8000/auth/register/superadmin \
  -H "Content-Type: application/json" \
  -d '{"email":"you@yourmail.com","password":"StrongPass123!","school_id":"platform","role":"superadmin"}'
```

Save the `access_token` from the response. You need it for all API calls.

## Day 5 — Create demo school + teacher

```bash
# 1. Create demo school (use your superadmin token):
curl -X POST http://localhost:8000/admin/schools \
  -H "Authorization: Bearer YOUR_SUPERADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"school_id":"demo","name":"Demo Public School","admin_email":"admin@demo.com","admin_password":"Demo@123","plan":"Starter"}'

# 2. Register a teacher:
curl -X POST http://localhost:8000/auth/register \
  -H "Authorization: Bearer YOUR_SUPERADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@demo.com","password":"Teacher@123","school_id":"demo","role":"teacher"}'

# 3. Log in as teacher:
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@demo.com","password":"Teacher@123"}'
```

## Day 7 — Nginx + SSL

```bash
# Copy nginx config:
cp nginx.conf /etc/nginx/sites-available/schoolbrain
# Edit it — replace yourdomain.com with your actual domain
nano /etc/nginx/sites-available/schoolbrain

ln -s /etc/nginx/sites-available/schoolbrain /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Free SSL:
certbot --nginx -d yourdomain.com

# Test live:
curl https://yourdomain.com/health
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /health | No | Health check |
| POST | /auth/login | No | Get JWT token |
| POST | /chat | Teacher+ | RAG chat |
| POST | /students/weak | Teacher+ | Detect at-risk students |
| GET | /students/list | Teacher+ | All students |
| GET | /students/{id}/scores | Teacher+ | Score history |
| POST | /quiz/generate | Teacher+ | Generate MCQ quiz |
| POST | /intervention/plan | Teacher+ | 7-day plan |
| POST | /lesson/plan | Teacher+ | Lesson plan |
| GET | /analytics/overview | School Admin+ | Dashboard data |
| GET | /reports/pdf?student_id=X | Teacher+ | Download PDF |
| POST | /memory/index | Teacher+ | Index curriculum text |
| POST | /memory/index/pdf | Teacher+ | Upload & index PDF |
| GET | /admin/schools | Superadmin | All schools |
| POST | /admin/schools | Superadmin | Create school |
| GET | /admin/revenue | Superadmin | Revenue overview |

## Production checklist

- [ ] Change `SECRET_KEY` in docker-compose.yml to a random 32+ char string
- [ ] Set up daily DB backup: `sqlite3 schoolbrain.db .dump > backup_$(date +%Y%m%d).sql`
- [ ] Configure UptimeRobot to ping `/health` every 5 min
- [ ] Set up Backblaze B2 + rclone for backup storage (Rs 200/month)
- [ ] Disable `/auth/register/superadmin` endpoint after first setup

## Gross margin calculation

```
Monthly infra cost:
  Hetzner CX21:      Rs  340
  Lambda Labs GPU:   Rs 3,500
  Backblaze backup:  Rs  200
  TOTAL:             Rs 4,040

Revenue (5 schools × Rs 10,000): Rs 50,000
Gross margin: (50,000 - 4,040) / 50,000 = 91.9%
```
