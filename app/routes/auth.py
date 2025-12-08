from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User, Faction
from app import db
from werkzeug.security import generate_password_hash

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        full_name = request.form['full_name']
        age = request.form['age']
        faction_id = request.form['faction_id']
        
        error = None
        
        if not username:
            error = 'Требуется указать имя пользователя.'
        elif not password:
            error = 'Требуется указать пароль.'
        elif not email:
            error = 'Требуется указать email.'
        elif not full_name:
            error = 'Требуется указать ФИО.'
        elif not age:
            error = 'Требуется указать возраст.'
        elif User.query.filter_by(username=username).first():
            error = 'Пользователь {} уже зарегистрирован.'.format(username)
        
        if error is None:
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                age=int(age),
                faction_id=faction_id
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Регистрация успешна! Ожидайте одобрения администратором.')
            return redirect(url_for('auth.login'))
        
        flash(error)
    
    factions = Faction.query.all()
    return render_template('auth/register.html', factions=factions)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        
        user = User.query.filter_by(username=username).first()
        
        if user is None:
            error = 'Неверное имя пользователя.'
        elif not user.check_password(password):
            error = 'Неверный пароль.'
        elif not user.is_approved:
            error = 'Ваша учетная запись еще не одобрена администратором.'
        
        if error is None:
            login_user(user)
            return redirect(url_for('main.index'))
        
        flash(error)
    
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id):
    if not current_user.is_admin:
        flash('У вас нет прав для выполнения этого действия.')
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'Пользователь {user.username} одобрен.')
    return redirect(url_for('admin.user_list')) 