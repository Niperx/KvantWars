from flask import Blueprint, jsonify, request, flash, redirect, url_for, render_template
from flask_login import login_required, current_user
from app import db
from app.models.game import Cell, Building, BuildingType
from app.models.user import Faction, User
from app.models.user_action import UserAction, ActionType
from datetime import datetime
from sqlalchemy import and_, or_
import logging
from app.game_manager import GameManager
import json
import random
from app.models.faction_log import FactionLog

bp = Blueprint('game', __name__)
logger = logging.getLogger('game')

@bp.route('/api/turn', methods=['GET'])
def get_turn():
    """Возвращает информацию о текущем ходе"""
    game_manager = GameManager.get_instance()
    return jsonify({
        'current_turn': game_manager.current_turn,
        'seconds_left': game_manager.seconds_left
    })

@bp.route('/api/map', methods=['GET'])
def get_map():
    """Возвращает данные карты для отображения"""
    cells = Cell.query.all()
    factions = Faction.query.all()
    
    # Создаем словарь с названиями фракций для быстрого доступа
    faction_names = {}
    for faction in factions:
        # Сокращаем название фракции, убирая слово "Квантум"
        short_name = faction.name.replace("-Квантум", "").replace(" Квантум", "")
        faction_names[faction.id] = short_name
    
    map_data = []
    for cell in cells:
        cell_data = {
            'x': cell.x,
            'y': cell.y,
            'faction_id': cell.faction_id,
            'building_type': cell.building_type
        }
        
        # Добавляем название фракции, если клетка принадлежит фракции
        if cell.faction_id and cell.faction_id in faction_names:
            cell_data['faction_name'] = faction_names[cell.faction_id]
        
        # Если клетка нейтральная и на ней есть постройка, добавляем информацию о защитниках
        if cell.faction_id is None and cell.building_type is not None:
            # Если значение защитников еще не установлено, генерируем его
            if cell.neutral_defenders is None:
                cell.neutral_defenders = random.randint(1, 3)
                db.session.add(cell)
                db.session.commit()
            
            cell_data['neutral_defenders'] = cell.neutral_defenders
        
        map_data.append(cell_data)
    
    return jsonify(map_data)

@bp.route('/api/faction_logs')
@login_required
def get_faction_logs():
    """Возвращает логи действий фракции в текущем ходу"""
    if not current_user.faction_id:
        return jsonify({'success': False, 'message': 'Вы не принадлежите ни к одной фракции'})
    
    current_turn = get_current_turn()
    
    # Получаем все действия пользователей фракции в текущем ходу
    faction_users = User.query.filter_by(faction_id=current_user.faction_id).all()
    faction_user_ids = [user.id for user in faction_users]
    
    actions = UserAction.query.filter(
        UserAction.user_id.in_(faction_user_ids),
        UserAction.turn == current_turn
    ).order_by(UserAction.created_at.desc()).all()
    
    # Получаем логи фракции из таблицы faction_logs
    faction_logs = FactionLog.query.filter_by(
        faction_id=current_user.faction_id,
        turn=current_turn
    ).order_by(FactionLog.timestamp.desc()).all()
    
    # Преобразуем действия в понятный формат
    logs = []
    
    # Добавляем логи действий пользователей
    for action in actions:
        user = User.query.get(action.user_id)
        username = user.username if user else "Неизвестный пользователь"
        
        log_entry = {
            'id': action.id,
            'username': username,
            'action_type': action.action_type,
            'timestamp': action.created_at.strftime('%H:%M:%S'),
            'message': format_action_message(action)
        }
        logs.append(log_entry)
    
    # Добавляем логи фракции
    for log in faction_logs:
        log_entry = {
            'id': f'faction_log_{log.id}',
            'username': 'Система',
            'action_type': 'SYSTEM',
            'timestamp': log.timestamp.strftime('%H:%M:%S'),
            'message': log.message
        }
        logs.append(log_entry)
    
    # Сортируем все логи по времени (сначала новые)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({
        'success': True,
        'current_turn': current_turn,
        'logs': logs
    })

def format_action_message(action):
    """Форматирует сообщение о действии для отображения в логах"""
    if action.action_type == ActionType.CAPTURE_CELL.value:
        return f"Отправлено {action.warriors} воинов для захвата клетки ({action.target_x}, {action.target_y})"
    
    elif action.action_type == ActionType.BUILD.value:
        building_name = get_building_name(action.building_type)
        return f"Начато строительство {building_name} на клетке ({action.target_x}, {action.target_y})"
    
    elif action.action_type == ActionType.TRANSFER_RESOURCES.value:
        resources_data = json.loads(action.resources) if action.resources else {}
        target_faction_id = resources_data.get('faction_id')
        target_faction = Faction.query.get(target_faction_id) if target_faction_id else None
        
        resources_text = []
        if resources_data.get('gold', 0) > 0:
            resources_text.append(f"{resources_data.get('gold')} золота")
        if resources_data.get('wood', 0) > 0:
            resources_text.append(f"{resources_data.get('wood')} дерева")
        if resources_data.get('stone', 0) > 0:
            resources_text.append(f"{resources_data.get('stone')} камня")
        if resources_data.get('ore', 0) > 0:
            resources_text.append(f"{resources_data.get('ore')} руды")
        
        resources_str = ", ".join(resources_text)
        faction_name = target_faction.name if target_faction else "неизвестную фракцию"
        
        return f"Передано {resources_str} фракции {faction_name}"
    
    elif action.action_type == ActionType.RECRUIT_WARRIORS.value:
        return f"Нанято {action.warriors} воинов"
    
    elif action.action_type == ActionType.DEFEND_CELL.value:
        return f"Отправлено {action.warriors} воинов для защиты клетки ({action.target_x}, {action.target_y})"
    
    else:
        return f"Выполнено действие {action.action_type}"

@bp.route('/api/resources')
@login_required
def get_resources():
    """
    Возвращает ресурсы фракции пользователя
    """
    print(f"[API] Запрос ресурсов от пользователя {current_user.username} (id: {current_user.id})")
    
    if not current_user.faction:
        print(f"[API] Пользователь {current_user.username} не принадлежит ни к одной фракции")
        return jsonify({
            'gold': 0,
            'wood': 0,
            'stone': 0,
            'ore': 0,
            'warriors': 0
        })
    
    # Получаем текущий ход
    current_turn = get_current_turn()
    
    # Проверяем, есть ли отправленные воины на захват в текущем ходу
    warriors_sent = 0
    capture_actions = UserAction.query.filter_by(
        user_id=current_user.id,
        action_type='CAPTURE_CELL',
        turn=current_turn  # Только для текущего хода
    ).all()
    
    for action in capture_actions:
        if action.warriors:
            warriors_sent += action.warriors
    
    # Проверяем, есть ли отправленные воины на защиту в текущем ходу
    defend_actions = UserAction.query.filter_by(
        user_id=current_user.id,
        action_type='DEFEND_CELL',
        turn=current_turn  # Только для текущего хода
    ).all()
    
    warriors_defending = 0
    for action in defend_actions:
        if action.warriors:
            warriors_defending += action.warriors
    
    # Общее количество отправленных воинов
    total_warriors_sent = warriors_sent + warriors_defending
    
    response_data = {
        'gold': current_user.faction.gold,
        'wood': current_user.faction.wood,
        'stone': current_user.faction.stone,
        'ore': current_user.faction.ore,
        'warriors': current_user.faction.warriors,
        'warriors_sent': warriors_sent,
        'warriors_defending': warriors_defending,
        'total_warriors_sent': total_warriors_sent
    }
    
    print(f"[API] Возвращаем ресурсы для фракции {current_user.faction.name}: {response_data}")
    
    return jsonify(response_data)

@bp.route('/api/execute_direct_action', methods=['POST'])
@login_required
def execute_direct_action():
    """Выполняет прямое действие пользователя"""
    # Проверяем, что пользователь принадлежит к фракции
    if not current_user.faction_id:
        return jsonify({'success': False, 'message': 'Вы не принадлежите ни к одной фракции'})
    
    # Получаем данные из запроса
    data = request.json
    action_type = data.get('action_type')
    target_x = data.get('target_x')
    target_y = data.get('target_y')
    
    # Проверяем, что координаты указаны
    if action_type != 'TRANSFER_RESOURCES' and (target_x is None or target_y is None):
        return jsonify({'success': False, 'message': 'Необходимо указать координаты'})
    
    # Получаем клетку по координатам
    if action_type != 'TRANSFER_RESOURCES':
        cell = Cell.query.filter_by(x=target_x, y=target_y).first()
        if not cell:
            return jsonify({'success': False, 'message': 'Клетка не найдена'})
    
    # Проверяем, владеет ли фракция центральной клеткой (бонус к воинам)
    has_warriors_bonus = False
    center_cell = Cell.query.filter_by(x=3, y=3, faction_id=current_user.faction_id).first()
    if center_cell:
        has_warriors_bonus = True
        print(f"[API] Фракция {current_user.faction.name} имеет бонус +20% к боевой мощи от центральной клетки")
    
    # Обрабатываем различные типы действий
    if action_type == 'CAPTURE_CELL':
        # Проверяем, что указано количество воинов
        warriors = data.get('warriors')
        if not warriors or warriors <= 0:
            return jsonify({'success': False, 'message': 'Необходимо указать количество воинов'})
        
        # Проверяем, является ли клетка угловой (с замком) и принадлежит ли другой фракции
        if is_corner_cell(target_x, target_y) and cell.faction_id and cell.faction_id != current_user.faction_id:
            return jsonify({'success': False, 'message': 'Нельзя захватить замок другой фракции'})
        
        # Проверяем, что клетка соседствует с территорией фракции
        if not is_adjacent_to_faction(target_x, target_y, current_user.faction_id) and not cell.faction_id == current_user.faction_id:
            return jsonify({'success': False, 'message': 'Можно захватывать только клетки, соседние с вашей территорией'})
        
        # Проверяем, что у фракции достаточно воинов
        if current_user.faction.warriors < warriors:
            return jsonify({'success': False, 'message': 'Недостаточно воинов'})
        
        # Уменьшаем количество воинов у фракции
        current_user.faction.warriors -= warriors
        
        # Если есть бонус к воинам, добавляем 30% к боевой мощи (но не к количеству отправленных воинов)
        actual_warriors = warriors
        effective_warriors = warriors
        if has_warriors_bonus:
            bonus_warriors = int(warriors * 0.3)
            effective_warriors += bonus_warriors
            print(f"[API] Фракция {current_user.faction.name} получает бонус +{bonus_warriors} к боевой мощи при захвате")
        
        # Записываем действие в историю
        action = UserAction(
            user_id=current_user.id,
            action_type=ActionType.CAPTURE_CELL.value,
            target_x=target_x,
            target_y=target_y,
            warriors=actual_warriors,  # Сохраняем фактическое количество воинов без бонуса
            turn=get_current_turn()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Отправлено {warriors} воинов для захвата клетки ({target_x}, {target_y})' + 
                      (f' (эффективная сила: {effective_warriors} с учетом бонуса +30%)' if has_warriors_bonus else '') + 
                      '. Результат будет известен в конце хода.'
        })
        
    elif action_type == 'BUILD':
        # Проверяем, что указан тип здания
        building_type = data.get('building_type')
        if not building_type:
            return jsonify({'success': False, 'message': 'Необходимо указать тип здания'})
        
        # Проверяем, что пользователь не пытается построить замок
        if building_type == 'CASTLE':
            return jsonify({'success': False, 'message': 'Замок является главным зданием фракции и не может быть построен'})
        
        # Проверяем, что клетка принадлежит фракции пользователя
        if cell.faction_id != current_user.faction_id:
            return jsonify({'success': False, 'message': 'Эта клетка не принадлежит вашей фракции'})
        
        # Проверяем, что на клетке нет здания
        if cell.building_type:
            return jsonify({'success': False, 'message': 'На этой клетке уже есть здание'})
        
        # Определяем стоимость здания в зависимости от типа
        building_costs = {
            'CASTLE': {'gold': 50, 'wood': 20, 'stone': 20, 'ore': 10},
            'SAWMILL': {'gold': 30, 'wood': 10, 'stone': 15, 'ore': 5},
            'MINE': {'gold': 30, 'wood': 15, 'stone': 10, 'ore': 5},
            'QUARRY': {'gold': 30, 'wood': 15, 'stone': 5, 'ore': 10},
            'WAREHOUSE': {'gold': 20, 'wood': 20, 'stone': 20, 'ore': 0},
            'BARRACKS': {'gold': 40, 'wood': 15, 'stone': 15, 'ore': 10}
        }
        
        # Получаем стоимость выбранного здания
        cost = building_costs.get(building_type)
        if not cost:
            return jsonify({'success': False, 'message': 'Неизвестный тип здания'})
        
        # Проверяем, достаточно ли ресурсов у фракции
        faction = current_user.faction
        if faction.gold < cost['gold']:
            return jsonify({'success': False, 'message': f'Недостаточно золота. Требуется: {cost["gold"]}'})
        if faction.wood < cost['wood']:
            return jsonify({'success': False, 'message': f'Недостаточно дерева. Требуется: {cost["wood"]}'})
        if faction.stone < cost['stone']:
            return jsonify({'success': False, 'message': f'Недостаточно камня. Требуется: {cost["stone"]}'})
        if faction.ore < cost['ore']:
            return jsonify({'success': False, 'message': f'Недостаточно руды. Требуется: {cost["ore"]}'})
        
        # Списываем ресурсы
        faction.gold -= cost['gold']
        faction.wood -= cost['wood']
        faction.stone -= cost['stone']
        faction.ore -= cost['ore']
        
        # Записываем действие в историю
        action = UserAction(
            user_id=current_user.id,
            action_type=ActionType.BUILD.value,
            target_x=target_x,
            target_y=target_y,
            building_type=building_type,
            turn=get_current_turn()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Ресурсы выделены на строительство {get_building_name(building_type)} на клетке ({target_x}, {target_y}). Строительство будет завершено в конце хода.'
        })
        
    elif action_type == 'TRANSFER_RESOURCES':
        # Проверяем, что указаны ресурсы и фракция-получатель
        resources_data = data.get('resources')
        if not resources_data or not resources_data.get('faction_id'):
            return jsonify({'success': False, 'message': 'Необходимо указать ресурсы и фракцию-получателя'})
        
        # Получаем фракцию-получателя
        target_faction_id = resources_data.get('faction_id')
        target_faction = Faction.query.get(target_faction_id)
        if not target_faction:
            return jsonify({'success': False, 'message': 'Фракция-получатель не найдена'})
        
        # Проверяем, что фракция-получатель не является фракцией отправителя
        if target_faction.id == current_user.faction.id:
            return jsonify({'success': False, 'message': 'Нельзя передать ресурсы своей фракции'})
        
        # Получаем количество ресурсов для передачи
        gold = int(resources_data.get('gold', 0))
        wood = int(resources_data.get('wood', 0))
        stone = int(resources_data.get('stone', 0))
        ore = int(resources_data.get('ore', 0))
        
        # Проверяем, что передается хотя бы один ресурс
        if gold <= 0 and wood <= 0 and stone <= 0 and ore <= 0:
            return jsonify({'success': False, 'message': 'Необходимо передать хотя бы один ресурс'})
        
        # Проверяем, что у фракции достаточно ресурсов
        faction = current_user.faction
        if faction.gold < gold or faction.wood < wood or \
           faction.stone < stone or faction.ore < ore:
            return jsonify({'success': False, 'message': 'Недостаточно ресурсов'})
        
        # Уменьшаем ресурсы фракции-отправителя
        faction.gold -= gold
        faction.wood -= wood
        faction.stone -= stone
        faction.ore -= ore
        
        # Увеличиваем ресурсы фракции-получателя
        target_faction.gold += gold
        target_faction.wood += wood
        target_faction.stone += stone
        target_faction.ore += ore
        
        # Сохраняем информацию о ресурсах в формате JSON
        resources_json = json.dumps({
            'gold': gold,
            'wood': wood,
            'stone': stone,
            'ore': ore,
            'target_faction_id': target_faction.id
        })
        
        # Записываем действие в историю
        action = UserAction(
            user_id=current_user.id,
            action_type=ActionType.TRANSFER_RESOURCES.value,
            resources=resources_json,
            turn=get_current_turn()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Ресурсы успешно переданы фракции {target_faction.name}'})
    
    elif action_type == 'RECRUIT_WARRIORS':
        # Проверяем, что указано количество воинов
        warriors_count = data.get('warriors')
        try:
            warriors_count = int(warriors_count)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Необходимо указать корректное количество воинов для найма'})
            
        if warriors_count < 1:
            return jsonify({'success': False, 'message': 'Количество воинов должно быть больше 0'})
        
        # Стоимость найма: 5 золота за воина
        cost_per_warrior = 5
        total_cost = warriors_count * cost_per_warrior
        
        # Проверяем, достаточно ли золота у фракции
        faction = current_user.faction
        if faction.gold < total_cost:
            return jsonify({'success': False, 'message': f'Недостаточно золота. Требуется: {total_cost}'})
        
        # Списываем золото и добавляем воинов
        faction.gold -= total_cost
        faction.warriors += warriors_count
        
        # Записываем действие в историю
        action = UserAction(
            user_id=current_user.id,
            action_type=ActionType.RECRUIT_WARRIORS.value,
            warriors=warriors_count,
            turn=get_current_turn()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Нанято {warriors_count} воинов за {total_cost} золота.'
        })
    
    elif action_type == 'DEFEND_CELL':
        # Проверяем, что указано количество воинов
        warriors = data.get('warriors')
        if not warriors or warriors <= 0:
            return jsonify({'success': False, 'message': 'Необходимо указать количество воинов для защиты'})
        
        # Проверяем, что у фракции достаточно воинов
        faction = current_user.faction
        if faction.warriors < warriors:
            return jsonify({'success': False, 'message': f'Недостаточно воинов. У вас есть только {faction.warriors} воинов.'})
        
        # Проверяем, что клетка принадлежит фракции пользователя
        if cell.faction_id != current_user.faction_id:
            return jsonify({'success': False, 'message': 'Можно защищать только свои клетки'})
        
        # Списываем воинов
        faction.warriors -= warriors
        
        # Если есть бонус к воинам, добавляем 30% к боевой мощи (но не к количеству отправленных воинов)
        actual_warriors = warriors
        effective_warriors = warriors
        if has_warriors_bonus:
            bonus_warriors = int(warriors * 0.3)
            effective_warriors += bonus_warriors
            print(f"[API] Фракция {current_user.faction.name} получает бонус +{bonus_warriors} к боевой мощи при защите")
        
        # Записываем действие в историю
        action = UserAction(
            user_id=current_user.id,
            action_type=ActionType.DEFEND_CELL.value,
            target_x=target_x,
            target_y=target_y,
            warriors=actual_warriors,  # Сохраняем фактическое количество воинов без бонуса
            turn=get_current_turn()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Отправлено {warriors} воинов для защиты клетки ({target_x}, {target_y})' + 
                      (f' (эффективная сила: {effective_warriors} с учетом бонуса +30%)' if has_warriors_bonus else '')
        })
    
    else:
        return jsonify({'success': False, 'message': 'Неизвестный тип действия'})

def get_current_turn():
    """Возвращает номер текущего хода"""
    game_manager = GameManager.get_instance()
    return game_manager.current_turn

def is_adjacent_to_faction(x, y, faction_id):
    """Проверяет, граничит ли клетка с территорией фракции"""
    # Проверяем соседние клетки (вверх, вниз, влево, вправо)
    adjacent_cells = [
        (x+1, y), (x-1, y), (x, y+1), (x, y-1)
    ]
    
    for adj_x, adj_y in adjacent_cells:
        cell = Cell.query.filter_by(x=adj_x, y=adj_y, faction_id=faction_id).first()
        if cell:
            return True
    
    return False

def is_corner_cell(x, y):
    """Проверяет, является ли клетка угловой (с замком)"""
    corners = [(0, 0), (0, 6), (6, 0), (6, 6)]
    return (x, y) in corners

# Вспомогательная функция для получения названия здания
def get_building_name(building_type):
    building_names = {
        'CASTLE': 'Замок',
        'SAWMILL': 'Лесопилка',
        'MINE': 'Шахта',
        'QUARRY': 'Карьер',
        'WAREHOUSE': 'Склад',
        'BARRACKS': 'Казармы'
    }
    return building_names.get(building_type, 'Здание') 