# Location API Setup Guide

This application uses the **CountryStateCity API** to provide comprehensive location data including:
- 247+ countries
- 5,000+ states/provinces  
- 150,000+ cities worldwide

## Getting Started

### 1. Get Free API Key

1. Visit: https://countrystatecity.in/
2. Sign up for a free account
3. Get your API key from the dashboard
4. Free tier includes: **3,000 requests/month**

### 2. Set Environment Variable

**Windows (CMD):**
```cmd
set COUNTRY_STATE_CITY_API_KEY=your_api_key_here
```

**Windows (PowerShell):**
```powershell
$env:COUNTRY_STATE_CITY_API_KEY="your_api_key_here"
```

**Linux/Mac:**
```bash
export COUNTRY_STATE_CITY_API_KEY=your_api_key_here
```

**Or add to `.env` file:**
```
COUNTRY_STATE_CITY_API_KEY=your_api_key_here
```

### 3. Populate Database (Optional)

To populate your database with comprehensive location data:

```bash
cd backend
python -m scripts.populate_locations_from_api
```

This will:
- Fetch all countries from the API
- Fetch all states for each country
- Fetch all cities for each state
- Store everything in your database

**Note:** This process may take 10-30 minutes depending on your internet connection and API rate limits.

## API Endpoints

### Get Countries
```
GET /api/v1/locations/countries?use_api=true
```
Returns comprehensive country data including ISO codes, currency, region, etc.

### Get States
```
GET /api/v1/locations/states?country_id=1&use_api=true
GET /api/v1/locations/countries/{country_code}/states?use_api=true
```
Returns all states/provinces for a country.

### Get Cities
```
GET /api/v1/locations/cities?state_id=1&use_api=true
GET /api/v1/locations/countries/{country_code}/states/{state_code}/cities?use_api=true
```
Returns all cities for a state.

## Features

### Automatic Fallback
- If API key is not set → Uses database
- If API request fails → Falls back to database
- If API rate limit exceeded → Falls back to database

### Comprehensive Data
When using the API (`use_api=true`), you get:
- ISO codes (ISO2, ISO3)
- Phone codes
- Currency information
- Geographic coordinates (latitude/longitude)
- Region and subregion data
- Emoji flags

### Database Mode
When using database mode (`use_api=false` or no API key):
- Uses your existing database records
- Faster response times
- No external API dependency

## Usage in Frontend

The frontend automatically tries to use the API first, then falls back to the database:

```javascript
// Automatically uses API if available
const response = await fetch('http://localhost:8000/api/v1/locations/countries?use_api=true')
```

## Rate Limits

**Free Tier:**
- 3,000 requests/month
- Suitable for development and small applications

**Paid Tiers:**
- Higher limits available
- Visit https://countrystatecity.in/ for pricing

## Troubleshooting

### API Key Not Working
- Verify the key is set correctly: `echo $COUNTRY_STATE_CITY_API_KEY`
- Check for extra spaces or quotes
- Ensure the key is active in your account

### No Data Returned
- Check API key is valid
- Verify internet connection
- Check API status: https://countrystatecity.in/
- The system will automatically fall back to database

### Slow Performance
- Use `use_api=false` to use database only
- Populate database first, then use database mode
- Cache API responses in your application

## Alternative APIs

If you prefer a different location API, you can modify:
- `backend/app/api/v1/endpoints/locations.py` - API integration
- `backend/scripts/populate_locations_from_api.py` - Database population script

Other recommended APIs:
- GeoNames API
- REST Countries API
- OpenStreetMap Nominatim



