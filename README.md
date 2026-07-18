# Intent Hub

Minimal authenticated Agent router. Agents are read from the fixed upstream API, synchronized to the existing Qdrant vector format, and queried with a fixed `0.8` threshold.

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

The web UI contains login, Agent synchronization/listing, route testing, and the only writable setting: Qdrant collection name.

See [USER_GUIDE.md](USER_GUIDE.md) and [docs/API.md](docs/API.md).

