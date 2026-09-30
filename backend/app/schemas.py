"""Pydantic v2 models matching the API contract exactly."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal["CRITICAL", "WARNING", "GREEN"]


class InventoryItemOut(BaseModel):
    medicine_name: str
    current_stock: int
    history: list[float]
    projected_demand_7d: float
    avg_daily_demand: float
    days_to_stockout: float
    status: Status
    suggested_source_id: str | None = None
    suggested_source_name: str | None = None


class PhcOut(BaseModel):
    phc_id: str
    phc_name: str
    district: str
    state: str
    lat: float
    lng: float
    beds_available: int
    beds_total: int
    doctors_present: int
    doctors_total: int
    inventory: list[InventoryItemOut]


class SummaryOut(BaseModel):
    total_phcs: int
    active_stockout_alerts: int
    beds_available: int
    beds_total: int
    bed_availability_ratio: float
    active_ai_transfers: int
    ai_mode: Literal["gemini", "mock"]


class NetworkStatus(BaseModel):
    summary: SummaryOut
    phcs: list[PhcOut]


class VoiceReportRequest(BaseModel):
    audio_transcript: str = Field(min_length=1, max_length=3000)
    phc_id: str
    language: str = "en-IN"


class Extracted(BaseModel):
    patient_count: int | None = None
    paracetamol_stock: int | None = None
    doctor_present: bool | None = None
    emergency_notes: str = ""


class VoiceReportResponse(BaseModel):
    source: Literal["gemini", "mock"]
    fallback_reason: str | None = None
    phc_id: str
    extracted: Extracted
    applied_to_network: bool = True


class RedistributionRequest(BaseModel):
    source_phc_id: str
    target_phc_id: str
    item_name: str


class Brief(BaseModel):
    transfer_quantity: int
    transport_mode: str
    route_priority: str
    emergency_justification: str
    estimated_travel_time: str


class RedistributionResponse(BaseModel):
    source: Literal["gemini", "mock"]
    fallback_reason: str | None = None
    facts: dict
    brief: Brief


class TransferOut(BaseModel):
    id: str
    item: str
    source_phc_id: str
    source_phc_name: str | None = None
    target_phc_id: str
    target_phc_name: str | None = None
    quantity: int
    brief: dict
    source: str
    created_at: str | None = None


class NearbyPhc(BaseModel):
    phc_id: str
    name: str
    district: str
    state: str
    distance_km: float
    beds_available: int
    beds_total: int
    doctors_present: int
    doctors_total: int
    maps_url: str

# ---------------- Chat ----------------
Availability = Literal["IN_STOCK", "LOW", "OUT"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=2000)


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list)
    location: LatLng | None = None
    district_hint: str | None = Field(default=None, max_length=60)

    @field_validator("history")
    @classmethod
    def keep_last_10(cls, v: list[ChatTurn]) -> list[ChatTurn]:
        return v[-10:]  # truncate instead of rejecting


class MedicineAvailability(BaseModel):
    name: str
    availability: Availability


class PhcCard(BaseModel):
    type: Literal["phc"] = "phc"
    phc_id: str
    name: str
    district: str
    distance_km: float | None = None
    beds_available: int
    beds_total: int
    doctors_present: int
    doctors_total: int
    maps_url: str
    medicines: list[MedicineAvailability] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    emergency: bool = False
    source: Literal["gemini", "mock"]
    data_as_of: str  # ISO 8601 UTC
    cards: list[PhcCard] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)