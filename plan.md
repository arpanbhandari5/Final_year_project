# Mobile App Integration Plan — Prayash

## Executive Summary

This plan outlines how to extend the Prayash career intelligence platform from a Flask web app to include a native mobile experience. The recommendation is a **Progressive Web App (PWA)** as the primary approach, with an optional **React Native** frontend for a native app store presence.

---

## Current Architecture

```
┌──────────────────────────────────────────────────┐
│                   Flask Backend                   │
│  app.py → routes → risk_assessor → ML pipeline   │
│  storage.py → SQLAlchemy → SQLite                │
│  Templates (Jinja2) → HTML/CSS/JS               │
└──────────────────────────────────────────────────┘
```

**Key API Endpoints (already exist):**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/upload` | POST | Resume analysis |
| `/api/analyze` | POST | Alias for upload |
| `/api/feedback` | POST | User feedback |
| `/login` | POST | Authentication |
| `/signup` | POST | Registration |
| `/healthz` | GET | Health check |

---

## Approach Comparison

| Criteria | PWA | React Native | Flutter | Flet (Python) |
|----------|-----|-------------|---------|---------------|
| **Dev Effort** | ⭐ Low | ⭐⭐⭐ High | ⭐⭐⭐ High | ⭐⭐ Medium |
| **Native Feel** | Good | Excellent | Excellent | Good |
| **Offline Support** | Via Service Worker | Full | Full | Limited |
| **App Store** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Code Reuse** | ~95% (existing) | ~30% (API only) | ~30% (API only) | ~70% (Python) |
| **Timeline Risk** | Low | High | High | Medium |
| **File Upload** | ✅ Native | ✅ Native | ✅ Native | ✅ Native |
| **Push Notifications** | ✅ Android / ⚠️ iOS | ✅ Full | ✅ Full | ⚠️ Limited |
| **ML Integration** | Server-side | Server-side | Server-side | Server-side |

---

## Recommended Approach: PWA + Optional React Native

### Phase 1: PWA Conversion (Week 1-2) — PRIMARY

Convert the existing Flask web app into an installable PWA with offline support.

#### 1.1 Add PWA Manifest
Create `static/manifest.json`:
```json
{
  "name": "Prayash — Career Intelligence",
  "short_name": "Prayash",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f0a1a",
  "theme_color": "#7c3aed",
  "icons": [...]
}
```

#### 1.2 Add Service Worker
Create `static/sw.js` for offline caching:
- Cache static assets (CSS, JS, fonts)
- Network-first strategy for API calls
- Offline fallback page

#### 1.3 Update Base Template
Add to `templates/base.html`:
```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#7c3aed">
<meta name="apple-mobile-web-app-capable" content="yes">
```

#### 1.4 Responsive UI Improvements
- Mobile-friendly hamburger menu
- Touch-friendly buttons and form elements
- Optimized score ring for small screens
- Bottom navigation bar for mobile

#### 1.5 File Upload on Mobile
- Camera capture option for resume photos
- Improved drag-and-drop with touch events
- File picker integration

---

### Phase 2: API Refactoring (Week 2-3) — OPTIONAL

Refactor Flask routes into a clean REST API for React Native consumption.

#### 2.1 Create API Blueprint
```python
# api.py
from flask import Blueprint, jsonify, request

api = Blueprint('api', __name__, url_prefix='/api/v1')

@api.route('/auth/login', methods=['POST'])
def login(): ...

@api.route('/auth/signup', methods=['POST'])
def signup(): ...

@api.route('/analyze', methods=['POST'])
def analyze(): ...

@api.route('/feedback', methods=['POST'])
def feedback(): ...

@api.route('/health', methods=['GET'])
def health(): ...
```

#### 2.2 Add JWT Authentication
- Replace session-based auth with JWT tokens for mobile
- Add token refresh endpoint
- Store tokens securely on device

#### 2.3 Add CORS Support
```python
from flask_cors import CORS
CORS(app, origins=["http://localhost:3000"])
```

---

### Phase 3: React Native App (Week 3-6) — OPTIONAL

Build a native mobile app that consumes the refactored API.

#### 3.1 Project Setup
```bash
npx react-native init PrayashMobile
cd PrayashMobile
npm install @react-navigation/native axios react-native-paper
```

#### 3.2 Screen Structure
```
App
├── AuthStack
│   ├── LoginScreen
│   └── SignupScreen
├── MainTabs
│   ├── HomeScreen (landing)
│   ├── AnalyzeScreen (upload/paste resume)
│   ├── ResultsScreen (risk, roles, roadmap)
│   └── ProfileScreen
└── ModalStack
    └── FeedbackScreen
```

#### 3.3 Key Components
- **ResumeUpload**: Camera capture + file picker + text paste
- **RiskGauge**: Animated circular gauge (react-native-svg)
- **RoleMatchCards**: Horizontal scroll of matched roles
- **LearningRoadmap**: Timeline view of recommended courses
- **RIASECProfile**: Radar/spider chart visualization

#### 3.4 Native Features
- **Biometric Auth**: Face ID / fingerprint login
- **Push Notifications**: Learning reminder alerts
- **Offline Cache**: Store last analysis results
- **Share**: Share results to social media

---

## Implementation Steps

### Step 1: PWA Foundation (Do First)
- [ ] Create `static/manifest.json` with app icons
- [ ] Create `static/sw.js` with caching strategy
- [ ] Update `templates/base.html` with PWA meta tags
- [ ] Register service worker in `static/script.js`
- [ ] Test installability on Chrome DevTools

### Step 2: Mobile UI Polish
- [ ] Add responsive breakpoints to `static/styles.css`
- [ ] Create mobile navigation (hamburger menu or bottom tabs)
- [ ] Optimize upload zone for touch devices
- [ ] Add touch gestures for swipeable cards
- [ ] Test on real mobile devices

### Step 3: API Refactoring (If React Native Needed)
- [ ] Create `api.py` Blueprint with clean endpoints
- [ ] Add JWT authentication (`flask-jwt-extended`)
- [ ] Add CORS support
- [ ] Write API documentation (OpenAPI/Swagger)
- [ ] Test with Postman/curl

### Step 4: React Native App (If App Store Needed)
- [ ] Initialize React Native project
- [ ] Set up navigation and auth flow
- [ ] Build upload screen with camera integration
- [ ] Build results dashboard with charts
- [ ] Add push notifications
- [ ] Build and test on iOS/Android

---

## File Changes Required

### PWA (Minimal Changes)
| File | Change |
|------|--------|
| `static/manifest.json` | **NEW** — PWA manifest |
| `static/sw.js` | **NEW** — Service worker |
| `static/icons/` | **NEW** — App icons (192x192, 512x512) |
| `templates/base.html` | Add manifest link + meta tags |
| `static/script.js` | Register service worker |
| `static/styles.css` | Add mobile responsive rules |
| `app.py` | Add manifest route, CORS headers |

### React Native (New Project)
| File | Purpose |
|------|---------|
| `mobile/App.js` | Root component |
| `mobile/src/screens/` | Screen components |
| `mobile/src/components/` | Reusable UI components |
| `mobile/src/services/api.js` | API client |
| `mobile/src/contexts/Auth.js` | Auth state management |
| `mobile/package.json` | Dependencies |

---

## Environment Variables (New)

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | auto-generated | JWT token signing key |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `API_VERSION` | `v1` | API version prefix |

---

## Testing Strategy

1. **PWA Testing**
   - Chrome DevTools → Application tab → Manifest & Service Worker
   - Lighthouse PWA audit (target: 90+ score)
   - Test on real Android/iOS devices

2. **API Testing**
   - Unit tests for each endpoint
   - Postman collection for manual testing
   - Load testing with `locust` or `k6`

3. **React Native Testing**
   - Jest unit tests for components
   - Detox E2E tests for critical flows
   - Test on iOS Simulator + Android Emulator

---

## Timeline Estimate

| Phase | Duration | Priority |
|-------|----------|----------|
| PWA Conversion | 1-2 weeks | **HIGH** — Do first |
| Mobile UI Polish | 1 week | **HIGH** — Part of PWA |
| API Refactoring | 1 week | MEDIUM — Only if React Native needed |
| React Native App | 3-4 weeks | LOW — Only if app store required |

**Total: 2-8 weeks depending on scope**

---

## Recommendation

**Start with PWA.** It gives you 90% of the mobile experience with 20% of the effort. The existing Flask app is already well-structured for this — you just need:

1. A `manifest.json` file
2. A service worker for caching
3. Some CSS responsive tweaks

Only pursue React Native if you specifically need:
- App Store / Play Store presence
- Native device features (camera API, biometrics, push notifications)
- Offline-first capability

The ML pipeline runs entirely server-side, so both approaches work equally well for the core functionality.
