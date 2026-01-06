from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .connection import Base

class System(Base):
    __tablename__ = 'systems'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False) # e.g. "Fe-Cr"
    element_a = Column(String, nullable=False)
    element_b = Column(String, nullable=False)
    element_c = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    results = relationship("SimulationResult", back_populates="system")

class SimulationResult(Base):
    __tablename__ = 'simulation_results'

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey('systems.id'))
    formula = Column(String, nullable=False)
    
    # Structure Properties
    total_atoms = Column(Integer)
    lattice_a = Column(Float)
    density = Column(Float)
    
    # Thermodynamic Properties
    energy_per_atom = Column(Float)
    energy_above_hull = Column(Float)
    is_stable = Column(Boolean)
    
    # MD Results
    md_performed = Column(Boolean, default=False)
    md_avg_temperature = Column(Float, nullable=True)
    md_temp_fluctuation = Column(Float, nullable=True)
    md_avg_energy_per_atom = Column(Float, nullable=True)
    md_volume_change_percent = Column(Float, nullable=True)
    md_thermally_stable = Column(Boolean, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    system = relationship("System", back_populates="results")
