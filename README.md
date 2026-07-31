# Intent Hub

Minimal Agent router protected by the fixed API code `telestar`. Agents are read from the fixed upstream API, synchronized to the existing Qdrant vector format, and queried with a fixed `0.8` threshold.

## Run

```powershell
cd intent-hub-backend
pip install -e .[dev]
python run.py
```

```powershell
cd intent-hub-frontend
npm install
npm run dev
```

The web UI sends the fixed API code automatically and contains Agent synchronization/listing, route testing, diagnostics, and settings.

See [USER_GUIDE.md](USER_GUIDE.md) and [docs/API.md](docs/API.md).
