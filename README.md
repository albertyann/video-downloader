# Video Downloader Web

A modern web-based video downloader built with Vue 3 + Tailwind CSS + FastAPI.

## Architecture

```
video-downloader-web/
├── backend/           # FastAPI Python backend
│   ├── app/
│   │   ├── api/      # API routes
│   │   ├── core/     # Configuration
│   │   ├── models/   # Database models & schemas
│   │   └── services/ # Business logic
│   ├── main.py       # FastAPI entry point
│   └── requirements.txt
│
└── frontend/         # Vue 3 + Tailwind CSS frontend
    ├── src/
    │   ├── components/  # Vue components
    │   ├── utils/       # API client & utilities
    │   ├── App.vue      # Main app component
    │   └── main.js      # Entry point
    └── package.json
```

## Features

- 🎨 **Modern Dark UI** - Beautiful interface with Tailwind CSS
- 🌐 **Domain-specific Proxy** - Configure proxy for specific domains
- 📊 **Quality Selection** - Choose from available video qualities
- 📈 **Real-time Progress** - WebSocket-based download progress
- 📜 **Download History** - SQLite-based history with search
- ⚙️ **Web-based Settings** - Configure everything in the browser

## Quick Start

### Option 1: Docker Compose (Recommended)

The easiest way to run the entire application:

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Access the application:
- Frontend: http://localhost
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

Downloaded videos will be saved to `./downloads/` directory.

### Option 2: Manual Setup

#### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will run on http://localhost:8000

Or use production mode (without reload):
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will run on http://localhost:5173

## API Endpoints

- `POST /api/video/info` - Get video information
- `POST /api/video/download` - Start download
- `GET /api/downloads` - Get download history
- `GET /api/downloads/search` - Search downloads
- `GET /api/settings` - Get settings
- `PUT /api/settings` - Update settings
- `WS /api/ws/download/{id}` - WebSocket for progress

## Configuration

Edit settings in the web UI or modify `backend/app/core/config.py`:

- `DOWNLOAD_PATH` - Where videos are saved
- `PROXY_URL` - HTTP/SOCKS5 proxy
- `PROXY_DOMAINS` - Domains that use proxy

## Requirements

- Python 3.8+
- Node.js 16+
- Linux/macOS/Windows

## License

Open source - feel free to use and modify.
