# AWS Lightsail Test Deployment

This project can be deployed cheaply for a test run on one Ubuntu Lightsail instance.

## Recommended size

- 1 Lightsail Ubuntu instance
- 1 GB or 2 GB RAM plan
- 1 Daphne process
- SQLite database
- In-memory Channels layer

This is fine for a small test with around 50 students if you keep it to one app process on one server.

## 1. Create the server

- Create an Ubuntu Lightsail instance.
- Open ports `80` and `443` in the Lightsail networking panel.
- SSH into the server.

## 2. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git
```

## 3. Upload the project

Clone or copy the project to:

```bash
/home/ubuntu/app
```

## 4. Create a virtual environment

```bash
cd /home/ubuntu/app
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Create the environment file

```bash
cp .env.example .env
```

Edit `.env` and set:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `SQLITE_PATH`

For a simple test server, keep:

- `DJANGO_DEBUG=False`
- `DB_ENGINE=django.db.backends.sqlite3`
- `CHANNEL_LAYER_BACKEND=memory`

## 6. Prepare Django

```bash
source /home/ubuntu/app/venv/bin/activate
cd /home/ubuntu/app
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_data
```

## 7. Configure Daphne service

Copy the example service:

```bash
sudo cp deploy/daphne.service.example /etc/systemd/system/quran-game.service
```

Then start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable quran-game
sudo systemctl start quran-game
sudo systemctl status quran-game
```

## 8. Configure Nginx

Copy the example config:

```bash
sudo cp deploy/nginx-quran-game.example /etc/nginx/sites-available/quran-game
sudo ln -s /etc/nginx/sites-available/quran-game /etc/nginx/sites-enabled/quran-game
sudo rm -f /etc/nginx/sites-enabled/default
```

Edit the file and set your real domain name.

Then reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 9. Optional HTTPS

If you have a domain, add SSL with Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

After HTTPS works, you can turn on:

- `DJANGO_SECURE_SSL_REDIRECT=True`

## 10. Important limitation for this test setup

This setup uses:

- SQLite
- in-memory Channels
- one Daphne process

That means:

- good for a small test
- not good for scaling across multiple servers
- not good for multiple Daphne workers

If the test goes well later, upgrade to:

- PostgreSQL
- Redis
- either a larger EC2/Lightsail setup or ECS
