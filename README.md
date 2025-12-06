# 🌿 Black Tie Orders

Production Order System for Black Tie Cannabis

Automatically reconciles POS inventory (Flowhub API) against Production inventory (Google Sheets) and generates weekly order emails.

## Features

- **Flowhub API Integration**: Pull inventory directly from POS - no CSV exports needed!
- **Auto-Detection**: Automatically discovers new sheet tabs in Google Sheets
- **Fuzzy Matching**: Matches products even with naming differences
- **Learning**: Remembers your match confirmations for future use
- **Order Generation**: Creates prioritized order lists
- **Email Notifications**: Sends formatted orders to production team
- **CSV Fallback**: Upload CSV if API is unavailable

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/blacktie-orders.git
cd blacktie-orders
npm install
```

### 2. Flowhub API (Already Configured)

Your credentials are pre-configured:
- **Endpoint**: `GET https://api.flowhub.co/v0/locations/{locationId}/inventory`
- **Client ID**: `2a114178-f811-4b69-89db-d6ef6ac6e4b4`
- **API Key**: `6365ac53-3186-4df4-bba9-6b41d52e671f`
- **Lewiston ID**: `b9d2a82b-9c98-4f18-95f3-df8843c0cf1e`
- **Greene ID**: `1333c834-871e-4a6b-b2c9-30bfac938233`

### 3. Set Up Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Google Sheets API**
4. Create a Service Account and download JSON key
5. Share your Production Google Sheet with the service account email

### 4. Set Up SendGrid

1. Create a [SendGrid account](https://sendgrid.com/)
2. Create an API key with "Mail Send" permissions
3. Verify sender email (blacktiecannabis@gmail.com)

### 5. Configure Environment Variables

Copy `.env.example` to `.env.local` and fill in values.

### 6. Run Locally

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Deploy to Vercel

See [DEPLOYMENT-GUIDE.md](./DEPLOYMENT-GUIDE.md) for full instructions.

## Usage

### Weekly Order Flow (Now Simplified!)

1. **Monday Morning**: Open the app
2. **Click "Sync from Flowhub"**: Pulls inventory automatically
3. **Review**: Confirm any fuzzy matches flagged for review
4. **Generate**: Preview the order, then send to production
5. **Friday**: Production delivers the order

No more CSV exports! 🎉

### What Gets Ordered

- **Critical (Out of Stock)**: POS quantity = 0
- **Low Stock**: Below threshold (varies by category)
- **New Products**: In production but not at retail location

### Thresholds

| Category | Reorder When Below | Order Quantity |
|----------|-------------------|----------------|
| Shatter | 10g | 28g (1 oz) |
| Badder | 10g | 28g |
| Sugar | 10g | 28g |
| Live Resin | 10g | 28g |
| Full Spec Oil | 20 carts | 50 carts |
| Prerolls | 50 units | 100 units |
| Flower | 100g | 448g (1 lb) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/flowhub-inventory` | GET | Get POS inventory from Flowhub API |
| `/api/inventory` | GET | Get production inventory from Google Sheets |
| `/api/upload-csv` | POST | Parse Flowhub CSV upload (fallback) |
| `/api/reconcile` | POST | Match POS against production inventory |
| `/api/generate-orders` | POST | Generate order and optionally send email |

## Flowhub API Response

The API returns rich data for each product:

```json
{
  "productName": "Blue Dream - 1g",
  "parentProductName": "Blue Dream",
  "category": "Flower",
  "quantity": 45,
  "inventoryUnitOfMeasure": "grams",
  "strainName": "Blue Dream",
  "supplierName": "Black Tie",
  "cannabinoidInformation": [
    {"name": "thc", "upperRange": 22, "unitOfMeasure": "%"}
  ],
  "sku": "h5aPEEmD8L"
}
```

## Project Structure

```
blacktie-orders/
├── api/                      # Python serverless functions
│   ├── flowhub.py           # Flowhub API client
│   ├── flowhub-inventory.py # Flowhub inventory endpoint
│   ├── sheets.py            # Google Sheets integration
│   ├── matcher.py           # Fuzzy matching logic
│   ├── inventory.py         # Production inventory endpoint
│   ├── upload-csv.py        # CSV parsing (fallback)
│   ├── reconcile.py         # Reconciliation endpoint
│   └── generate-orders.py   # Order generation + email
├── app/                      # Next.js frontend
│   ├── page.jsx             # Main app page
│   ├── layout.jsx           # App layout
│   └── globals.css          # Tailwind styles
├── package.json
├── requirements.txt          # Python dependencies
├── vercel.json              # Vercel configuration
└── README.md
```

## Troubleshooting

### Flowhub API 401 Unauthorized

- Verify `clientId` and `key` headers are correct
- Check environment variables in Vercel

### "Permission denied" from Google Sheets

- Make sure the service account email has access to your sheet

### Emails not sending

- Verify your sender email in SendGrid
- Check the API key has "Mail Send" permission

### Products not matching

- Products with <70% similarity won't match automatically
- Confirm matches manually to teach the system

## Support

For issues or questions, contact Nick at blacktiecannabis@gmail.com

---

Built with ❤️ for Black Tie Cannabis
