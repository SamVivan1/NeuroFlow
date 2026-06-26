from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from app.database import Base

class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    activity = Column(String, index=True)
    stress_level = Column(Integer)
    heart_rate = Column(Integer)
    avg_bpm_30s = Column(Integer)
    spo2 = Column(Integer)
    tremor_intensity = Column(Float)
    battery_pct = Column(Integer)
    device_status = Column(String)
