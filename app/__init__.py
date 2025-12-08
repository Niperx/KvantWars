from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
import logging

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)  # Показывать только предупреждения и ошибки
    
    # Настройка логгера для game_manager
    game_logger = logging.getLogger('game_manager')
    game_logger.setLevel(logging.INFO)
    
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    from app.routes import auth, main, game
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(game.bp)
    
    from app.game_manager import GameManager
    
    # Инициализируем GameManager при создании приложения
    game_manager = GameManager.get_instance()
    game_manager.start_game(app)
    
    # Сохраняем game_manager в конфигурации приложения
    app.config['GAME_MANAGER'] = game_manager
    
    return app 