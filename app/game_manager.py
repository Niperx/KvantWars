from datetime import datetime, timedelta
import threading
import time
import logging
import random
from sqlalchemy import func

from app import db
from app.models.game import Cell, Building, BuildingType
from app.models.user import User, Faction
from app.models.user_action import UserAction, ActionType
from app.models.faction_log import FactionLog

class GameManager:
    _instance = None
    TURN_DURATION = 30  # длительность хода в секундах
    
    def __init__(self):
        self.turn_start_time = None
        self.turn_timer = None
        self.is_running = False
        self.app = None
        self.current_turn = 0
        self.next_turn_time = None  # время следующего хода
        self.logger = logging.getLogger('game_manager')
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            # Используем обычный print, так как экземпляр еще не создан и логгер недоступен
            print("[GameManager] Создание нового экземпляра GameManager")
            cls._instance = GameManager()
        return cls._instance
    
    @property
    def seconds_left(self):
        """Возвращает количество секунд до конца текущего хода"""
        if not self.next_turn_time:
            return self.TURN_DURATION
        
        now = datetime.utcnow()
        if now >= self.next_turn_time:
            return 0
        
        return int((self.next_turn_time - now).total_seconds())
    
    def start_game(self, app=None):
        """Запускает игровой цикл"""
        if app:
            self.app = app
        
        if not self.app:
            self.logger.error("Ошибка: приложение не инициализировано")
            return
        
        # Проверяем, не запущена ли уже игра
        if self.is_running:
            self.logger.info("Игра уже запущена, пропускаем повторный запуск")
            return
        
        # Отменяем предыдущий таймер, если он существует
        if self.turn_timer:
            self.turn_timer.cancel()
        
        self.is_running = True
        self.current_turn = 1
        self.turn_start_time = datetime.utcnow()
        self.next_turn_time = self.turn_start_time + timedelta(seconds=self.TURN_DURATION)
        
        with self.app.app_context():
            self._initialize_faction_resources()
        
        self.logger.info("Игра запущена")
        
        # Запускаем первый ход
        self._schedule_next_turn()
    
    def stop_game(self):
        """Останавливает игровой цикл"""
        self.is_running = False
        if self.turn_timer:
            self.turn_timer.cancel()
        self.logger.info("Игра остановлена")
    
    def _schedule_next_turn(self):
        """Планирует следующий ход"""
        if not self.is_running:
            return
            
        # Отменяем предыдущий таймер, если он существует
        if self.turn_timer:
            self.turn_timer.cancel()
            self.turn_timer = None
        
        # Планируем следующий ход
        self.turn_timer = threading.Timer(self.TURN_DURATION, self._process_turn)
        self.turn_timer.daemon = True
        self.turn_timer.start()
        
        # Устанавливаем время следующего хода
        self.next_turn_time = datetime.utcnow() + timedelta(seconds=self.TURN_DURATION)
        self.logger.info(f"Запланирован ход {self.current_turn + 1} на {self.next_turn_time.strftime('%H:%M:%S')}")
    
    def _process_turn(self):
        """Обработка хода игры"""
        self.logger.info(f"Обработка хода {self.current_turn}")
        
        # Обрабатываем захваты клеток
        self._process_cell_captures()
        
        # Проверяем связность территорий и освобождаем несвязанные клетки
        self._check_territory_connectivity()
        
        # Обрабатываем строительство зданий
        self._process_buildings()
        
        # Обновляем ресурсы фракций
        self._update_faction_resources()
        
        # Увеличиваем номер текущего хода
        self.current_turn += 1
        
        # Сохраняем изменения в базе данных
        with self.app.app_context():
            try:
                db.session.commit()
            except Exception as e:
                self.logger.error(f"Ошибка при сохранении изменений хода: {str(e)}")
                db.session.rollback()
        
        # Планируем следующий ход
        self._schedule_next_turn()
    
    def _process_cell_captures(self):
        """Обрабатывает захваты клеток в конце хода"""
        with self.app.app_context():
            try:
                # Получаем все действия захвата клеток для текущего хода
                capture_actions = UserAction.query.filter_by(
                    action_type='capture_cell',
                    turn=self.current_turn
                ).all()
                
                # Получаем все действия защиты клеток для текущего хода
                defend_actions = UserAction.query.filter_by(
                    action_type='defend_cell',
                    turn=self.current_turn
                ).all()
                
                # Группируем действия защиты по координатам клеток
                cell_defenses = {}
                for action in defend_actions:
                    key = (action.target_x, action.target_y)
                    if key not in cell_defenses:
                        cell_defenses[key] = []
                    cell_defenses[key].append(action)
                
                # Группируем действия по координатам клеток
                cell_captures = {}
                for action in capture_actions:
                    key = (action.target_x, action.target_y)
                    if key not in cell_captures:
                        cell_captures[key] = []
                    cell_captures[key].append(action)
                
                # Проверяем, какие фракции владеют центральной клеткой (бонус к боевой мощи)
                factions_with_bonus = set()
                center_cells = Cell.query.filter_by(x=3, y=3).all()
                for cell in center_cells:
                    if cell.faction_id:
                        factions_with_bonus.add(cell.faction_id)
                        self.logger.info(f"Фракция {cell.faction_id} имеет бонус +20% к боевой мощи от центральной клетки")
                
                # Обрабатываем каждую клетку, на которую претендуют фракции
                for coords, actions in cell_captures.items():
                    x, y = coords
                    
                    # Получаем клетку
                    cell = Cell.query.filter_by(x=x, y=y).first()
                    if not cell:
                        self.logger.warning(f"Клетка с координатами ({x}, {y}) не найдена")
                        continue
                    
                    # Проверяем, является ли клетка угловой (с замком)
                    if self.is_corner_cell(x, y) and cell.faction_id:
                        self.logger.warning(f"Попытка захвата замка фракции {cell.faction_id} на клетке ({x}, {y})")
                        # Возвращаем воинов всем фракциям, которые пытались захватить замок
                        for action in actions:
                            user = action.user
                            faction = user.faction
                            if faction:
                                faction.warriors = min(faction.warriors + action.warriors, faction.max_warriors)
                                self.logger.info(f"Возвращено {action.warriors} воинов фракции {faction.id} (попытка захвата замка)")
                        continue
                    
                    # Получаем защитников клетки, если они есть
                    defenders = cell_defenses.get((x, y), [])
                    total_defenders = 0
                    
                    # Если клетка принадлежит фракции и есть защитники
                    if cell.faction_id and defenders:
                        # Суммируем всех защитников с учетом бонуса
                        for action in defenders:
                            user = action.user
                            faction_id = user.faction_id
                            warriors = action.warriors
                            
                            # Применяем бонус к боевой мощи, если фракция владеет центральной клеткой
                            if faction_id in factions_with_bonus:
                                bonus_warriors = int(warriors * 0.2)
                                effective_warriors = warriors + bonus_warriors
                                self.logger.info(f"Фракция {faction_id} получает бонус +{bonus_warriors} к защите клетки ({x}, {y})")
                                total_defenders += effective_warriors
                            else:
                                total_defenders += warriors
                        
                        self.logger.info(f"Клетка ({x}, {y}) защищается {total_defenders} воинами фракции {cell.faction_id}")
                    
                    # Если на клетку претендует только одна фракция
                    if len(actions) == 1:
                        action = actions[0]
                        user = action.user
                        faction_id = user.faction_id
                        warriors_sent = action.warriors
                        
                        # Применяем бонус к боевой мощи, если фракция владеет центральной клеткой
                        effective_warriors = warriors_sent
                        if faction_id in factions_with_bonus:
                            bonus_warriors = int(warriors_sent * 0.2)
                            effective_warriors = warriors_sent + bonus_warriors
                            self.logger.info(f"Фракция {faction_id} получает бонус +{bonus_warriors} к захвату клетки ({x}, {y})")
                        
                        # Получаем фракцию пользователя
                        faction = Faction.query.get(faction_id)
                        if not faction:
                            self.logger.warning(f"Фракция с ID {faction_id} не найдена")
                            continue
                        
                        # Если клетка уже принадлежит этой фракции, просто возвращаем воинов
                        if cell.faction_id == faction_id:
                            self.logger.info(f"Клетка ({x}, {y}) уже принадлежит фракции {faction_id}")
                            # Возвращаем воинов обратно фракции
                            faction.warriors = min(faction.warriors + warriors_sent, faction.max_warriors)
                            self.logger.info(f"Возвращено {warriors_sent} воинов фракции {faction_id}")
                            continue
                        
                        # Проверяем, требуются ли дополнительные воины для захвата
                        additional_warriors_required = self.get_required_warriors_for_capture(cell)
                        
                        # Учитываем защитников клетки
                        if cell.faction_id and total_defenders > 0:
                            additional_warriors_required += total_defenders
                        
                        # Если требуются дополнительные воины и их недостаточно
                        # Используем effective_warriors для сравнения с требуемым количеством
                        if additional_warriors_required > 0 and effective_warriors <= additional_warriors_required:
                            self.logger.info(f"Недостаточно воинов для захвата клетки ({x}, {y}). Требуется минимум {additional_warriors_required + 1} воинов.")
                            # Все воины погибают
                            self.logger.info(f"Фракция {faction_id} потеряла {warriors_sent} воинов в попытке захвата клетки ({x}, {y})")
                            continue
                        
                        # Если клетка пуста или принадлежит другой фракции
                        old_faction_id = cell.faction_id
                        
                        # Захватываем клетку
                        cell.faction_id = faction_id
                        db.session.add(cell)
                        
                        # Рассчитываем, сколько воинов вернется
                        remaining_warriors = max(0, warriors_sent - additional_warriors_required)
                        
                        # Возвращаем оставшихся воинов обратно фракции
                        faction.warriors = min(faction.warriors + remaining_warriors, faction.max_warriors)
                        
                        if old_faction_id:
                            self.logger.info(f"Фракция {faction_id} захватила клетку ({x}, {y}) у фракции {old_faction_id}")
                        else:
                            self.logger.info(f"Фракция {faction_id} захватила пустую клетку ({x}, {y})")
                        
                        lost_warriors = warriors_sent - remaining_warriors
                        self.logger.info(f"Отправлено {warriors_sent} воинов, потеряно {lost_warriors}, возвращено {remaining_warriors} воинов фракции {faction_id}")
                    
                    # Если на клетку претендуют несколько фракций
                    else:
                        # Группируем действия по фракциям и суммируем воинов с учетом бонуса
                        faction_warriors = {}
                        for action in actions:
                            user = action.user
                            faction_id = user.faction_id
                            warriors = action.warriors
                            
                            if faction_id not in faction_warriors:
                                faction_warriors[faction_id] = 0
                            
                            # Применяем бонус к боевой мощи, если фракция владеет центральной клеткой
                            if faction_id in factions_with_bonus:
                                bonus_warriors = int(warriors * 0.2)
                                effective_warriors = warriors + bonus_warriors
                                self.logger.info(f"Фракция {faction_id} получает бонус +{bonus_warriors} к захвату клетки ({x}, {y})")
                                faction_warriors[faction_id] += effective_warriors
                            else:
                                faction_warriors[faction_id] += warriors
                        
                        # Проверяем, требуются ли дополнительные воины для захвата
                        additional_warriors_required = self.get_required_warriors_for_capture(cell)
                        
                        # Учитываем защитников клетки
                        if cell.faction_id and total_defenders > 0:
                            additional_warriors_required += total_defenders
                            
                        if additional_warriors_required > 0:
                            self.logger.info(f"Для захвата клетки ({x}, {y}) требуется на {additional_warriors_required} воинов больше")
                        
                        # Сортируем фракции по количеству воинов (по убыванию)
                        sorted_factions = sorted(faction_warriors.items(), key=lambda x: x[1], reverse=True)
                        
                        # Проверяем, есть ли ничья между фракциями с наибольшим количеством воинов
                        if len(sorted_factions) >= 2 and sorted_factions[0][1] == sorted_factions[1][1]:
                            # Ничья - территория остается нейтральной, все воины погибают
                            self.logger.info(f"Ничья в битве за клетку ({x}, {y}). Территория остается нейтральной.")
                            
                            # Если клетка принадлежала какой-то фракции, освобождаем её
                            if cell.faction_id:
                                old_faction_id = cell.faction_id
                                cell.faction_id = None
                                db.session.add(cell)
                                self.logger.info(f"Клетка ({x}, {y}) освобождена от фракции {old_faction_id}")
                            
                            # Логируем потери всех фракций
                            for faction_id, warriors in faction_warriors.items():
                                self.logger.info(f"Фракция {faction_id} потеряла {warriors} воинов в битве за клетку ({x}, {y})")
                        
                        else:
                            # Есть победитель
                            winning_faction_id, max_warriors = sorted_factions[0]
                            
                            # Проверяем, достаточно ли воинов для захвата с учетом дополнительных требований
                            if max_warriors <= additional_warriors_required:
                                self.logger.info(f"Недостаточно воинов для захвата клетки ({x}, {y}). Требуется минимум {additional_warriors_required + 1} воинов.")
                                
                                # Территория остается нейтральной, все воины погибают
                                if cell.faction_id:
                                    old_faction_id = cell.faction_id
                                    cell.faction_id = None
                                    db.session.add(cell)
                                    self.logger.info(f"Клетка ({x}, {y}) освобождена от фракции {old_faction_id}")
                                
                                # Логируем потери всех фракций
                                for faction_id, warriors in faction_warriors.items():
                                    self.logger.info(f"Фракция {faction_id} потеряла {warriors} воинов в битве за клетку ({x}, {y})")
                                
                                continue
                            
                            # Получаем фракцию победителя
                            winning_faction = Faction.query.get(winning_faction_id)
                            if not winning_faction:
                                self.logger.warning(f"Фракция с ID {winning_faction_id} не найдена")
                                continue
                            
                            # Рассчитываем оставшихся воинов
                            # Если есть вторая по силе фракция, то остаются воины, равные разнице
                            # между воинами победителя и второй фракции
                            remaining_warriors = 0
                            if len(sorted_factions) >= 2:
                                second_faction_warriors = sorted_factions[1][1]
                                remaining_warriors = max(0, max_warriors - second_faction_warriors)
                            else:
                                # Если нет второй фракции, то остаются все воины
                                remaining_warriors = max_warriors
                            
                            # Учитываем дополнительные требования для захвата
                            remaining_warriors = max(0, remaining_warriors - additional_warriors_required)
                            
                            # Захватываем клетку
                            old_faction_id = cell.faction_id
                            cell.faction_id = winning_faction_id
                            db.session.add(cell)
                            
                            # Возвращаем оставшихся воинов победившей фракции
                            if remaining_warriors > 0:
                                winning_faction.warriors = min(winning_faction.warriors + remaining_warriors, winning_faction.max_warriors)
                                self.logger.info(f"Возвращено {remaining_warriors} воинов фракции {winning_faction_id}")
                            
                            if old_faction_id:
                                self.logger.info(f"Фракция {winning_faction_id} захватила клетку ({x}, {y}) у фракции {old_faction_id}")
                            else:
                                self.logger.info(f"Фракция {winning_faction_id} захватила пустую клетку ({x}, {y})")
                            
                            # Логируем потери
                            lost_warriors = max_warriors - remaining_warriors
                            self.logger.info(f"Фракция {winning_faction_id} отправила {max_warriors} воинов, потеряла {lost_warriors}, осталось: {remaining_warriors}")
                            
                            # Логируем потери других фракций
                            for faction_id, warriors in faction_warriors.items():
                                if faction_id != winning_faction_id:
                                    self.logger.info(f"Фракция {faction_id} потеряла {warriors} воинов в битве за клетку ({x}, {y})")
                
                db.session.commit()
                self.logger.info("Обработка захватов клеток завершена")
            except Exception as e:
                self.logger.error(f"Ошибка при обработке захватов клеток: {str(e)}")
                db.session.rollback()
    
    def _process_buildings(self):
        """Обрабатывает строительство зданий в конце хода"""
        with self.app.app_context():
            try:
                # Получаем все действия строительства для текущего хода
                build_actions = UserAction.query.filter_by(
                    action_type='build',
                    turn=self.current_turn
                ).all()
                
                self.logger.info(f"Обработка строительства зданий: найдено {len(build_actions)} действий")
                
                for action in build_actions:
                    x = action.target_x
                    y = action.target_y
                    building_type = action.building_type
                    user = action.user
                    
                    # Получаем клетку
                    cell = Cell.query.filter_by(x=x, y=y).first()
                    if not cell:
                        self.logger.warning(f"Клетка с координатами ({x}, {y}) не найдена")
                        continue
                    
                    # Проверяем, что клетка принадлежит фракции пользователя
                    if not cell.faction_id or cell.faction_id != user.faction_id:
                        self.logger.warning(f"Клетка ({x}, {y}) не принадлежит фракции {user.faction_id}")
                        continue
                    
                    # Проверяем, что на клетке нет здания
                    if cell.building_type:
                        self.logger.warning(f"На клетке ({x}, {y}) уже есть здание {cell.building_type}")
                        continue
                    
                    # Строим здание
                    cell.building_type = building_type
                    
                    # Создаем объект здания в базе данных
                    building_enum = None
                    try:
                        building_enum = BuildingType[building_type]
                    except KeyError:
                        self.logger.warning(f"Неизвестный тип здания: {building_type}")
                        continue
                    
                    building = Building(type=building_enum, level=1, cell=cell)
                    db.session.add(building)
                    
                    self.logger.info(f"Построено здание {building_type} на клетке ({x}, {y}) для фракции {user.faction_id}")
                
                db.session.commit()
                self.logger.info("Обработка строительства зданий завершена")
            except Exception as e:
                self.logger.error(f"Ошибка при обработке строительства зданий: {str(e)}")
                db.session.rollback()
    
    def _update_faction_resources(self):
        """Обновляет ресурсы всех фракций"""
        with self.app.app_context():
            try:
                factions = Faction.query.all()
                current_turn = self.current_turn  # Используем текущий ход напрямую
                
                for faction in factions:
                    # Получаем всех пользователей фракции
                    faction_users = User.query.filter_by(faction_id=faction.id).all()
                    
                    # Получаем все клетки фракции
                    faction_cells = Cell.query.filter_by(faction_id=faction.id).all()
                    territories_count = len(faction_cells)
                    
                    # Сохраняем старые значения для логирования
                    old_gold = faction.gold
                    old_wood = faction.wood
                    old_stone = faction.stone
                    old_ore = faction.ore
                    old_warriors = faction.warriors
                    old_max_gold = faction.max_gold
                    old_max_wood = faction.max_wood
                    old_max_stone = faction.max_stone
                    old_max_ore = faction.max_ore
                    old_max_warriors = faction.max_warriors
                    
                    # Устанавливаем базовые максимальные значения ресурсов
                    faction.max_gold = 100
                    faction.max_wood = 50
                    faction.max_stone = 50
                    faction.max_ore = 50
                    faction.max_warriors = 10
                    
                    # Обновляем максимальные значения ресурсов на основе зданий
                    total_storage_bonus = 0
                    total_warrior_capacity = 0
                    
                    # Дополнительный доход от зданий
                    building_income = {
                        'gold': 0,
                        'wood': 0,
                        'stone': 0,
                        'ore': 0
                    }
                    
                    for cell in faction_cells:
                        if cell.building_type:
                            # Добавляем бонус к хранилищу от зданий
                            storage_bonus = 10  # Базовый бонус к хранилищу
                            total_storage_bonus += storage_bonus
                            
                            # Добавляем вместимость воинов от зданий
                            warrior_capacity = 5  # Базовая вместимость воинов
                            total_warrior_capacity += warrior_capacity
                            
                            # Добавляем доход от зданий (+3 к соответствующему ресурсу)
                            if cell.building_type == BuildingType.SAWMILL.value:
                                building_income['wood'] += 3
                            elif cell.building_type == BuildingType.QUARRY.value:
                                building_income['stone'] += 3
                            elif cell.building_type == BuildingType.MINE.value:
                                building_income['ore'] += 3
                    
                    # Применяем бонусы к максимальным значениям ресурсов
                    faction.max_gold += total_storage_bonus
                    faction.max_wood += total_storage_bonus
                    faction.max_stone += total_storage_bonus
                    faction.max_ore += total_storage_bonus
                    faction.max_warriors += total_warrior_capacity
                    
                    # Базовый прирост ресурсов
                    base_income = {
                        'gold': 1,  # Базовый прирост золота
                        'wood': 3,
                        'stone': 3,
                        'ore': 3
                    }
                    
                    # Обновляем базовые ресурсы с учетом дохода от зданий
                    faction.wood = min(faction.wood + base_income['wood'] + building_income['wood'], faction.max_wood)
                    faction.stone = min(faction.stone + base_income['stone'] + building_income['stone'], faction.max_stone)
                    faction.ore = min(faction.ore + base_income['ore'] + building_income['ore'], faction.max_ore)
                    
                    # Обновляем золото: базовый прирост + 1 за каждую территорию + доход от зданий
                    gold_from_territories = territories_count  # +1 за каждую территорию
                    
                    # Проверяем наличие клеток с бонусами к ресурсам
                    resource_bonus = {
                        'gold': 0,
                        'wood': 0,
                        'stone': 0,
                        'ore': 0
                    }
                    
                    # Координаты клеток с бонусами к ресурсам
                    gold_bonus_cell = (1, 3)
                    wood_bonus_cell = (3, 1)
                    ore_bonus_cell = (3, 5)
                    stone_bonus_cell = (5, 3)
                    warriors_bonus_cell = (3, 3)  # Центральная клетка с бонусом к воинам
                    
                    # Проверяем, владеет ли фракция клетками с бонусами
                    for cell in faction_cells:
                        if (cell.x, cell.y) == gold_bonus_cell:
                            # Бонус +30% к общему доходу золота
                            resource_bonus['gold'] = 0.3 * (base_income['gold'] + gold_from_territories + building_income['gold'])
                            self.logger.info(f"Фракция {faction.name} получает бонус +30% к золоту от клетки {gold_bonus_cell}")
                        elif (cell.x, cell.y) == wood_bonus_cell:
                            # Бонус +30% к общему доходу дерева
                            resource_bonus['wood'] = 0.3 * (base_income['wood'] + building_income['wood'])
                            self.logger.info(f"Фракция {faction.name} получает бонус +30% к дереву от клетки {wood_bonus_cell}")
                        elif (cell.x, cell.y) == ore_bonus_cell:
                            # Бонус +30% к общему доходу руды
                            resource_bonus['ore'] = 0.3 * (base_income['ore'] + building_income['ore'])
                            self.logger.info(f"Фракция {faction.name} получает бонус +30% к руде от клетки {ore_bonus_cell}")
                        elif (cell.x, cell.y) == stone_bonus_cell:
                            # Бонус +30% к общему доходу камня
                            resource_bonus['stone'] = 0.3 * (base_income['stone'] + building_income['stone'])
                            self.logger.info(f"Фракция {faction.name} получает бонус +30% к камню от клетки {stone_bonus_cell}")
                        elif (cell.x, cell.y) == warriors_bonus_cell:
                            # Бонус к боевой мощи при захватах и защитах (логируем, но не меняем максимум воинов)
                            self.logger.info(f"Фракция {faction.name} получает бонус +30% к боевой мощи от клетки {warriors_bonus_cell}")
                    
                    # Округляем бонусы до целых чисел
                    for resource in resource_bonus:
                        resource_bonus[resource] = int(resource_bonus[resource])
                    
                    # Подсчитываем общее количество воинов, включая отправленных на захват и защиту
                    total_warriors = faction.warriors
                    
                    # Получаем воинов, отправленных на захват и защиту
                    warriors_sent_to_capture = 0
                    warriors_sent_to_defend = 0
                    
                    for user in faction_users:
                        # Воины, отправленные на захват
                        capture_actions = UserAction.query.filter_by(
                            user_id=user.id,
                            action_type=ActionType.CAPTURE_CELL.value,
                            turn=current_turn
                        ).all()
                        
                        for action in capture_actions:
                            if action.warriors:
                                warriors_sent_to_capture += action.warriors
                        
                        # Воины, отправленные на защиту
                        defend_actions = UserAction.query.filter_by(
                            user_id=user.id,
                            action_type=ActionType.DEFEND_CELL.value,
                            turn=current_turn
                        ).all()
                        
                        for action in defend_actions:
                            if action.warriors:
                                warriors_sent_to_defend += action.warriors
                    
                    # Общее количество воинов, включая отправленных
                    total_warriors += warriors_sent_to_capture + warriors_sent_to_defend
                    
                    # Списываем золото за содержание всех воинов (0.5 золота за каждого воина)
                    gold_for_warriors = total_warriors * 0.5  # Снижена стоимость содержания
                    
                    # Округляем стоимость содержания до целого числа
                    gold_for_warriors = int(gold_for_warriors)
                    
                    # Итоговое изменение золота: прирост минус расходы на воинов
                    gold_change = base_income['gold'] + gold_from_territories + building_income['gold'] + resource_bonus['gold'] - gold_for_warriors
                    
                    # Обновляем золото с учетом расходов на воинов
                    faction.gold = max(0, min(faction.gold + gold_change, faction.max_gold))
                    
                    # Если золота не хватает на содержание воинов, уменьшаем их количество
                    if faction.gold == 0 and gold_change < 0:
                        # Определяем, сколько воинов нужно распустить
                        warriors_to_dismiss = abs(gold_change)
                        self.logger.info(f"Фракция {faction.name} не может содержать {warriors_to_dismiss} воинов из-за нехватки золота")
                        
                        # Сначала уменьшаем количество воинов в резерве
                        if faction.warriors > 0:
                            dismissed_from_reserve = min(faction.warriors, warriors_to_dismiss)
                            faction.warriors -= dismissed_from_reserve
                            warriors_to_dismiss -= dismissed_from_reserve
                            self.logger.info(f"Фракция {faction.name} распустила {dismissed_from_reserve} воинов из резерва")
                        
                        # Если нужно распустить еще воинов, уменьшаем количество воинов, отправленных на защиту
                        if warriors_to_dismiss > 0 and warriors_sent_to_defend > 0:
                            # Получаем все действия защиты для этой фракции
                            defend_actions = []
                            for user in faction_users:
                                user_defend_actions = UserAction.query.filter_by(
                                    user_id=user.id,
                                    action_type=ActionType.DEFEND_CELL.value,
                                    turn=current_turn
                                ).all()
                                defend_actions.extend(user_defend_actions)
                            
                            # Сортируем действия по количеству воинов (сначала с наибольшим количеством)
                            defend_actions.sort(key=lambda a: a.warriors if a.warriors else 0, reverse=True)
                            
                            # Уменьшаем количество воинов в действиях защиты
                            dismissed_from_defend = 0
                            for action in defend_actions:
                                if warriors_to_dismiss <= 0:
                                    break
                                
                                if action.warriors:
                                    warriors_to_remove = min(action.warriors, warriors_to_dismiss)
                                    action.warriors -= warriors_to_remove
                                    warriors_to_dismiss -= warriors_to_remove
                                    dismissed_from_defend += warriors_to_remove
                                    
                                    # Если все воины были удалены, отменяем действие
                                    if action.warriors <= 0:
                                        db.session.delete(action)
                            
                            if dismissed_from_defend > 0:
                                self.logger.info(f"Фракция {faction.name} потеряла {dismissed_from_defend} воинов, отправленных на защиту")
                        
                        # Если нужно распустить еще воинов, уменьшаем количество воинов, отправленных на захват
                        if warriors_to_dismiss > 0 and warriors_sent_to_capture > 0:
                            # Получаем все действия захвата для этой фракции
                            capture_actions = []
                            for user in faction_users:
                                user_capture_actions = UserAction.query.filter_by(
                                    user_id=user.id,
                                    action_type=ActionType.CAPTURE_CELL.value,
                                    turn=current_turn
                                ).all()
                                capture_actions.extend(user_capture_actions)
                            
                            # Сортируем действия по количеству воинов (сначала с наибольшим количеством)
                            capture_actions.sort(key=lambda a: a.warriors if a.warriors else 0, reverse=True)
                            
                            # Уменьшаем количество воинов в действиях захвата
                            dismissed_from_capture = 0
                            for action in capture_actions:
                                if warriors_to_dismiss <= 0:
                                    break
                                
                                if action.warriors:
                                    warriors_to_remove = min(action.warriors, warriors_to_dismiss)
                                    action.warriors -= warriors_to_remove
                                    warriors_to_dismiss -= warriors_to_remove
                                    dismissed_from_capture += warriors_to_remove
                                    
                                    # Если все воины были удалены, отменяем действие
                                    if action.warriors <= 0:
                                        db.session.delete(action)
                            
                            if dismissed_from_capture > 0:
                                self.logger.info(f"Фракция {faction.name} потеряла {dismissed_from_capture} воинов, отправленных на захват")
                        
                        # Добавляем запись в лог фракции о потере воинов
                        log_entry = FactionLog(
                            faction_id=faction.id,
                            turn=current_turn,
                            message=f"Из-за нехватки золота фракция потеряла {abs(gold_change)} воинов",
                            timestamp=datetime.utcnow()
                        )
                        db.session.add(log_entry)
                    
                    # Проверяем наличие казармы для получения воинов
                    has_barracks = False
                    for cell in faction_cells:
                        if cell.building and cell.building.type == BuildingType.BARRACKS:
                            has_barracks = True
                            break
                    
                    # Если есть казарма, добавляем 1 воина за ход
                    if has_barracks:
                        faction.warriors = min(faction.warriors + 1, faction.max_warriors)
                    
                    # Добавляем ресурсы от зданий
                    for cell in faction_cells:
                        if cell.building:
                            production = cell.building.get_production()
                            for resource, amount in production.items():
                                if resource in ['wood', 'stone', 'ore', 'gold']:
                                    current = getattr(faction, resource)
                                    maximum = getattr(faction, f'max_{resource}')
                                    setattr(faction, resource, min(current + amount, maximum))
                    
                    # Добавляем бонусы от специальных клеток
                    faction.wood = min(faction.wood + resource_bonus['wood'], faction.max_wood)
                    faction.stone = min(faction.stone + resource_bonus['stone'], faction.max_stone)
                    faction.ore = min(faction.ore + resource_bonus['ore'], faction.max_ore)
                    
                    self.logger.info(f"[GameManager] Фракция {faction.name}:")
                    self.logger.info(f"  - Всего территорий: {territories_count}")
                    self.logger.info(f"  - Золото: {old_gold} -> {faction.gold} (+{faction.gold - old_gold}), макс: {old_max_gold} -> {faction.max_gold}")
                    self.logger.info(f"  - Дерево: {old_wood} -> {faction.wood} (+{faction.wood - old_wood}), макс: {old_max_wood} -> {faction.max_wood}")
                    self.logger.info(f"  - Камень: {old_stone} -> {faction.stone} (+{faction.stone - old_stone}), макс: {old_max_stone} -> {faction.max_stone}")
                    self.logger.info(f"  - Руда: {old_ore} -> {faction.ore} (+{faction.ore - old_ore}), макс: {old_max_ore} -> {faction.max_ore}")
                    self.logger.info(f"  - Воины: {old_warriors} -> {faction.warriors} (+{faction.warriors - old_warriors}), макс: {old_max_warriors} -> {faction.max_warriors}")
                    self.logger.info(f"  - Воины на захвате: {warriors_sent_to_capture}")
                    self.logger.info(f"  - Воины на защите: {warriors_sent_to_defend}")
                    self.logger.info(f"  - Общее количество воинов: {total_warriors}")
                    self.logger.info(f"  - Расходы на воинов: {gold_for_warriors} золота")
                    
                    # Логируем изменения ресурсов
                    self.logger.info(f"Обновление ресурсов для фракции {faction.name}:")
                    self.logger.info(f"  Золото: {old_gold} -> {faction.gold} (изменение: {faction.gold - old_gold})")
                    self.logger.info(f"  Дерево: {old_wood} -> {faction.wood} (изменение: {faction.wood - old_wood})")
                    self.logger.info(f"  Камень: {old_stone} -> {faction.stone} (изменение: {faction.stone - old_stone})")
                    self.logger.info(f"  Руда: {old_ore} -> {faction.ore} (изменение: {faction.ore - old_ore})")
                    self.logger.info(f"  Воины: {old_warriors} -> {faction.warriors} (изменение: {faction.warriors - old_warriors})")
                    
                    # Логируем доход от зданий
                    if any(value > 0 for value in building_income.values()):
                        self.logger.info(f"  Доход от зданий: Золото +{building_income['gold']}, Дерево +{building_income['wood']}, Камень +{building_income['stone']}, Руда +{building_income['ore']}")
                    
                    # Логируем бонусы от специальных клеток
                    if any(value > 0 for value in resource_bonus.values()):
                        self.logger.info(f"  Бонусы от специальных клеток: Золото +{resource_bonus['gold']}, Дерево +{resource_bonus['wood']}, Камень +{resource_bonus['stone']}, Руда +{resource_bonus['ore']}")
                    
                    db.session.add(faction)
                
                db.session.commit()
                self.logger.info("Ресурсы всех фракций обновлены")
            except Exception as e:
                db.session.rollback()
                self.logger.error(f"Ошибка при обновлении ресурсов фракций: {str(e)}")
    
    def get_turn_info(self):
        """Возвращает информацию о текущем ходе"""
        # Этот метод не обращается к базе данных, поэтому контекст приложения не требуется
        
        if not self.app:
            return {
                'seconds_left': self.TURN_DURATION,
                'turn_duration': self.TURN_DURATION,
                'is_running': False,
                'current_turn': self.current_turn
            }
        
        if not self.turn_start_time or not self.is_running:
            return {
                'seconds_left': self.TURN_DURATION,
                'turn_duration': self.TURN_DURATION,
                'is_running': self.is_running,
                'current_turn': self.current_turn
            }
        
        now = datetime.utcnow()
        elapsed = (now - self.turn_start_time).total_seconds()
        seconds_left = max(0, self.TURN_DURATION - elapsed)
        
        return {
            'seconds_left': int(seconds_left),
            'turn_duration': self.TURN_DURATION,
            'is_running': self.is_running,
            'current_turn': self.current_turn
        }
    
    def _initialize_faction_resources(self):
        """Инициализирует стартовые ресурсы для всех фракций"""
        try:
            with self.app.app_context():
                with db.session.begin():
                    factions = Faction.query.all()
                    
                    for faction in factions:
                        # Сохраняем старые значения для логирования
                        old_gold = faction.gold
                        old_wood = faction.wood
                        old_stone = faction.stone
                        old_ore = faction.ore
                        old_warriors = faction.warriors
                        
                        # Устанавливаем стартовые значения ресурсов
                        faction.gold = 15  # Начальное золото - 15 единиц
                        faction.max_gold = 100  # Базовое максимальное значение
                        
                        faction.wood = 10  # Начальное дерево - 10 единиц
                        faction.max_wood = 50
                        
                        faction.stone = 10  # Начальный камень - 10 единиц
                        faction.max_stone = 50
                        
                        faction.ore = 10  # Начальная руда - 10 единиц
                        faction.max_ore = 50
                        
                        faction.warriors = 2  # Начальное количество воинов - 2
                        faction.max_warriors = 20
                        
                        db.session.add(faction)
                        
                        self.logger.info(f"[GameManager] Инициализация ресурсов фракции {faction.name}:")
                        self.logger.info(f"  - Золото: {old_gold} -> {faction.gold}")
                        self.logger.info(f"  - Дерево: {old_wood} -> {faction.wood}")
                        self.logger.info(f"  - Камень: {old_stone} -> {faction.stone}")
                        self.logger.info(f"  - Руда: {old_ore} -> {faction.ore}")
                        self.logger.info(f"  - Воины: {old_warriors} -> {faction.warriors}")
                    
                    self.logger.info("[GameManager] Стартовые ресурсы фракций установлены")
        except Exception as e:
            self.logger.error(f"[GameManager] Ошибка при инициализации ресурсов фракций: {str(e)}")
            with self.app.app_context():
                db.session.rollback()
    
    def is_corner_cell(self, x, y):
        """Проверяет, является ли клетка угловой (с замком)"""
        corners = [(0, 0), (0, 6), (6, 0), (6, 6)]
        return (x, y) in corners
        
    def is_connected_to_castle(self, faction_id):
        """Проверяет связность территории фракции с замком
        
        Возвращает словарь, где ключи - это координаты клеток (x, y), 
        а значения - булевы значения, указывающие, связана ли клетка с замком
        """
        with self.app.app_context():
            try:
                # Получаем все клетки фракции
                faction_cells = Cell.query.filter_by(faction_id=faction_id).all()
                
                # Если нет клеток, возвращаем пустой словарь
                if not faction_cells:
                    return {}
                
                # Находим замок (угловую клетку)
                castle_cell = None
                for cell in faction_cells:
                    if self.is_corner_cell(cell.x, cell.y):
                        castle_cell = cell
                        break
                
                # Если замок не найден, считаем, что ни одна клетка не связана
                if not castle_cell:
                    return {(cell.x, cell.y): False for cell in faction_cells}
                
                # Используем поиск в ширину для определения связности
                connected = {(cell.x, cell.y): False for cell in faction_cells}
                connected[(castle_cell.x, castle_cell.y)] = True
                
                queue = [(castle_cell.x, castle_cell.y)]
                visited = set([(castle_cell.x, castle_cell.y)])
                
                # Направления для соседних клеток (вверх, вправо, вниз, влево)
                directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
                
                while queue:
                    x, y = queue.pop(0)
                    
                    # Проверяем соседние клетки
                    for dx, dy in directions:
                        nx, ny = x + dx, y + dy
                        
                        # Проверяем, что координаты в пределах карты
                        if nx < 0 or nx > 6 or ny < 0 or ny > 6:
                            continue
                        
                        # Проверяем, что клетка принадлежит этой фракции и еще не посещена
                        if (nx, ny) in connected and (nx, ny) not in visited:
                            connected[(nx, ny)] = True
                            queue.append((nx, ny))
                            visited.add((nx, ny))
                
                return connected
            except Exception as e:
                self.logger.error(f"Ошибка при проверке связности территории: {str(e)}")
                return {}
    
    def get_required_warriors_for_capture(self, cell):
        """Определяет, сколько дополнительных воинов требуется для захвата клетки
        
        Если на нейтральной клетке есть постройка, требуется дополнительное количество воинов,
        которое хранится в поле neutral_defenders
        """
        # Если клетка не нейтральная, дополнительные воины не требуются
        if cell.faction_id is not None:
            return 0
            
        # Если на нейтральной клетке есть постройка, используем сохраненное значение защитников
        if cell.building_type is not None:
            # Если значение защитников еще не установлено, генерируем его
            if cell.neutral_defenders is None:
                cell.neutral_defenders = random.randint(1, 3)
                db.session.add(cell)
                db.session.commit()
                self.logger.info(f"Установлено {cell.neutral_defenders} защитников для нейтральной клетки ({cell.x}, {cell.y}) с постройкой {cell.building_type}")
            
            return cell.neutral_defenders
            
        # В остальных случаях дополнительные воины не требуются
        return 0

    def _check_territory_connectivity(self):
        """Проверяет связность территорий и освобождает несвязанные клетки"""
        with self.app.app_context():
            try:
                factions = Faction.query.all()
                
                for faction in factions:
                    # Получаем все клетки фракции
                    faction_cells = Cell.query.filter_by(faction_id=faction.id).all()
                    
                    # Проверяем связность территории
                    connected = self.is_connected_to_castle(faction.id)
                    
                    for cell in faction_cells:
                        # Пропускаем угловые клетки (замки)
                        if self.is_corner_cell(cell.x, cell.y):
                            continue
                            
                        # Проверяем, связана ли клетка с замком
                        if (cell.x, cell.y) in connected and connected[(cell.x, cell.y)]:
                            # Клетка связана с замком
                            continue
                        
                        # Клетка не связана с замком - освобождаем её
                        self.logger.info(f"Клетка ({cell.x}, {cell.y}) фракции {faction.id} не связана с замком и будет освобождена")
                        cell.faction_id = None
                        db.session.add(cell)
                
                db.session.commit()
                self.logger.info("Проверка связности территорий завершена")
            except Exception as e:
                self.logger.error(f"Ошибка при проверке связности территорий: {str(e)}")
                db.session.rollback() 