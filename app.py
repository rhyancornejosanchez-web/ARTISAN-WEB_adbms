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

# --- Ensure instance folder exists ---
os.makedirs(app.instance_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'Web_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    return redirect(url_for("views.login"))

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)