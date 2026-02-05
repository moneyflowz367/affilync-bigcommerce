# Affilync BigCommerce Integration

BigCommerce app for Affilync affiliate tracking platform. Enables BigCommerce merchants to track affiliate conversions and sync products with Affilync.

## Features

- **OAuth Installation** - Seamless app installation via BigCommerce App Store
- **Webhook Processing** - Real-time order and product sync via webhooks
- **Conversion Tracking** - Automatic affiliate attribution for orders
- **Product Sync** - Sync products to Affilync marketplace
- **Embedded Dashboard** - Analytics and settings within BigCommerce control panel

## Architecture

```
affilync-bigcommerce/
├── backend/app/
│   ├── routes/         # FastAPI routes
│   │   ├── oauth.py    # OAuth flow handlers
│   │   ├── webhooks.py # Webhook processors
│   │   └── api.py      # Frontend API endpoints
│   ├── services/       # Business logic
│   │   ├── store_service.py      # Store management
│   │   ├── bigcommerce_client.py # BC API client
│   │   ├── conversion_service.py # Conversion tracking
│   │   └── product_sync.py       # Product sync
│   ├── models/         # SQLAlchemy models
│   ├── middleware/     # HMAC verification
│   └── utils/          # Encryption, attribution
├── frontend/src/
│   ├── pages/          # Dashboard, Products, Analytics, Settings
│   ├── hooks/          # useBigCommerceFetch
│   └── components/     # Layout, UI components
└── render.yaml         # Deployment config
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL database
- Redis instance
- BigCommerce Partner account

### Environment Variables

```env
# BigCommerce OAuth
BIGCOMMERCE_CLIENT_ID=your_client_id
BIGCOMMERCE_CLIENT_SECRET=your_client_secret
BIGCOMMERCE_APP_ID=your_app_id

# Affilync API
AFFILYNC_API_URL=https://api.affilync.com
AFFILYNC_API_KEY=your_api_key

# Database
DATABASE_URL=postgresql://user:pass@host/dbname

# Redis
REDIS_URL=redis://localhost:6379

# Security
ENCRYPTION_KEY=your_encryption_key
JWT_SECRET_KEY=your_jwt_secret

# App URLs
APP_URL=https://bigcommerce.affilync.com
```

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m app.main

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### BigCommerce App Configuration

1. Create app in BigCommerce Partner Portal
2. Set OAuth callback URL: `https://bigcommerce.affilync.com/oauth/callback`
3. Set Load URL: `https://bigcommerce.affilync.com/oauth/load`
4. Set Uninstall URL: `https://bigcommerce.affilync.com/oauth/uninstall`
5. Required scopes:
   - `store_v2_default`
   - `store_v2_orders`
   - `store_v2_products`
   - `store_webhooks_manage`

## Webhooks

The app registers and handles these BigCommerce webhooks:

| Scope | Handler |
|-------|---------|
| `store/order/created` | Log order creation |
| `store/order/updated` | Handle order updates |
| `store/order/statusUpdated` | Track conversions |
| `store/product/created` | Sync new products |
| `store/product/updated` | Update products |
| `store/product/deleted` | Remove products |
| `store/app/uninstalled` | Clean up on uninstall |

## API Endpoints

### OAuth
- `GET /oauth/auth` - Start OAuth flow
- `GET /oauth/callback` - OAuth callback
- `GET /oauth/load` - Load app in control panel
- `GET /oauth/uninstall` - Uninstall callback

### Webhooks
- `POST /webhooks/bigcommerce` - Webhook handler

### API
- `GET /api/store` - Get store info
- `POST /api/store/connect` - Connect to Affilync brand
- `POST /api/store/disconnect` - Disconnect from brand
- `PUT /api/store/settings` - Update settings
- `GET /api/products` - List products
- `POST /api/products/sync` - Trigger full sync
- `GET /api/analytics` - Get analytics overview

## Deployment

### Render.com

1. Connect repository to Render
2. Use Blueprint (render.yaml)
3. Configure environment variables
4. Deploy

### Manual

```bash
# Build frontend
cd frontend && npm run build

# Run backend
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8006
```

## Security

- Webhook signatures verified via HMAC-SHA256
- Access tokens encrypted with Fernet (PBKDF2 key derivation)
- JWT session tokens for OAuth callbacks
- Rate limiting on API endpoints

## License

MIT License - see LICENSE file for details.
