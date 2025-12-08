import os
from datetime import timedelta

class Config:
    # Базовые настройки
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///game.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки игры
    GAME_TURN_DURATION = 30  # длительность хода в секундах
    MAP_SIZE = 7  # размер карты (7x7)
    
    # Начальные ресурсы
    INITIAL_RESOURCES = {
        'gold': 10,
        'wood': 5,
        'stone': 5,
        'ore': 5,
        'warriors': 1
    }
    
    # Базовый прирост ресурсов за ход
    BASE_INCOME = {
        'gold': 2,
        'wood': 1,
        'stone': 1,
        'ore': 1,
        'warriors': 0
    }
    
    # Стоимость найма воинов
    WARRIOR_COST = 5  # золота
    MAX_WARRIORS_PER_TURN = 10
    WARRIOR_MAINTENANCE = 1  # стоимость содержания одного воина за ход
