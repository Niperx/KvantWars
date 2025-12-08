from app import create_app, db
from app.models.user import User, Faction
from app.models.game import Cell, Building, BuildingType

def init_db():
    app = create_app()
    with app.app_context():
        # Пересоздаем все таблицы
        db.drop_all()
        db.create_all()
        
        print("Создание фракций...")
        # Создаем фракции
        factions = [
            Faction(name='IT-Квантум', color='#FF0000'),
            Faction(name='Design-Квантум', color='#00FF00'),
            Faction(name='Robo-Квантум', color='#0000FF'),
            Faction(name='Aero-Квантум', color='#FFFF00')
        ]
        
        for faction in factions:
            db.session.add(faction)
        db.session.commit()
        
        print("Создание администратора...")
        # Создаем администратора в первой фракции (IT-Квантум)
        admin = User(
            username='admin',
            email='admin@example.com',
            full_name='Администратор Системы',
            age=30,
            is_approved=True,
            is_admin=True,
            faction_id=factions[0].id  # IT-Квантум
        )
        admin.set_password('admin')
        db.session.add(admin)
        
        # Создаем пользователей для других фракций
        design_user = User(
            username='design',
            email='design@example.com',
            full_name='Design Пользователь',
            age=25,
            is_approved=True,
            is_admin=False,
            faction_id=factions[1].id  # Design-Квантум
        )
        design_user.set_password('design')
        db.session.add(design_user)
        
        aero_user = User(
            username='aero',
            email='aero@example.com',
            full_name='Aero Пользователь',
            age=25,
            is_approved=True,
            is_admin=False,
            faction_id=factions[3].id  # Aero-Квантум
        )
        aero_user.set_password('aero')
        db.session.add(aero_user)
        
        robo_user = User(
            username='robo',
            email='robo@example.com',
            full_name='Robo Пользователь',
            age=25,
            is_approved=True,
            is_admin=False,
            faction_id=factions[2].id  # Robo-Квантум
        )
        robo_user.set_password('robo')
        db.session.add(robo_user)
        
        db.session.commit()
        
        print("Создание всех клеток карты 7x7...")
        # Создаем все клетки карты 7x7
        for x in range(7):
            for y in range(7):
                cell = Cell(
                    x=x,
                    y=y,
                    faction_id=None  # Изначально клетки не принадлежат никакой фракции
                )
                db.session.add(cell)
        db.session.commit()
        
        print("Назначение начальных клеток для фракций...")
        # Назначаем начальные клетки для каждой фракции (стартовые позиции)
        start_positions = [
            (0, 0),    # IT-Квантум - верхний левый угол
            (6, 0),    # Design-Квантум - верхний правый угол
            (0, 6),    # Robo-Квантум - нижний левый угол
            (6, 6)     # Aero-Квантум - нижний правый угол
        ]
        
        for i, faction in enumerate(factions):
            x, y = start_positions[i]
            # Находим клетку по координатам
            cell = Cell.query.filter_by(x=x, y=y).first()
            # Назначаем клетку фракции
            cell.faction_id = faction.id
            db.session.add(cell)
            
            # Создаем замок для начальной клетки
            castle = Building(
                type=BuildingType.CASTLE,
                level=1,
                cell_id=cell.id
            )
            db.session.add(castle)
        
        db.session.commit()
        print("Инициализация базы данных завершена!")

if __name__ == '__main__':
    init_db() 