"""Entry point for the scheduled alert check:  python -m app.jobs.run_alerts
Local:   docker compose --profile jobs run --rm alerts
AWS:     EventBridge Scheduler -> ECS RunTask (backend image, command override). See docs/AWS_DEPLOYMENT.md."""
import json
import logging

from ..database import Base, SessionLocal, engine
from ..services.alert_dispatch import run_alerts

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        print(json.dumps(run_alerts(db)))
