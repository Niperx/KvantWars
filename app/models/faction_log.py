from datetime import datetime
from app import db

class FactionLog(db.Model):
    """Модель для хранения логов фракции"""
    __tablename__ = 'faction_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    faction_id = db.Column(db.Integer, db.ForeignKey('faction.id'), nullable=False)
    turn = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Отношение к фракции
    faction = db.relationship('Faction', backref=db.backref('logs', lazy='dynamic'))
    
    def __repr__(self):
        return f'<FactionLog {self.id}: {self.message}>' 