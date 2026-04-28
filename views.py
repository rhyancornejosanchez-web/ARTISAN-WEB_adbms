from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
import os
from forms import RegistrationForm, LoginForm, UserProfileForm, ShopForm, ItemForm, SearchForm, RatingForm, AddToCartForm, BlogPostForm
from models import db, User, Shop, Item, Address, Category, Rating, CartItem, Order, OrderItem, BlogPost
from utils import save_picture, save_profile_picture, get_or_create_category, save_file
from datetime import datetime


views_bp = Blueprint('views', __name__, url_prefix='/')


# ---------------------------------------------- AUTHENTICATION ROUTES ---------------------------------------------
# ----------- LOGIN -----------
@views_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if not user:
            flash("Username not found.", "warning")
            return redirect(url_for("views.login"))

        if not user.check_password(form.password.data):
            flash("Incorrect password.", "danger")
            return redirect(url_for("views.login"))

        login_user(user, remember=form.remember_me.data)
        flash("Login successfully!", "success")
        return redirect(url_for("home"))

    return render_template("login.html", form=form)
    
# ----------------------------------------------------- LOGOUT --------------------------------------------------------
@views_bp.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("views.login"))
    except Exception as e:
        # Rollback if any DB/session issue occurs
        db.session.rollback()
        current_app.logger.error(f"Logout error: {e}", exc_info=True)
        flash("An error occurred while logging out. Please try again.", "danger")
        return redirect(url_for("views.login"))

# --- SIGNUP ---
@views_bp.route('/signup', methods=['GET', 'POST'])
def sign_up():
    form = RegistrationForm()

    if form.validate_on_submit():
        try:
            # Check if username already exists
            user_exists = User.query.filter_by(username=form.username.data).first()
            if user_exists:
                flash("Username already exists.", "danger")
                return redirect(url_for("views.sign_up"))

            # Create new user
            new_user = User(username=form.username.data)
            new_user.set_password(form.password.data)

            db.session.add(new_user)
            db.session.commit()

            flash("Account created! Please log in.", "success")
            return redirect(url_for("views.login"))

        except Exception as e:
            # Rollback to avoid partial commits
            db.session.rollback()
            current_app.logger.error(f"Signup error: {e}", exc_info=True)
            flash("An unexpected error occurred. Please try again.", "danger")
            return redirect(url_for("views.sign_up"))

    # GET request or invalid form
    return render_template("signup.html", form=form)
# --------------------------------------------------  endfor --------------------------------------------------------



# --------------------------------------------- user profile action -------------------------------------------------------
@views_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    # Display the current user's profile, address, and blog posts
    user = current_user
    address = user.address 

    # Query blog posts for this user
    posts = BlogPost.query.filter_by(user_id=user.user_id).order_by(BlogPost.created_at.desc()).all()

    return render_template('profile.html', user=user, address=address, posts=posts)


# The Edit Profile Route
@views_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = current_user
    form = UserProfileForm(obj=user)

    if form.validate_on_submit():
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.gender = form.gender.data
        user.birthdate = form.birthdate.data
        user.contact_num = form.contact_num.data
        user.bio = form.bio.data

        # Handle profile image upload
        if form.profile_image.data:
            user.profile_img_url = save_profile_picture(form.profile_image.data)

        # Handle address
        if user.address:
            user.address.street_address = form.street_address.data
            user.address.city = form.city.data
            user.address.province = form.province.data
            user.address.zip_code = form.zip_code.data
        else:
            new_address = Address(
                user_id=user.user_id,
                street_address=form.street_address.data,
                city=form.city.data,
                province=form.province.data,
                zip_code=form.zip_code.data
            )
            db.session.add(new_address)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('views.profile'))

    return render_template('edit_profile.html', form=form, user=user)
# ---------------------------------------------------- endfor -------------------------------------------------







#_______________________________________________________________________________________________________________
# ------------------------------------ routes related to user created shop -------------------------------------
# --- READ: My Shop 
@views_bp.route('/myshop')
@login_required
def my_shop():
    try:
        # Ensure user has a shop
        if not current_user.shops or len(current_user.shops) == 0:
            flash("You don't have a shop yet.", "info")
            return redirect(url_for('home'))

        shop = current_user.shops[0]  
        items = getattr(shop, 'items', [])

        return render_template('my_shop.html', shop=shop, items=items)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading shop for user {current_user.id}: {e}")
        flash("An error occurred while loading your shop. Please try again.", "danger")
        return redirect(url_for('home'))


@views_bp.route('/create-shop', methods=['GET', 'POST'])
@login_required
def create_shop():
    # Check if user already has a shop
    if current_user.shops:
        flash("You already have a shop.", "info")
        return redirect(url_for('views.my_shop'))

    form = ShopForm()
    if form.validate_on_submit():
        new_shop = Shop(
            name=form.shop_name.data,
            description=form.shop_description.data,
            owner_id=current_user.user_id
        )
        try:
            db.session.add(new_shop)
            db.session.commit()
            flash('Shop created successfully!', 'success')
            return redirect(url_for('views.my_shop'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating shop: {e}")
            flash('An error occurred while creating your shop. Please try again.', 'danger')
            return redirect(url_for('views.create_shop'))
    elif form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", "danger")

    return render_template('create_shop.html', form=form)



@views_bp.route('/add-product', methods=['GET', 'POST'])
@login_required
def add_product():
    try:
        # Ensure user has a shop
        if not current_user.shops:
            flash("You must create a shop before adding products.", "warning")
            return redirect(url_for("views.create_shop"))

        shop = current_user.shops[0]
        form = ItemForm()

        if form.validate_on_submit():
            # Validation: prevent negative values
            if form.price.data < 0 or form.stock.data < 0:
                flash("Price and stock must be non-negative.", "danger")
                return redirect(url_for("views.add_product"))

            # 1. Handle Image
            image_file = save_picture(form.image.data) if form.image.data else 'products/default.jpg'

            # 2. Handle Category (String -> Object)
            cat_obj = get_or_create_category(form.category.data)

            new_item = Item(
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
                stock=form.stock.data,
                img_url=image_file,
                shop_id=shop.shop_id,
                category_id=cat_obj.id  # Link to category
            )

            db.session.add(new_item)
            db.session.commit()
            flash('Product added successfully!', 'success')
            return redirect(url_for('views.my_shop'))

        return render_template('manage_product.html', form=form, title="Add New Product")

    except Exception as e:
        db.session.rollback()  # rollback if commit fails
        current_app.logger.error(f"Error adding product: {e}")
        flash("An error occurred while adding the product.", "danger")
        return redirect(url_for('views.my_shop'))



#  UPDATE ROUTE 
@views_bp.route('/edit-product/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_product(item_id):
    try:
        item = Item.query.get_or_404(item_id)

        # Security Check: only shop owner can edit
        if item.shop.owner_id != current_user.user_id:
            abort(403)

        form = ItemForm()

        if form.validate_on_submit():
            item.name = form.name.data
            item.description = form.description.data
            item.price = form.price.data
            item.stock = form.stock.data

            # Update Category
            cat_obj = get_or_create_category(form.category.data)
            item.category_id = cat_obj.id

            # Handle image upload
            if form.image.data:
                item.img_url = save_picture(form.image.data)

            db.session.commit()
            flash('Product updated!', 'success')
            return redirect(url_for('views.my_shop'))

        elif request.method == 'GET':
            # Pre-fill form with existing values
            form.name.data = item.name
            form.description.data = item.description
            form.price.data = item.price
            form.stock.data = item.stock

            # Pre-fill category name
            if item.category:
                form.category.data = item.category.name

        return render_template('manage_product.html', form=form, title="Edit Product")

    except Exception as e:
        db.session.rollback()  # rollback if commit fails
        current_app.logger.error(f"Error editing product {item_id}: {e}")
        flash("An error occurred while updating the product.", "danger")
        return redirect(url_for('views.my_shop'))


#  DELETE: Delete Product
@views_bp.route('/delete-product/<int:item_id>', methods=['POST'])
@login_required
def delete_product(item_id):
    try:
        item = Item.query.get_or_404(item_id)

        # Security Check
        if item.shop.owner_id != current_user.user_id:
            abort(403)

        db.session.delete(item)
        db.session.commit()
        flash('Product deleted.', 'success')

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error deleting product {item_id}: {e}")
        flash("An error occurred while deleting the product.", "danger")

    return redirect(url_for('views.my_shop'))

# user shop dashboard
# user must have a shop to access dashboard
@views_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        if not current_user.shops:
            flash("You don't have a shop yet. Please create one first.", "warning")
            return redirect(url_for("views.create_shop"))

        shop = current_user.shops[0]

        total_items = (
            db.session.query(func.count(Item.item_id))
            .filter_by(shop_id=shop.shop_id)
            .scalar()
        )
        total_stock = (
            db.session.query(func.sum(Item.stock))
            .filter_by(shop_id=shop.shop_id)
            .scalar() or 0
        )
        total_value = (
            db.session.query(func.sum(Item.price * Item.stock))
            .filter_by(shop_id=shop.shop_id)
            .scalar() or 0
        )

        avg_rating = None
        if shop.ratings:
            avg_rating = sum(r.value for r in shop.ratings) / len(shop.ratings)

        recent_items = (
            Item.query.filter_by(shop_id=shop.shop_id)
            .order_by(Item.item_id.desc())
            .limit(5)
            .all()
        )

        total_sold = (
            db.session.query(func.sum(OrderItem.quantity))
            .join(Order)
            .filter(Order.shop_id == shop.shop_id, Order.status == "shipped")
            .scalar() or 0
        )

        sales_value = (
            db.session.query(func.sum(OrderItem.price * OrderItem.quantity))
            .join(Order)
            .filter(Order.shop_id == shop.shop_id, Order.status == "shipped")
            .scalar() or 0
        )

        ratings = (
            Rating.query.filter_by(shop_id=shop.shop_id)
            .order_by(Rating.id.desc())
            .all()
        )

        return render_template(
            'dashboard.html',
            shop=shop,
            total_items=total_items,
            total_stock=total_stock,
            total_value=total_value,
            avg_rating=avg_rating,
            recent_items=recent_items,
            total_sold=total_sold,
            sales_value=sales_value,
            ratings=ratings
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading dashboard for user {current_user.user_id}: {e}")
        flash("An error occurred while loading your dashboard.", "danger")
        return redirect(url_for("views.home"))



# ------------------------------------- Universal ang shop -----------------------------------------------


# --- Global Shop Display (Marketplace) ---
@views_bp.route('/market', methods=['GET', 'POST'])
def global_market():
    try:
        form = SearchForm()
        query = Item.query.join(Category).join(Shop)

        # Exclude current user's shop items
        if current_user.is_authenticated:
            user_shop = Shop.query.filter_by(owner_id=current_user.user_id).first()
            if user_shop:
                query = query.filter(Item.shop_id != user_shop.shop_id)

        # Optional filters
        if form.validate_on_submit():
            if form.name.data:
                query = query.filter(Item.name.ilike(f"%{form.name.data}%"))
            if form.category.data and form.category.data != "":
                query = query.filter(Category.code == form.category.data)
            if form.min_price.data:
                query = query.filter(Item.price >= form.min_price.data)
            if form.max_price.data:
                query = query.filter(Item.price <= form.max_price.data)

            # Sorting
            if form.sort_by.data == "price":
                query = query.order_by(Item.price.asc() if form.order.data == "asc" else Item.price.desc())
            elif form.sort_by.data == "name":
                query = query.order_by(Item.name.asc() if form.order.data == "asc" else Item.name.desc())
      #      elif form.sort_by.data == "stock":
      #      query = query.order_by(Item.stock.asc() if form.order.data == "asc" else Item.stock.desc())

        items = query.all()
        return render_template('market.html', form=form, items=items)

    except Exception as e:
        db.session.rollback()  # rollback if query fails
        current_app.logger.error(f"Error loading global market: {e}")
        flash("An error occurred while loading the marketplace.", "danger")
        return redirect(url_for('views.home'))


@views_bp.route('/market/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def market_item_detail(item_id):
    try:
        item = Item.query.get_or_404(item_id)
        form = AddToCartForm()

        if form.validate_on_submit():
            quantity = form.quantity.data

            # enforce stock limit
            if quantity > item.stock:
                flash(f"Cannot add {quantity} × {item.name}. Only {item.stock} left in stock.", "danger")
                return redirect(url_for('views.market_item_detail', item_id=item_id))

            cart_item = CartItem.query.filter_by(user_id=current_user.user_id, item_id=item_id).first()
            if cart_item:
                # check combined quantity
                if cart_item.quantity + quantity > item.stock:
                    flash(f"Cannot exceed stock. You already have {cart_item.quantity} in cart.", "warning")
                else:
                    cart_item.quantity += quantity
                    flash(f"Updated {item.name} quantity to {cart_item.quantity}.", "success")
            else:
                cart_item = CartItem(user_id=current_user.user_id, item_id=item_id, quantity=quantity)
                db.session.add(cart_item)
                flash(f"Added {quantity} × {item.name} to your cart.", "success")

            db.session.commit()
            return redirect(url_for('views.view_cart'))

        return render_template('market_item_detail.html', item=item, form=form)

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error adding item {item_id} to cart: {e}")
        flash("An error occurred while adding the item to your cart.", "danger")
        return redirect(url_for('views.market_item_detail', item_id=item_id))




@views_bp.route('/market/shop/<int:shop_id>', methods=['GET', 'POST'])
@login_required
def market_shop(shop_id):
    try:
        shop = Shop.query.get_or_404(shop_id)
        items = Item.query.filter_by(shop_id=shop.shop_id).all()

        form = RatingForm()

        # Check if user has a completed order with this shop
        eligible_order = Order.query.filter_by(
            user_id=current_user.user_id,
            shop_id=shop.shop_id,
            status="received"
        ).first()

        # Handle rating submission
        if form.validate_on_submit() and eligible_order:
            if shop.owner_id == current_user.user_id:
                flash("You cannot rate your own shop.", "warning")
                return redirect(url_for("views.market_shop", shop_id=shop_id))

            existing = Rating.query.filter_by(
                user_id=current_user.user_id,
                shop_id=shop_id
            ).first()

            if existing:
                existing.value = form.value.data
                flash("Your rating has been updated.", "success")
            else:
                rating = Rating(
                    user_id=current_user.user_id,
                    shop_id=shop_id,
                    value=form.value.data
                )
                db.session.add(rating)
                flash("Thanks for rating this shop!", "success")

            db.session.commit()
            return redirect(url_for("views.market_shop", shop_id=shop_id))

        # Calculate average rating
        avg_rating = None
        if shop.ratings:
            avg_rating = sum(r.value for r in shop.ratings) / len(shop.ratings)

        return render_template(
            'market_shop.html',
            shop=shop,
            items=items,
            form=form,
            avg_rating=avg_rating,
            eligible_order=eligible_order,  # required for template logic
            is_home=False
        )

    except Exception as e:
        db.session.rollback()  # rollback if commit fails
        current_app.logger.error(f"Error loading shop {shop_id}: {e}")
        flash("An error occurred while loading the shop.", "danger")
        return redirect(url_for("views.market"))





# -------------------------------------- CART ACTION ----------------------------------------------

@views_bp.route('/cart')
@login_required
def view_cart():
    try:
        cart_items = CartItem.query.filter_by(user_id=current_user.user_id).all()
        total_value = sum(ci.item.price * ci.quantity for ci in cart_items)

        return render_template(
            'cart.html',
            cart_items=cart_items,
            total_value=total_value
        )

    except Exception as e:
        db.session.rollback()  # rollback if query fails
        current_app.logger.error(f"Error loading cart for user {current_user.user_id}: {e}")
        flash("An error occurred while loading your cart.", "danger")
        return redirect(url_for('views.market'))



@views_bp.route('/cart/add/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    try:
        item = Item.query.get_or_404(item_id)
        form = AddToCartForm()

        if form.validate_on_submit():
            quantity = form.quantity.data

            # enforce stock limit
            if quantity > item.stock:
                flash(f"Cannot add {quantity} × {item.name}. Only {item.stock} left in stock.", "danger")
                return redirect(url_for('views.market_item_detail', item_id=item_id))

            cart_item = CartItem.query.filter_by(user_id=current_user.user_id, item_id=item_id).first()
            if cart_item:
                # check combined quantity
                if cart_item.quantity + quantity > item.stock:
                    flash(f"Cannot exceed stock. You already have {cart_item.quantity} in cart.", "warning")
                else:
                    cart_item.quantity += quantity
                    flash(f"Updated {item.name} quantity to {cart_item.quantity}.", "success")
            else:
                cart_item = CartItem(user_id=current_user.user_id, item_id=item_id, quantity=quantity)
                db.session.add(cart_item)
                flash(f"Added {quantity} × {item.name} to your cart.", "success")

            db.session.commit()
            return redirect(url_for('views.view_cart'))

        return redirect(url_for('views.market_item_detail', item_id=item_id))

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error adding item {item_id} to cart: {e}")
        flash("An error occurred while adding the item to your cart.", "danger")
        return redirect(url_for('views.market_item_detail', item_id=item_id))



@views_bp.route('/cart/delete/<int:cart_item_id>', methods=['POST'])
@login_required
def delete_from_cart(cart_item_id):
    try:
        cart_item = CartItem.query.get_or_404(cart_item_id)

        # Security check
        if cart_item.user_id != current_user.user_id:
            flash("You cannot delete items from another user's cart.", "danger")
            return redirect(url_for('views.view_cart'))

        db.session.delete(cart_item)
        db.session.commit()
        flash("Item removed from your cart.", "success")

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error deleting cart item {cart_item_id}: {e}")
        flash("An error occurred while removing the item from your cart.", "danger")

    return redirect(url_for('views.view_cart'))









# ------------------------------------------------- ORDERING ACTION -------------------------------------

@views_bp.route("/my_orders")
@login_required
def my_orders():
    try:
        orders = (
            Order.query
            .filter_by(user_id=current_user.user_id)
            .order_by(Order.id.desc())
            .all()
        )
        return render_template("my_orders.html", orders=orders)

    except Exception as e:
        db.session.rollback()  # rollback if query fails
        current_app.logger.error(f"Error loading orders for user {current_user.user_id}: {e}")
        flash("An error occurred while loading your orders.", "danger")
        return redirect(url_for("home"))



@views_bp.route("/item/<int:item_id>/place_order_now", methods=["POST"])
@login_required
def place_order_now(item_id):
    """Place an order directly from the item detail page (Place Order Now button)."""
    try:
        item = Item.query.get_or_404(item_id)
        user = current_user

        if not user.address:
            flash("Please add your address to your profile first.", "warning")
            return redirect(url_for("views.profile"))

        quantity = int(request.form.get("quantity", 1))

        if quantity < 1:
            flash("Invalid quantity.", "danger")
            return redirect(url_for("views.market_item_detail", item_id=item_id))

        if quantity > item.stock:
            flash(f"Only {item.stock} left in stock.", "danger")
            return redirect(url_for("views.market_item_detail", item_id=item_id))

        location_str = f"{user.address.street_address}, {user.address.city}, {user.address.province} {user.address.zip_code}"

        order = Order(
            user_id=user.user_id,
            shop_id=item.shop_id,
            location=location_str,
            status="placed"
        )
        db.session.add(order)
        db.session.flush()  # get order.id before commit

        order_item = OrderItem(
            order_id=order.id,
            item_id=item.item_id,
            quantity=quantity,
            price=item.price
        )
        db.session.add(order_item)

        # Auto-deduct stock immediately
        item.stock = max(item.stock - quantity, 0)

        db.session.commit()
        flash("Order placed successfully!", "success")
        return redirect(url_for("views.my_orders"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error placing direct order for item {item_id}: {e}")
        flash("An error occurred while placing your order.", "danger")
        return redirect(url_for("views.market_item_detail", item_id=item_id))


@views_bp.route("/cart/place_order/<int:shop_id>", methods=["POST"])
@login_required
def place_order_for_shop(shop_id):
    try:
        user = current_user

        if not user.address:
            flash("Please add your address to your profile first.", "warning")
            return redirect(url_for("views.profile"))

        # Build location string from Address model
        location_str = f"{user.address.street_address}, {user.address.city}, {user.address.province} {user.address.zip_code}"

        # Create order
        order = Order(
            user_id=user.user_id,
            shop_id=shop_id,
            location=location_str,
            status="placed"
        )
        db.session.add(order)
        db.session.commit()

        # Attach cart items as OrderItems
        cart_items = CartItem.query.filter_by(user_id=user.user_id).all()
        if not cart_items:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("views.view_cart"))

        for ci in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                item_id=ci.item_id,
                quantity=ci.quantity,
                price=ci.item.price
            )
            db.session.add(order_item)

            # Auto-deduct stock when order is placed
            if ci.item:
                ci.item.stock = max(ci.item.stock - ci.quantity, 0)

        # Clear cart after placing order
        CartItem.query.filter_by(user_id=user.user_id).delete()

        db.session.commit()

        flash("Order placed successfully!", "success")
        return redirect(url_for("views.my_orders"))

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error placing order for shop {shop_id}: {e}")
        flash("An error occurred while placing your order.", "danger")
        return redirect(url_for("views.view_cart"))




# Cancel Order (buyer side)
@views_bp.route("/order/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order_user(order_id):
    try:
        order = Order.query.get_or_404(order_id)

        # Security check: only the buyer can cancel
        if order.user_id != current_user.user_id:
            abort(403)

        if order.status in ["placed", "shipped"]:
            # Restock items automatically
            for order_item in order.order_items:
                item = order_item.item
                if item:
                    item.stock += order_item.quantity

            order.status = "canceled"
            db.session.commit()
            flash("Order canceled and items restocked.", "info")
        else:
            flash("Order cannot be canceled in its current status.", "warning")

    except Exception as e:
        db.session.rollback()  # keep DB consistent
        current_app.logger.error(f"Error canceling order {order_id}: {e}")
        flash("An error occurred while canceling the order.", "danger")

    return redirect(url_for("views.my_orders"))



# ship order - action for seller 
@views_bp.route("/shop/<int:shop_id>/orders")
@login_required
def shop_orders(shop_id):
    try:
        shop = Shop.query.get_or_404(shop_id)

        # Security check: only shop owner can view
        if shop.owner_id != current_user.user_id:
            abort(403)

        orders = Order.query.filter_by(shop_id=shop_id).order_by(Order.id.desc()).all()
        return render_template("shop_orders.html", shop=shop, orders=orders)

    except Exception as e:
        db.session.rollback()  # rollback if query fails
        current_app.logger.error(f"Error loading orders for shop {shop_id}: {e}")
        flash("An error occurred while loading shop orders.", "danger")
        return redirect(url_for("views.dashboard"))



# Receive Order (buyer side)
@views_bp.route("/order/<int:order_id>/receive", methods=["POST"])
@login_required
def receive_order_user(order_id):
    try:
        order = Order.query.get_or_404(order_id)

        # Security check: only buyer can mark as received
        if order.user_id != current_user.user_id:
            abort(403)

        if order.status == "shipped":
            order.status = "received"
            db.session.commit()
            flash("Order marked as received.", "success")
        else:
            flash("Order cannot be marked as received in its current status.", "warning")

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error receiving order {order_id}: {e}")
        flash("An error occurred while marking the order as received.", "danger")

    return redirect(url_for("views.my_orders"))



# Rate Shop buyer side - can rate shop after orders
@views_bp.route("/shop/<int:shop_id>/rate", methods=["POST"])
@login_required
def rate_shop_user(shop_id):
    try:
        shop = Shop.query.get_or_404(shop_id)

        # Must have a received order
        order = Order.query.filter_by(
            user_id=current_user.user_id,
            shop_id=shop_id,
            status="received"
        ).first()

        if not order:
            flash("You must complete an order before rating this shop.", "warning")
            return redirect(url_for("views.my_orders"))

        form = RatingForm()
        if form.validate_on_submit():
            if shop.owner_id == current_user.user_id:
                flash("You cannot rate your own shop.", "warning")
                return redirect(url_for("views.market_shop", shop_id=shop_id))

            existing = Rating.query.filter_by(
                user_id=current_user.user_id,
                shop_id=shop_id
            ).first()

            if existing:
                existing.value = form.value.data
                flash("Your rating has been updated.", "success")
            else:
                rating = Rating(
                    user_id=current_user.user_id,
                    shop_id=shop_id,
                    value=form.value.data
                )
                db.session.add(rating)
                flash("Thanks for rating this shop!", "success")

            db.session.commit()

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error rating shop {shop_id}: {e}")
        flash("An error occurred while submitting your rating.", "danger")

    return redirect(url_for("views.show_rate_shop", shop_id=shop_id))


@views_bp.route("/shop/<int:shop_id>/rate", methods=["GET"])
@login_required
def show_rate_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    form = RatingForm()

    eligible_order = Order.query.filter_by(
        user_id=current_user.user_id,
        shop_id=shop_id,
        status="received"
    ).first()

    existing_rating = Rating.query.filter_by(
        user_id=current_user.user_id,
        shop_id=shop_id
    ).first()

    avg_rating = None
    if shop.ratings:
        avg_rating = sum(r.value for r in shop.ratings) / len(shop.ratings)

    return render_template(
        "shop_rating.html",
        shop=shop,
        form=form,
        avg_rating=avg_rating,
        eligible_order=eligible_order,
        existing_rating=existing_rating
    )





@views_bp.route("/order/<int:order_id>")
@login_required
def order_detail(order_id):
    try:
        order = Order.query.get_or_404(order_id)

        # Security check: only buyer can view
        if order.user_id != current_user.user_id:
            abort(403)

        return render_template("order_detail.html", order=order)

    except Exception as e:
        db.session.rollback()  # rollback if query fails
        current_app.logger.error(f"Error loading order {order_id}: {e}")
        flash("An error occurred while loading the order details.", "danger")
        return redirect(url_for("views.my_orders"))



@views_bp.route("/order/<int:order_id>/ship", methods=["POST"])
@login_required
def ship_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)

        # Security check
        if order.shop.owner_id != current_user.user_id:
            abort(403)

        current_app.logger.debug(f"Processing ship request for Order ID: {order.id}")
        current_app.logger.debug(f"Order {order.id} status BEFORE change: {order.status}")

        # Stock was already deducted at order placement — just log missing items
        for order_item in order.order_items:
            if not order_item.item:
                current_app.logger.warning(f"Item ID {order_item.item_id} not found for order item {order_item.id} in Order {order.id}.")

        order.status = "shipped"
        current_app.logger.debug(f"Order {order.id} status AFTER change (before commit): {order.status}")

        current_app.logger.info(f"Attempting to commit changes for Order ID: {order.id} (status 'shipped').")
        db.session.commit()
        current_app.logger.info(f"Successfully committed changes for Order ID: {order.id}. New status in DB should be 'shipped'.")

        flash(f"Order #{order.id} shipped successfully.", "success")

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        current_app.logger.error(f"Error shipping order {order_id}: {e}", exc_info=True) # exc_info=True prints the full traceback
        flash("An error occurred while shipping the order.", "danger")
        # If an error occurs before 'order' is fully defined or committed,
        # redirect might fail. Ensure 'order' is available or handle gracefully.
        if 'order' in locals(): # Check if order variable exists
            return redirect(url_for("views.shop_orders", shop_id=order.shop_id))
        else:
            return redirect(url_for("home")) # Fallback if order object is not available

    return redirect(url_for("views.shop_orders", shop_id=order.shop_id))
# _________________________________________________ BLOG POST ROUTES _____________________________________________





@views_bp.route("/blog/new", methods=["GET", "POST"])
@login_required
def new_blog_post():
    form = BlogPostForm()
    if form.validate_on_submit():
        try:
            media_path = None
            if form.media.data:
                media_path = save_file(form.media.data, folder="uploads")

            post = BlogPost(
                user_id=current_user.user_id,
                title=form.title.data,
                description=form.description.data,
                media_url=media_path
            )
            db.session.add(post)
            db.session.commit()

            flash("Blog post published!", "success")
            return redirect(url_for("views.user_blog", user_id=current_user.user_id))

        except Exception as e:
            db.session.rollback()  # rollback to keep DB consistent
            current_app.logger.error(f"Error creating blog post: {e}")
            flash("An error occurred while publishing your post.", "danger")
            return redirect(url_for("views.profile"))

    return render_template("new_blog_post.html", form=form)




@views_bp.route("/user/<int:user_id>/blog")
def user_blog(user_id):
    try:
        user = User.query.get_or_404(user_id)
        posts = BlogPost.query.filter_by(user_id=user_id).order_by(BlogPost.created_at.desc()).all()
        return render_template("user_blog.html", user=user, posts=posts)

    except Exception as e:
        db.session.rollback()  # rollback if query fails
        current_app.logger.error(f"Error loading blog posts for user {user_id}: {e}")
        flash("An error occurred while loading this user's blog posts.", "danger")
        return redirect(url_for("views.blog_list"))

@views_bp.route("/about")
def about():
    # This will render your about.html template
    return render_template("about.html")


@views_bp.route("/blogs")
def blog_list():
    try:
        # Show all blog posts from all users
        posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
        return render_template("blog_list.html", posts=posts)

    except Exception as e:
        db.session.rollback()  # rollback if something went wrong
        current_app.logger.error(f"Error loading blog list: {e}")  # log for debugging
        flash("An error occurred while loading blog posts.", "danger")
        return redirect(url_for("views.blog_list"))



@views_bp.route('/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    try:
        post = BlogPost.query.get_or_404(post_id)

        # Security check
        if post.user_id != current_user.user_id:
            flash("You don't have permission to delete this post.", "danger")
            return redirect(url_for('views.profile'))

        db.session.delete(post)
        db.session.commit()
        flash("Post deleted successfully.", "success")

    except Exception as e:
        db.session.rollback()  # rollback to keep DB consistent
        flash(f"An error occurred while deleting the post: {str(e)}", "danger")

    return redirect(url_for('views.profile'))