from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize DB
db = SQLAlchemy()

# --- NEW ADDRESS TABLE ---
class Address(db.Model):
    __tablename__ = 'addresses'

    address_id = db.Column(db.Integer, primary_key=True)
    # Foreign Key connecting to User (One-to-One)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), unique=True, nullable=False)
    
    street_address = db.Column(db.String(150), nullable=False, default="N/A")
    city = db.Column(db.String(100), nullable=False, default="N/A")
    province = db.Column(db.String(100), nullable=False, default="N/A")
    zip_code = db.Column(db.String(20), nullable=False, default="0000")

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    # Primary Key
    user_id = db.Column(db.Integer, primary_key=True)
    
    # Auth Data
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    # Profile Data (Address removed and moved to separate table)
    first_name = db.Column(db.String(150), nullable=True)
    last_name = db.Column(db.String(150), nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    birthdate = db.Column(db.Date, nullable=True)
    contact_num = db.Column(db.String(20), nullable=False, default="N/A")
    bio = db.Column(db.Text, nullable=True)
    profile_img_url = db.Column(db.String(250), nullable=True, default='images/default.png')


    # Relationships
    
    # 1. Address Relationship (One-to-One)
    # uselist=False ensures it behaves like a single object (user.address.city) not a list
    address = db.relationship('Address', backref='user', uselist=False, cascade="all, delete-orphan", lazy=True)

    # 2. Shop Relationship
    shops = db.relationship('Shop', backref='owner', lazy=True)

    def get_id(self):
        return str(self.user_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Shop(db.Model):
    __tablename__ = 'shops'
    
    shop_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Foreign Key to User
    owner_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)

    # Self-Referential Key for Branches/Locations
    parent_shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=True)
    
    # One Shop has many items
    items = db.relationship('Item', backref='shop', lazy=True)


class Item(db.Model):
    __tablename__ = 'items'
    
    item_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer)
    img_url = db.Column(db.String(250), nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    # Foreign Key to Shop
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)

    def __repr__(self):
        return f'<Item {self.name}>'
    
    def formatted_price(self):
        return f"₱{self.price:,.2f}"

class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    # Matching your form validator (max=300)
    name = db.Column(db.String(300), nullable=False, unique=True)
    code = db.Column(db.String(50))
    
    # Relationship: Allows you to type item.category.name or category.items
    items = db.relationship('Item', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.item_id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref='cart_items')
    item = db.relationship('Item', backref='cart_entries')



class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey("shops.shop_id"), nullable=False)
    status = db.Column(db.String(20), default="placed")  # placed, shipped, received, canceled
    location = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    seen_by_buyer = db.Column(db.Boolean, default=True)  # False = new shipped notification

    order_items = db.relationship("OrderItem", backref="order", lazy=True)
    shop = db.relationship("Shop", backref="orders")
    user = db.relationship("User", backref="orders")



class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.item_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    item = db.relationship("Item")


class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.shop_id'), nullable=False)
    value = db.Column(db.Integer, nullable=False)

    shop = db.relationship('Shop', backref='ratings')
    user = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'shop_id', name='uq_user_shop_rating'),
    )


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(300))   #store path to uploaded image or video
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="blog_posts")








