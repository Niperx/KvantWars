from enum import Enum
from app import db
from datetime import datetime

class ActionType(Enum):
    CAPTURE_CELL = 'capture_cell'
    BUILD = 'build'
    UPGRADE = 'upgrade'
    TRANSFER_RESOURCES = 'transfer_resources'
    RECRUIT_WARRIORS = 'recruit_warriors'
    DEFEND_CELL = 'defend_cell'

class UserAction(db.Model):
    """Модель для отслеживания действий пользователей"""
    __tablename__ = 'user_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    turn = db.Column(db.Integer, nullable=False)
    target_x = db.Column(db.Integer)
    target_y = db.Column(db.Integer)
    building_type = db.Column(db.String(50))
    warriors = db.Column(db.Integer)
    resources = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Отношения
    user = db.relationship('User', backref=db.backref('actions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<UserAction {self.id}: {self.action_type} by User {self.user_id} at Turn {self.turn}>'
    
    def to_dict(self):
        """Преобразует объект в словарь для API"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action_type': self.action_type,
            'turn': self.turn,
            'target_x': self.target_x,
            'target_y': self.target_y,
            'building_type': self.building_type,
            'warriors': self.warriors,
            'resources': self.resources,
            'created_at': self.created_at.isoformat() if self.created_at else None
        } 