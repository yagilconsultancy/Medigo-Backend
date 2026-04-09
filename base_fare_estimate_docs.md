# Base Fare Estimate API

## Overview
A simplified fare estimation endpoint that calculates base fares for **all ride types** based on distance only. This is faster and simpler than the full fare estimate, perfect for showing quick price comparisons to riders.

## Endpoint

```
POST /payments/base-fare-estimate
```

**Public Endpoint** - No authentication required

## What's Included

This base fare estimate includes:
- ✅ Base fare for each vehicle type
- ✅ Distance charge (distance × per_km_rate)
- ✅ Booking fee
- ✅ Accessibility fee (wheelchair only)
- ✅ Attendant fee (stretcher only)
- ✅ Care assistant fee (PSW/caregiver only)

## What's NOT Included

This does NOT include:
- ❌ Time-based surcharges (peak hours, night, weekend)
- ❌ Weather surcharges
- ❌ Holiday surcharges
- ❌ Highway 407 tolls
- ❌ Wait time charges
- ❌ Real-time distance calculation (uses provided distance)

## Request

### Schema

```json
{
  "distance_km": 5.2
}
```

### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `distance_km` | float | Yes | Distance in kilometers (≥ 0) |

### Example Request

```bash
curl -X POST http://localhost:8000/payments/base-fare-estimate \
  -H "Content-Type: application/json" \
  -d '{"distance_km": 5.2}'
```

## Response

### Schema

```json
{
  "success": true,
  "data": {
    "distance_km": 5.2,
    "estimates": [
      {
        "service_type": "standard",
        "display_name": "Standard Vehicle",
        "base_fare": 12.00,
        "distance_charge": 11.44,
        "booking_fee": 3.50,
        "accessibility_fee": 0,
        "attendant_fee": 0,
        "care_assistant_fee": 0,
        "estimated_total": 26.94,
        "description": "Comfortable transport for mobile patients."
      },
      {
        "service_type": "wheelchair_wav",
        "display_name": "Wheelchair (WAV)",
        "base_fare": 22.00,
        "distance_charge": 14.56,
        "booking_fee": 3.50,
        "accessibility_fee": 15.00,
        "attendant_fee": 0,
        "care_assistant_fee": 0,
        "estimated_total": 55.06,
        "description": "Safe and secure transport for wheelchair users."
      },
      {
        "service_type": "stretcher",
        "display_name": "Stretcher Transport",
        "base_fare": 85.00,
        "distance_charge": 23.40,
        "booking_fee": 5.00,
        "accessibility_fee": 0,
        "attendant_fee": 35.00,
        "care_assistant_fee": 0,
        "estimated_total": 148.40,
        "description": "Full medical transport for patients unable to sit upright."
      },
      {
        "service_type": "psw_caregiver",
        "display_name": "PSW / Caregiver",
        "base_fare": 12.00,
        "distance_charge": 11.44,
        "booking_fee": 0,
        "accessibility_fee": 0,
        "attendant_fee": 0,
        "care_assistant_fee": 32.00,
        "estimated_total": 55.44,
        "description": "Transport with professional caregiver assistance."
      },
      {
        "service_type": "hospital_discharge",
        "display_name": "Hospital Discharge",
        "base_fare": 0,
        "distance_charge": 0,
        "booking_fee": 0,
        "accessibility_fee": 0,
        "attendant_fee": 0,
        "care_assistant_fee": 0,
        "estimated_total": 89.00,
        "description": "Complete hospital discharge package with assistance."
      }
    ],
    "currency": "CAD",
    "note": "This is a base fare estimate. Final price may vary based on time of day, weather conditions, and other factors.",
    "estimated_at": "2026-04-09T07:19:00Z"
  }
}
```

### Response Fields

**Root Level:**
| Field | Type | Description |
|-------|------|-------------|
| `distance_km` | float | Distance in kilometers used for calculation |
| `estimates` | array | Array of estimates for all active ride types |
| `currency` | string | Currency code (CAD) |
| `note` | string | Important note about estimate limitations |
| `estimated_at` | datetime | Timestamp of estimate generation |

**Estimate Item:**
| Field | Type | Description |
|-------|------|-------------|
| `service_type` | string | Service type identifier (e.g., "standard", "wheelchair_wav") |
| `display_name` | string | Human-readable service name |
| `base_fare` | float | Base fare for the service type |
| `distance_charge` | float | Charge based on distance (distance_km × per_km_rate) |
| `booking_fee` | float | Booking fee |
| `accessibility_fee` | float | Accessibility fee (wheelchair only) |
| `attendant_fee` | float | Medical attendant fee (stretcher only) |
| `care_assistant_fee` | float | Caregiver hourly rate (PSW only) |
| `estimated_total` | float | Total estimated fare |
| `description` | string | Description of the service |

## Pricing Formula

### Standard, Wheelchair, Stretcher
```
estimated_total = base_fare + (distance_km × per_km_rate) + booking_fee + fees
```

Where `fees` includes:
- Wheelchair: `accessibility_fee` (typically $15)
- Stretcher: `attendant_fee` (typically $35)

### PSW / Caregiver
```
estimated_total = base_fare + (distance_km × per_km_rate) + hourly_rate
```

### Hospital Discharge
```
estimated_total = fixed_package_price ($89)
```

## Example Pricing (5.2 km)

| Service Type | Base Fare | Distance | Fees | Total |
|--------------|-----------|----------|------|-------|
| Standard Vehicle | $12.00 | $11.44 | $3.50 | **$26.94** |
| Wheelchair (WAV) | $22.00 | $14.56 | $18.50 | **$55.06** |
| Stretcher Transport | $85.00 | $23.40 | $40.00 | **$148.40** |
| PSW / Caregiver | $12.00 | $11.44 | $32.00 | **$55.44** |
| Hospital Discharge | - | - | - | **$89.00** |

## Use Cases

### 1. Quick Price Comparison
Show all ride types with base prices so users can compare options quickly.

### 2. Initial Booking Flow
Display estimated prices before users enter detailed trip information.

### 3. Mobile App Integration
Fast, lightweight endpoint for mobile apps to show instant pricing.

### 4. Distance-Based Quotes
When you have the distance but don't need time-specific pricing.

## Comparison with Full Fare Estimate

| Feature | Base Fare Estimate | Full Fare Estimate |
|---------|-------------------|-------------------|
| **Speed** | ⚡ Very Fast | Slower (geocoding + calculations) |
| **Input Required** | Just distance | Full trip details + addresses |
| **Surcharges** | ❌ None | ✅ All (time, weather, holiday) |
| **Toll Charges** | ❌ No | ✅ Highway 407 |
| **Distance Calculation** | User provides | ✅ Google Maps API |
| **Wait Time** | ❌ No | ✅ Yes |
| **Accuracy** | Base estimate only | High accuracy |
| **Use Case** | Quick comparison | Final booking price |

## Integration Example

```typescript
// React/TypeScript example
async function getBaseFareEstimates(distanceKm: number) {
  const response = await fetch('/payments/base-fare-estimate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ distance_km: distanceKm })
  });

  const result = await response.json();
  return result.data.estimates;
}

// Usage
const estimates = await getBaseFareEstimates(5.2);

estimates.forEach(estimate => {
  console.log(`${estimate.display_name}: $${estimate.estimated_total}`);
});

// Output:
// Standard Vehicle: $26.94
// Wheelchair (WAV): $55.06
// Stretcher Transport: $148.40
// PSW / Caregiver: $55.44
// Hospital Discharge: $89.00
```

## Important Notes

1. **Not for Final Pricing**: This is a base estimate only. Always use the full fare estimate endpoint (`/fare-estimate`) for accurate final pricing before booking.

2. **No Time Factors**: Prices don't account for time of day, day of week, or seasonal factors.

3. **No Weather**: Weather surcharges are not included.

4. **Returns All Types**: Always returns estimates for all active service types - cannot filter to specific types.

5. **Distance-Based Only**: Pricing is purely based on distance. Actual trips may vary due to traffic, route changes, etc.

## API Gateway Route

The endpoint is accessible through the API gateway at:
```
POST /payments/base-fare-estimate
```

No authentication required - this is a public endpoint.
