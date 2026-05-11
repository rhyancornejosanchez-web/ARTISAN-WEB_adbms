from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from models import db, User, Order
from views import views_bp
from cli_command import register_cli_commands
import os

# --- Initialize Flask App ---
app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-change-in-production')

# --- MySQL Database Connection ---
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'rhyan12')  # ← change this
MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DB = os.environ.get('MYSQL_DB', 'artisan_db')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True  # ← add this line
app.config['UPLOAD_FOLDER'] = 'static/artisans'

# --- Initialize Extensions ---
db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'views.login'

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Register Blueprints & CLI Commands ---
app.register_blueprint(views_bp)
register_cli_commands(app)

# --- Auto-create DB tables if they don't exist ---
with app.app_context():
    db.create_all()

# --- Inject new order count for shop owner nav badge ---
@app.context_processor
def inject_new_orders_count():
    new_orders_count = 0
    shipped_count = 0
    if current_user.is_authenticated:
        if current_user.shops:
            shop_id = current_user.shops[0].shop_id
            new_orders_count = Order.query.filter_by(shop_id=shop_id, status='placed').count()
        shipped_count = Order.query.filter_by(
            user_id=current_user.user_id,
            status='shipped',
            seen_by_buyer=False
        ).count()
    return dict(new_orders_count=new_orders_count, shipped_count=shipped_count)

# --- Routes ---
@app.route("/")
def home():
    if current_user.is_authenticated:
        return render_template("home.html")
    return redirect(url_for("views.landing"))

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)