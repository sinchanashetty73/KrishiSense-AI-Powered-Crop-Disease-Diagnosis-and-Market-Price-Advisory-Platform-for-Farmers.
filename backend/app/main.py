from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .routers import advisory, alerts, auth, chat, inventory, market, meta, outbreaks, prices, scans
from .seed import seed_demo_prices, seed_reference


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Creates tables on first start. For schema changes later, add Alembic migrations.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db)
        if settings.seed_demo_data:
            seed_demo_prices(db)
    yield


app = FastAPI(title="KrishiSense API", version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])

# Everything lives under /api so nginx and the AWS load balancer can route by path.
api = APIRouter(prefix="/api")
for r in (meta.router, auth.router, scans.router, prices.router, alerts.router, outbreaks.router,
          advisory.router, market.router, inventory.router, chat.router):
    api.include_router(r)
app.include_router(api)
