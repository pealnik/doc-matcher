# Backend Deployment Guide (Docker on Hostinger)

> **Frontend is deployed on Vercel.** This guide covers only the backend API deployment.

## Quick Deploy (3 Steps)

### 1. Install Docker on Hostinger VPS

```bash
# SSH into your Hostinger server
ssh username@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose -y

# Verify
docker --version
docker-compose --version
```

### 2. Clone & Configure

```bash
# Clone repository
cd ~
git clone https://github.com/yourusername/doc-matcher.git
cd doc-matcher/backend

# Create .env file with your API keys
nano .env
```

Add to `.env`:

```env
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
```

**Update CORS in `api.py`** - Add your Vercel URL:

```python
allow_origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "https://your-app.vercel.app",  # ← Add your Vercel URL
],
```

### 3. Deploy

```bash
# Start the backend
docker-compose up -d --build

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

✅ **Backend is now running on port 8000!**

---

## Set Up Domain & SSL (Recommended)

### 1. Point subdomain to your server

In your domain DNS settings, create an A record:

- **Host**: `api` (for api.yourdomain.com)
- **Points to**: Your Hostinger server IP

### 2. Install Nginx

```bash
sudo apt install nginx certbot python3-certbot-nginx -y
```

### 3. Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/api
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;

        # Allow large PDF uploads
        client_max_body_size 100M;

        # Timeout settings for long-running operations
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Set Up SSL (HTTPS)

```bash
sudo certbot --nginx -d api.yourdomain.com
```

Follow the prompts. Certbot will automatically configure HTTPS.

### 5. Update Vercel Frontend

In your Vercel project, update the environment variable:

```env
VITE_API_URL=https://api.yourdomain.com
```

Redeploy your Vercel frontend for changes to take effect.

---

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Restart backend
docker-compose restart

# Stop backend
docker-compose down

# Update code and restart
git pull
docker-compose up -d --build

# Check disk usage
df -h
du -sh uploads
du -sh vectorstores

# Clean up Docker
docker system prune -a
```

---

## Monitoring & Maintenance

### Auto-restart on server reboot

Docker containers will auto-restart due to `restart: unless-stopped` in docker-compose.yml.

Enable Docker on boot:

```bash
sudo systemctl enable docker
```

### Backups

Backup your data regularly:

```bash
# Create backup
tar -czf backup-$(date +%Y%m%d).tar.gz uploads vectorstores

# Download to local machine
scp username@server-ip:~/doc-matcher/backend/backup-*.tar.gz ~/backups/
```

### Monitor logs

```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Service logs on host
sudo journalctl -u docker -f
```

---

## Troubleshooting

### Port 8000 already in use

```bash
sudo lsof -i :8000
sudo kill -9 <PID>
docker-compose restart
```

### Container won't start

```bash
# Check logs
docker-compose logs

# Restart with rebuild
docker-compose down
docker-compose up -d --build --force-recreate
```

### Out of disk space

```bash
# Check space
df -h

# Clean old uploads (if needed)
rm -rf uploads/reports/*

# Clean Docker cache
docker system prune -a
```

### CORS errors

Make sure your Vercel URL is in the `allow_origins` list in `api.py`

---

## Security Checklist

- ✅ `.env` file is secure (not in git)
- ✅ SSL/HTTPS enabled
- ✅ Firewall configured (UFW)
- ✅ Regular system updates
- ✅ Strong API keys
- ✅ Regular backups

---

## Cost & Performance Tips

- Monitor disk usage for uploads and vectorstores
- Set up log rotation to prevent log files from growing too large
- Consider implementing file cleanup for old uploads
- Monitor RAM usage - RAG operations can be memory-intensive
- For production, consider using a proper database instead of in-memory storage
