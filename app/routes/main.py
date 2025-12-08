from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models.game import Cell, Building, BuildingType
from app.models.user import Faction, User
from app import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Главная страница"""
    cells = Cell.query.all()
    factions = Faction.query.all()
    
    # Преобразуем клетки в формат, удобный для отображения на карте
    map_data = []
    for y in range(7):  # 7x7 карта
        row = []
        for x in range(7):
            cell = next((c for c in cells if c.x == x and c.y == y), None)
            
            # Если клетка не найдена, создаем пустую клетку
            if not cell:
                cell_data = {
                    'x': x,
                    'y': y,
                    'faction_id': None,
                    'building_type': None,
                    'color': '#ffffff'  # Белый цвет для пустых клеток
                }
            else:
                # Определяем цвет клетки в зависимости от фракции
                color = '#ffffff'  # По умолчанию белый
                if cell.faction_id:
                    # Цвета фракций
                    faction_colors = {
                        1: '#E53935',  # IT-Квантум - красный
                        2: '#43A047',  # Design-Квантум - зеленый
                        3: '#1E88E5',  # Robo-Квантум - синий
                        4: '#FDD835',  # Aero-Квантум - желтый
                        5: '#8E24AA',  # Дополнительный цвет - фиолетовый
                        6: '#F4511E'   # Дополнительный цвет - оранжевый
                    }
                    color = faction_colors.get(cell.faction_id, '#757575')
                
                # Определяем тип здания
                building_type = None
                if cell.building:
                    building_type = cell.building.type.value.upper()
                
                # Проверяем, является ли клетка соседней с территорией текущего пользователя
                is_adjacent = False
                if current_user.is_authenticated and current_user.faction:
                    # Получаем все клетки фракции пользователя
                    user_faction_cells = Cell.query.filter_by(faction_id=current_user.faction_id).all()
                    # Проверяем, граничит ли текущая клетка с любой из клеток фракции пользователя
                    for user_cell in user_faction_cells:
                        if ((abs(user_cell.x - x) == 1 and user_cell.y == y) or 
                            (abs(user_cell.y - y) == 1 and user_cell.x == x)):
                            is_adjacent = True
                            break
                
                cell_data = {
                    'x': x,
                    'y': y,
                    'faction_id': cell.faction_id,
                    'building_type': building_type,
                    'color': color,
                    'is_adjacent': is_adjacent
                }
            
            row.append(cell_data)
        map_data.append(row)
    
    # Если нет клеток с фракциями, создаем начальные территории в углах карты
    if not any(cell.faction_id for cell in cells):
        # Проверяем, есть ли фракции
        if len(factions) >= 4:
            # Создаем начальные территории в углах карты только для фракций без территорий
            corners = [(0, 0), (0, 6), (6, 0), (6, 6)]
            for i, (x, y) in enumerate(corners):
                faction_id = i + 1  # Фракции с ID от 1 до 4
                
                # Проверяем, есть ли у фракции уже территории
                faction_has_cells = Cell.query.filter_by(faction_id=faction_id).first() is not None
                if faction_has_cells:
                    continue
                
                # Находим клетку в углу
                corner_cell = next((c for c in cells if c.x == x and c.y == y), None)
                
                # Если клетка не существует, создаем ее
                if not corner_cell:
                    corner_cell = Cell(x=x, y=y, faction_id=faction_id)
                    db.session.add(corner_cell)
                else:
                    corner_cell.faction_id = faction_id
                
                # Создаем замок в углу
                if not corner_cell.building:
                    castle = Building(type=BuildingType.CASTLE, level=1, cell=corner_cell)
                    db.session.add(castle)
            
            # Сохраняем изменения
            db.session.commit()
            
            # Обновляем данные карты
            return redirect(url_for('main.index'))
    
    return render_template('main/index.html', 
                         map_data=map_data, 
                         factions=factions,
                         current_user=current_user)

@bp.route('/faction/<int:faction_id>')
@login_required
def faction_info(faction_id):
    """Страница информации о фракции"""
    faction = Faction.query.get_or_404(faction_id)
    
    # Получаем текущий ход
    from app.routes.game import get_current_turn
    current_turn = get_current_turn()
    
    # Получаем все действия пользователей фракции в текущем ходу
    from app.models.user_action import UserAction
    faction_users = User.query.filter_by(faction_id=faction_id).all()
    faction_user_ids = [user.id for user in faction_users]
    
    actions = UserAction.query.filter(
        UserAction.user_id.in_(faction_user_ids),
        UserAction.turn == current_turn
    ).all()
    
    # Подсчитываем количество зданий каждого типа
    buildings = {}
    cells = Cell.query.filter_by(faction_id=faction_id).all()
    
    for cell in cells:
        if cell.building_type:
            if cell.building_type not in buildings:
                buildings[cell.building_type] = 0
            buildings[cell.building_type] += 1
    
    return render_template('main/faction.html', 
                          faction=faction, 
                          current_turn=current_turn,
                          actions=actions,
                          buildings=buildings,
                          cells=cells)

@bp.route('/rules')
def rules():
    """Страница с правилами игры"""
    return render_template('main/rules.html') 