from pydantic import BaseModel


class GeocodeResponse(BaseModel):
    latitude: float
    longitude: float
    formatted_address: str
    place_id: str | None = None
    source: str = "google"


class ReverseGeocodeResponse(BaseModel):
    formatted_address: str
    place_id: str | None = None
    latitude: float
    longitude: float


class AutocompleteResult(BaseModel):
    description: str
    place_id: str
    main_text: str
    secondary_text: str


class DistanceResponse(BaseModel):
    distance_miles: float
    distance_km: float
    duration_minutes: float
    duration_text: str
    distance_text: str
    source: str = "google"


class PlaceDetailsResponse(BaseModel):
    name: str
    formatted_address: str
    place_id: str
    latitude: float | None = None
    longitude: float | None = None
    types: list[str] = []


class ServiceAreaCheckResponse(BaseModel):
    in_service_area: bool
    area_name: str | None = None
    area_id: str | None = None
