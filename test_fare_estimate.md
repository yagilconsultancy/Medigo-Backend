# Fare Estimate API - Multiple Ride Types Support

## Overview
The fare estimate endpoint now supports returning estimates for **all ride types** in a single request by setting `ride_type: "all"`.

## Changes Made

### 1. New Response Schemas

Added two new schemas in `services/payment-service/app/schemas/rate_card.py`:

- **`RiderFareEstimateItem`**: Represents a single fare estimate with service type info
- **`RiderFareEstimateArrayResponse`**: Container for multiple estimates with shared distance/duration data

### 2. Updated Endpoint

Modified `/fare-estimate` endpoint in `services/payment-service/app/api/v1/fare_estimate_endpoints.py`:
- Accepts `ride_type: "all"` in the request
- Returns array of estimates for all active service types when "all" is specified
- Returns single estimate when specific ride type is provided (backward compatible)

## API Usage

### Single Ride Type Estimate (Existing)

**Request:**
```json
POST /payments/fare-estimate
{
  "pickup_address": "123 Main St, Toronto, ON",
  "destination_address": "456 King St, Toronto, ON",
  "ride_type": "standard",
  "trip_type": "transport_only",
  "trip_structure": "one_way",
  "use_highway_407": false,
  "is_dialysis_trip": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "distance_km": 5.2,
    "distance_miles": 3.23,
    "duration_minutes": 12,
    "base_fare": 12.00,
    "distance_charge": 11.44,
    "total_fare": 28.50,
    "ride_type": "ambulatory",
    "trip_type": "transport_only",
    "currency": "CAD",
    "estimated_at": "2026-04-08T13:52:00Z",
    // ... other fields
  }
}
```

### All Ride Types Estimate (NEW ✨)

**Request:**
```json
POST /payments/fare-estimate
{
  "pickup_address": "123 Main St, Toronto, ON",
  "destination_address": "456 King St, Toronto, ON",
  "ride_type": "all",
  "trip_type": "transport_only",
  "trip_structure": "one_way",
  "use_highway_407": false,
  "is_dialysis_trip": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "distance_km": 5.2,
    "distance_miles": 3.23,
    "duration_minutes": 12,
    "estimates": [
      {
        "service_type": "standard",
        "display_name": "Standard Vehicle",
        "base_fare": 12.00,
        "distance_charge": 11.44,
        "total_fare": 28.50,
        "ride_type": "ambulatory",
        "trip_type": "transport_only",
        // ... other fields
      },
      {
        "service_type": "wheelchair_wav",
        "display_name": "Wheelchair (WAV)",
        "base_fare": 22.00,
        "distance_charge": 14.56,
        "accessibility_fee": 15.00,
        "total_fare": 56.78,
        "ride_type": "wheelchair",
        "trip_type": "transport_only",
        // ... other fields
      },
      {
        "service_type": "stretcher",
        "display_name": "Stretcher Transport",
        "base_fare": 85.00,
        "distance_charge": 23.40,
        "attendant_fee": 35.00,
        "total_fare": 148.45,
        "ride_type": "stretcher",
        "trip_type": "transport_only",
        // ... other fields
      },
      {
        "service_type": "psw_caregiver",
        "display_name": "PSW / Caregiver",
        "base_fare": 12.00,
        "care_assistant_fee": 32.00,
        "total_fare": 52.30,
        "ride_type": "ambulatory",
        "trip_type": "transport_care_assistant",
        // ... other fields
      },
      {
        "service_type": "hospital_discharge",
        "display_name": "Hospital Discharge",
        "base_fare": 89.00,
        "total_fare": 102.50,
        "ride_type": "ambulatory",
        "trip_type": "hospital_discharge",
        // ... other fields
      }
    ],
    "currency": "CAD",
    "estimated_at": "2026-04-08T13:52:00Z"
  }
}
```

## Service Types Included

When `ride_type: "all"` is used, estimates are generated for all active service types:

1. **standard** - Standard Vehicle
2. **wheelchair_wav** - Wheelchair Accessible Vehicle (WAV)
3. **stretcher** - Stretcher Transport
4. **psw_caregiver** - PSW / Caregiver
5. **hospital_discharge** - Hospital Discharge Package

## Benefits

✅ **Single API call** - Get all estimates in one request
✅ **Comparison shopping** - Users can compare prices across all service types
✅ **Efficient** - Distance calculation happens once, estimates generated for all types
✅ **Backward compatible** - Existing single estimate requests still work

## Implementation Details

- The endpoint checks if `ride_type == "all"`
- If true, fetches all active service types from `service_type_configs` table
- Loops through each service type and generates individual estimates
- Returns `RiderFareEstimateArrayResponse` with all estimates
- If false, returns single `RiderFareEstimateResponse` (existing behavior)

## Notes

- Distance and duration are calculated once and shared across all estimates
- Each estimate respects the specific service type's pricing configuration
- Only active service types are included in the "all" response
- The `service_type` and `display_name` fields identify each estimate in the array
