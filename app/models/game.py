from app import db
from enum import Enum

class BuildingType(Enum):
    CASTLE = 'castle'    # Замок
    SAWMILL = 'sawmill'  # Лесопилка
    MINE = 'mine'        # Шахта
    QUARRY = 'quarry'    # Карьер
    WAREHOUSE = 'warehouse'  # Склад
    BARRACKS = 'barracks'   # Казарма

class Cell(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    faction_id = db.Column(db.Integer, db.ForeignKey('faction.id'))
    building_type = db.Column(db.String(50), nullable=True)  # Прямое указание типа здания
    neutral_defenders = db.Column(db.Integer, nullable=True)  # Количество защитников для нейтральных клеток с постройками
    
    # Связи
    faction = db.relationship('Faction', backref='cells')
    building = db.relationship('Building', backref='cell', uselist=False)
    
    # Убеждаемся, что координаты клетки уникальны
    __table_args__ = (db.UniqueConstraint('x', 'y'),)

class Building(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum(BuildingType), nullable=False)
    level = db.Column(db.Integer, default=1)
    cell_id = db.Column(db.Integer, db.ForeignKey('cell.id'), unique=True)
    
    def get_production(self):
        """Возвращает производство ресурсов за ход в зависимости от типа и уровня здания"""
        base_production = {
            BuildingType.CASTLE: {},  # Замок не производит ресурсы напрямую
            BuildingType.SAWMILL: {'wood': 3},
            BuildingType.MINE: {'ore': 3},
            BuildingType.QUARRY: {'stone': 3},
            BuildingType.WAREHOUSE: {},  # Склад не производит ресурсы
            BuildingType.BARRACKS: {}    # Казарма не производит ресурсы
        }
        
        # Увеличиваем производство на 50% за каждый уровень после первого
        production = base_production[self.type]
        if self.level > 1:
            for resource in production:
                production[resource] = int(production[resource] * (1 + 0.5 * (self.level - 1)))
        
        return production
    
    def get_storage_bonus(self):
        """Возвращает бонус к хранилищу ресурсов (для складов и замков)"""
        if self.type == BuildingType.WAREHOUSE:
            return 50 * self.level  # +50 к максимуму каждого ресурса за уровень
        elif self.type == BuildingType.CASTLE:
            return 100 * self.level  # +100 к максимуму каждого ресурса за уровень замка
        return 0
    
    def get_warrior_capacity(self):
        """Возвращает вместимость воинов (для казарм и замков)"""
        if self.type == BuildingType.BARRACKS:
            return 10 * self.level  # +10 к максимуму воинов за уровень
        elif self.type == BuildingType.CASTLE:
            return 20 * self.level  # +20 к максимуму воинов за уровень замка
        return 0 