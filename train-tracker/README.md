# Train Tracker India

A mobile application for tracking Indian Railways trains in real-time, calculating ETA to destinations, and viewing complete route information with all intermediate stops.

## Features

- **Train Search** - Search trains by number or name
- **Live Tracking** - Real-time running status with delay information
- **ETA Calculation** - Estimated time of arrival to any station on the route, adjusted for delays
- **Route Display** - Visual timeline of all stations with arrival/departure times
- **Station-to-Station** - Find all trains between any two stations
- **Journey Summary** - Distance, duration, intermediate stops, and running days

## Architecture

```
train-tracker/
├── backend/                 # Python Flask API server
│   ├── app.py              # Flask routes and API endpoints
│   ├── models/             # Data models (Station, TrainRoute, LiveStatus, ETA)
│   ├── services/           # Business logic
│   │   ├── train_service.py    # Train data fetching, search, live status
│   │   └── eta_service.py      # ETA calculation engine
│   └── data/               # Sample train data (10 popular trains)
└── mobile/                  # React Native (Expo) mobile app
    ├── App.js              # Navigation and app entry point
    ├── screens/            # App screens
    │   ├── HomeScreen.js           # Search and popular trains
    │   ├── TrainDetailScreen.js    # Live status + schedule timeline
    │   ├── ETAScreen.js            # ETA with countdown and route
    │   └── StationSearchScreen.js  # Find trains between stations
    ├── components/         # Reusable UI components
    │   ├── StationTimeline.js  # Vertical route timeline
    │   ├── TrainCard.js        # Train search result card
    │   └── ETACard.js          # ETA display with countdown
    ├── services/           # API client
    └── utils/              # Colors, formatting helpers
```

## Backend Setup

```bash
cd train-tracker/backend
pip install -r requirements.txt
python app.py
```

The API server starts on `http://localhost:5000`.

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/trains/search?q=rajdhani` | Search trains by name/number |
| `GET /api/trains/12301/route` | Get full route and schedule |
| `GET /api/trains/12301/live` | Get live running status |
| `GET /api/trains/12301/eta?station=HWH` | Calculate ETA to station |
| `GET /api/trains/12301/journey?from=NDLS&to=CNB` | Journey summary |
| `GET /api/stations/search?q=delhi` | Search stations |
| `GET /api/trains/between?from=NDLS&to=BPL` | Trains between stations |

## Mobile App Setup

```bash
cd train-tracker/mobile
npm install
npx expo start
```

Scan the QR code with the Expo Go app on your phone.

### Configure API URL

Edit `mobile/services/api.js` and update `BASE_URL` to point to your backend:
- Local development: `http://localhost:5000/api`
- Device testing: `http://<your-ip>:5000/api`

## Sample Trains Included

| Train | Route |
|---|---|
| 12301 Howrah Rajdhani | New Delhi → Howrah |
| 12951 Mumbai Rajdhani | Mumbai Central → New Delhi |
| 12611 Chennai Rajdhani | New Delhi → Chennai |
| 12431 TVC Rajdhani | New Delhi → Thiruvananthapuram |
| 12002 Bhopal Shatabdi | New Delhi → Bhopal |
| 12622 Tamil Nadu Express | New Delhi → Chennai |
| 12723 Telangana Express | New Delhi → Secunderabad |
| 12627 Karnataka Express | New Delhi → Bengaluru |
| 12259 Sealdah Duronto | New Delhi → Sealdah |
| 16526 Kanyakumari Express | Bengaluru → Kanyakumari |

## How It Works

1. **Search** a train by number (e.g., "12301") or name (e.g., "Rajdhani")
2. **View** live running status with current position and delay
3. **Tap** any station to see ETA with remaining distance, stops, and expected arrival time
4. **Track** the train's position on the route timeline (green = passed, orange = current, grey = upcoming)

The app uses Indian Railways data with a built-in simulation engine for demo mode when live APIs are unavailable.
