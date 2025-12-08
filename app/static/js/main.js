function initiateTransfer() {
    // Обновляем ресурсы в модальном окне
    updateTransferModalResources();
    
    // Открываем модальное окно
    const transferModal = new bootstrap.Modal(document.getElementById('transferModal'));
    transferModal.show();
    
    // Добавляем небольшую задержку и повторно обновляем значения после открытия модального окна
    setTimeout(updateTransferModalResources, 300);
}

function showTransferModal(x, y) {
    document.getElementById('transfer-x').value = x;
    document.getElementById('transfer-y').value = y;
    
    // Обновляем ресурсы в модальном окне
    updateTransferModalResources();
    
    // Открываем модальное окно
    const modal = new bootstrap.Modal(document.getElementById('transferModal'));
    modal.show();
    
    // Добавляем небольшую задержку и повторно обновляем значения после открытия модального окна
    setTimeout(updateTransferModalResources, 300);
}

// Функция для обновления доступных ресурсов в модальном окне передачи
function updateTransferModalResources() {
    // Получаем текущие ресурсы фракции напрямую из элементов на странице
    const goldElement = document.getElementById('gold-amount');
    const woodElement = document.getElementById('wood-amount');
    const stoneElement = document.getElementById('stone-amount');
    const oreElement = document.getElementById('ore-amount');
    
    if (!goldElement || !woodElement || !stoneElement || !oreElement) {
        console.error('Не найдены элементы с ресурсами на странице');
        return;
    }
    
    const gold = goldElement.textContent;
    const wood = woodElement.textContent;
    const stone = stoneElement.textContent;
    const ore = oreElement.textContent;
    
    console.log('Ресурсы для обновления модального окна:', { gold, wood, stone, ore });
    
    // Обновляем отображение доступных ресурсов в модальном окне
    const availableGoldElement = document.getElementById('available-gold');
    const availableWoodElement = document.getElementById('available-wood');
    const availableStoneElement = document.getElementById('available-stone');
    const availableOreElement = document.getElementById('available-ore');
    
    if (availableGoldElement) availableGoldElement.textContent = gold;
    if (availableWoodElement) availableWoodElement.textContent = wood;
    if (availableStoneElement) availableStoneElement.textContent = stone;
    if (availableOreElement) availableOreElement.textContent = ore;
    
    // Обновляем максимальные значения для полей ввода
    const transferGoldElement = document.getElementById('transfer-gold');
    const transferWoodElement = document.getElementById('transfer-wood');
    const transferStoneElement = document.getElementById('transfer-stone');
    const transferOreElement = document.getElementById('transfer-ore');
    
    if (transferGoldElement) transferGoldElement.max = gold;
    if (transferWoodElement) transferWoodElement.max = wood;
    if (transferStoneElement) transferStoneElement.max = stone;
    if (transferOreElement) transferOreElement.max = ore;
    
    console.log('Обновлены ресурсы в модальном окне передачи');
}

// Функция для инициализации обработчиков событий модальных окон
function initModalEventListeners() {
    // Обработчик события открытия модального окна передачи ресурсов
    const transferModal = document.getElementById('transferModal');
    if (transferModal) {
        transferModal.addEventListener('shown.bs.modal', function() {
            console.log('Модальное окно передачи ресурсов открыто, обновляем ресурсы');
            updateTransferModalResources();
        });
    }
    
    // Добавляем обработчики для всех модальных окон, чтобы исправить проблему с неактивной страницей
    const allModals = document.querySelectorAll('.modal');
    allModals.forEach(modal => {
        modal.addEventListener('hidden.bs.modal', function() {
            console.log('Модальное окно закрыто, проверяем наличие backdrop');
            // Проверяем, есть ли еще открытые модальные окна
            const openModals = document.querySelectorAll('.modal.show');
            if (openModals.length === 0) {
                // Если нет открытых модальных окон, удаляем backdrop вручную
                const backdrop = document.querySelector('.modal-backdrop');
                if (backdrop) {
                    backdrop.remove();
                }
                // Убираем класс modal-open с body
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }
        });
    });
}

// Инициализация при загрузке страницы
// Этот код уже есть в шаблоне index.html, поэтому комментируем его здесь
/*
document.addEventListener('DOMContentLoaded', function() {
    // Сначала инициализируем карту
    initMap();
    
    // Затем добавляем обработчики событий
    initEventListeners();
    
    // Инициализируем обработчики событий модальных окон
    initModalEventListeners();
    
    // Обновляем состояние игры через небольшую задержку, чтобы клетки успели создаться
    setTimeout(function() {
        updateGameState();
        
        // Устанавливаем интервал обновления состояния игры
        setInterval(updateGameState, 5000);
    }, 1000);
});
*/

// Инициализация карты
function initMap() {
    const mapContainer = document.querySelector('.map-container');
    if (!mapContainer) return;
    
    // Очищаем контейнер перед созданием новых элементов
    mapContainer.innerHTML = '';
    console.log('Очищен контейнер карты перед инициализацией');
    
    // Получаем данные карты
    fetch('/api/map')
        .then(response => response.json())
        .then(mapData => {
            console.log('Initial map data:', mapData);
            
            // Создаем клетки
            mapData.forEach(cell => {
                const cellElement = createCellElement(cell);
                
                // Добавляем обработчик клика для выбора клетки
                cellElement.addEventListener('click', function() {
                    // Заполняем поля в модальных окнах
                    document.querySelectorAll('#capture-x, #build-x').forEach(el => el.value = cell.x);
                    document.querySelectorAll('#capture-y, #build-y').forEach(el => el.value = cell.y);
                });
                
                // Добавляем клетку на карту
                mapContainer.appendChild(cellElement);
            });
        })
        .catch(error => console.error('Ошибка при инициализации карты:', error));
}