from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from models import db, User
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

# --- Routes ---
@app.route("/")
def home():
    return render_template("home.html")

# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True)