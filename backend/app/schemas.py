from datetime import date as date_type, datetime
from typing import Literal

from pydantic import BaseModel, Field


class OTPRequest(BaseModel):
    phone: str = Field(pattern=r"^\+?\d{10,13}$")


class OTPVerify(BaseModel):
    phone: str = Field(pattern=r"^\+?\d{10,13}$")
    code: str = Field(min_length=6, max_length=6)
    name: str | None = None
    language: str = "en"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    phone: str
    name: str | None
    language: str
    district: str | None
    state: str | None
    lat: float | None
    lon: float | None
    role: str
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    language: str | None = None
    district: str | None = None
    state: str | None = None
    lat: float | None = None
    lon: float | None = None


class CropOut(BaseModel):
    id: int
    name: str
    local_names: dict
    model_config = {"from_attributes": True}


class MarketOut(BaseModel):
    id: int
    name: str
    district: str | None
    state: str | None
    lat: float | None
    lon: float | None
    model_config = {"from_attributes": True}


class DiseaseOut(BaseModel):
    id: int
    label: str
    name: str
    is_healthy: bool
    symptoms: str
    organic_treatment: str
    chemical_treatment: str
    prevention: str
    model_config = {"from_attributes": True}


class TopPrediction(BaseModel):
    label: str
    confidence: float


class ScanOut(BaseModel):
    id: int
    created_at: datetime
    label: str
    confidence: float
    uncertain: bool
    message: str | None = None
    demo: bool = False
    disease: DiseaseOut | None = None
    top: list[TopPrediction] = []
    disclaimer: str = ("This is automated advice, not a prescription. Confirm with your local "
                       "agriculture officer before applying chemicals.")


class ScanHistoryItem(BaseModel):
    id: int
    created_at: datetime
    predicted_label: str
    confidence: float
    uncertain: bool
    feedback: str | None
    model_config = {"from_attributes": True}


class FeedbackIn(BaseModel):
    correct: bool
    true_label: str | None = None


class PricePoint(BaseModel):
    date: date_type
    modal_price: float
    min_price: float | None = None
    max_price: float | None = None


class ForecastPoint(BaseModel):
    date: date_type
    predicted: float
    lower: float
    upper: float


class ForecastOut(BaseModel):
    crop: str
    market: str
    last_date: date_type
    last_price: float
    method: Literal["ml", "baseline"]
    advice_key: Literal["wait", "sell", "stable"]
    advice: str
    change_pct: float
    points: list[ForecastPoint]
    disclaimer: str = "Forecasts are estimates and can be wrong. Prices depend on weather and policy."


class MarketRank(BaseModel):
    market_id: int
    market: str
    district: str | None
    price: float
    price_date: date_type
    distance_km: float | None
    transport_cost: float | None
    net_price: float


class ProfitIn(BaseModel):
    quantity_qtl: float = Field(gt=0)
    price_per_qtl: float = Field(gt=0)
    transport_cost: float = Field(ge=0, default=0)
    other_costs: float = Field(ge=0, default=0)


class ProfitOut(BaseModel):
    revenue: float
    total_costs: float
    net_profit: float


class AlertIn(BaseModel):
    crop_id: int
    market_id: int
    # above / below: price in Rs. rise / fall: percent change over the last 3 days
    direction: Literal["above", "below", "rise", "fall"]
    threshold: float = Field(gt=0)
    notify_sms: bool = True
    notify_push: bool = True


class AlertOut(BaseModel):
    id: int
    crop_id: int
    crop: str
    market_id: int
    market: str
    direction: str
    threshold: float
    current_price: float | None
    change_pct: float | None
    triggered: bool
    notify_sms: bool
    notify_push: bool


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class PushSubscribeIn(BaseModel):
    endpoint: str = Field(max_length=512)
    keys: PushKeys


class OutbreakOut(BaseModel):
    district: str
    crop: str | None
    disease: str
    count: int
    lat: float | None
    lon: float | None


class DiseaseBrief(BaseModel):
    id: int
    label: str
    name: str
    crop: str | None
    is_healthy: bool
    has_products: bool


class DosageIn(BaseModel):
    disease_id: int
    area_acres: float = Field(gt=0, le=1000)
    spray_volume_l_per_acre: float | None = Field(default=None, ge=50, le=600)


class ListingOut(BaseModel):
    id: int
    crop_id: int
    crop: str
    title: str
    description: str
    quantity_qtl: float
    price_per_qtl: float
    district: str | None
    state: str | None
    image_url: str | None
    status: str
    seller_name: str
    created_at: datetime
    market_price: float | None
    price_vs_market_pct: float | None
    mine: bool


class ListingUpdate(BaseModel):
    status: Literal["active", "sold"] | None = None
    price_per_qtl: float | None = Field(default=None, gt=0)
    quantity_qtl: float | None = Field(default=None, gt=0)


class InquiryIn(BaseModel):
    message: str = Field(min_length=3, max_length=500)


class InquiryOut(BaseModel):
    id: int
    listing_id: int
    listing_title: str
    buyer_name: str
    buyer_phone: str
    message: str
    created_at: datetime


class InventoryIn(BaseModel):
    crop_id: int
    quantity_qtl: float = Field(gt=0)
    harvest_date: date_type
    storage_location: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=300)


class InventoryUpdate(BaseModel):
    quantity_qtl: float | None = Field(default=None, ge=0)
    storage_location: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=300)


class InventoryOut(BaseModel):
    id: int
    crop_id: int
    crop: str
    quantity_qtl: float
    harvest_date: date_type
    storage_location: str | None
    notes: str | None
    days_stored: int
    shelf_life_days: int | None
    sell_soon: bool
    market_price: float | None
    est_value: float | None


class InventorySummary(BaseModel):
    items: list[InventoryOut]
    total_qtl: float
    total_value: float
    sell_soon_count: int


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    language: Literal["en", "hi", "kn"] = "en"


class ChatOut(BaseModel):
    reply: str
    intent: str
    suggestions: list[str] = []
