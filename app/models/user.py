from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    full_name = db.Column(db.String(128), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    faction_id = db.Column(db.Integer, db.ForeignKey('faction.id'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class Faction(db.Model):
    __tablename__ = 'faction'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False)  # HEX color code
    users = db.relationship('User', backref='faction', lazy=True)
    
    # Ресурсы фракции
    gold = db.Column(db.Integer, default=10)
    wood = db.Column(db.Integer, default=5)
    stone = db.Column(db.Integer, default=5)
    ore = db.Column(db.Integer, default=5)
    warriors = db.Column(db.Integer, default=1)
    
    # Максимальные значения ресурсов (могут быть увеличены постройками)
    max_gold = db.Column(db.Integer, default=100)
    max_wood = db.Column(db.Integer, default=50)
    max_stone = db.Column(db.Integer, default=50)
    max_ore = db.Column(db.Integer, default=50)
    max_warriors = db.Column(db.Integer, default=20) 