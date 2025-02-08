"""
E-Commerce Web Application
A Flask-based e-commerce platform with user authentication, product management,
shopping cart functionality, and seller dashboard.

Author: Satbir
Version: 1.0.0
"""

# Standard library imports
import os
import time
import uuid
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
from functools import wraps

# Third-party imports
import pandas as pd
from flask import (
    Flask, 
    render_template, 
    request, 
    redirect, 
    url_for,
    flash, 
    jsonify, 
    session, 
    send_file
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func, case
from pytz import timezone

# Logging setup
import logging
from logging.handlers import RotatingFileHandler

# Create the Flask application instance
app = Flask(__name__)

# Configuration settings
app.config["SECRET_KEY"] = "8BYkEfBA6O6donzWlSihBXox7C0sKR6b"  # Secret key for sessions
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"  # SQLite database URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "dist", "product_images")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database and Login Manager Initialization
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

###############################################################################################################################################
# Models
###############################################################################################################################################


class UserDatabase(db.Model, UserMixin):
    __tablename__ = "user_database"  # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(10), nullable=False)
    address = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    is_seller = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone("Asia/Kolkata")))
    earning = db.Column(db.Float, default=0)
    # Relationships
    cart_items = db.relationship("CartItem", backref="user", lazy=True)
    orders = db.relationship("Order", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)


class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone("Asia/Kolkata")))
    earning = db.Column(db.Float, default=0)

    # Relationships
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("user_database.id"), nullable=False
    )
    reviews = db.relationship("Review", backref="product", lazy=True)
    cart_items = db.relationship("CartItem", backref="product", lazy=True)


class CartItem(db.Model):
    __tablename__ = "cart_item"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_database.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)


class Order(db.Model):
    __tablename__ = "order"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_database.id"), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone("Asia/Kolkata")),
        nullable=False,
    )


class OrderItem(db.Model):
    __tablename__ = "order_item"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)  # Store price at the time of purchase

    # Relationships
    order = db.relationship("Order", backref="order_items", lazy=True)
    product = db.relationship("Product", backref="order_items", lazy=True)


class Wishlist(db.Model):
    __tablename__ = "wishlist"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user_database.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)


class Review(db.Model):
    __tablename__ = "review"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user_database.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone("Asia/Kolkata")),
        nullable=False,
    )


# Create tables in the databases
with app.app_context():
    db.create_all()


###############################################################################################################################################
# Utility Functions
###############################################################################################################################################


@login_manager.user_loader
def load_user(user_id):
    """User loader function for Flask-Login."""
    return UserDatabase.query.get(int(user_id))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.template_filter("slice")
def slice_filter(iterable, limit):
    """Custom filter to slice an iterable to a specified limit."""
    return list(iterable)[:limit]



###############################################################################################################################################
# Routes
###############################################################################################################################################

###############################################################################
# === Authentication Routes ===
###############################################################################

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login.
    
    GET: Display login form
    POST: Authenticate user credentials and create session
    
    Returns:
        GET: Login page template
        POST: Redirect to home page on success, back to login with error on failure
    """
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Basic validation
        if not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        # Check if user exists and verify credentials
        user = UserDatabase.query.filter_by(email=email).first()
        if not user:
            flash("Email not registered.", "error")
            return redirect(url_for("login"))

        if user.is_banned:
            flash("Your account has been banned. Please contact support.", "error")
            return redirect(url_for("login"))

        if not check_password_hash(user.password, password):
            flash("Incorrect password.", "error")
            return redirect(url_for("login"))

        login_user(user)
        return redirect(url_for("home"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Handle new user registration.
    
    GET: Display registration form
    POST: Create new user account
    
    Returns:
        GET: Registration page template
        POST: Redirect to home page on success, back to register with error on failure
    """
    if request.method == "POST":
        # Get form data
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone_number = request.form.get("phone")
        address = request.form.get("address")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        print(
            first_name,
            last_name,
            email,
            phone_number,
            address,
            password,
            confirm_password,
        )

        # Basic validation
        if not all(
            [
                first_name,
                last_name,
                email,
                phone_number,
                address,
                password,
                confirm_password,
            ]
        ):
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        # Check if user already exists
        user = UserDatabase.query.filter_by(email=email).first()
        if user:
            flash("Email already registered.", "error")
            return redirect(url_for("register"))

        # Create new user
        try:
            new_user = UserDatabase(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                address=address,
                password=generate_password_hash(password, method="pbkdf2:sha256"),
            )
            db.session.add(new_user)
            db.session.commit()

            # Log the user in after registration
            login_user(new_user)
            # flash("Registration successful!", "success")
            return redirect(url_for("home"))

        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration.", "error")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    """Log out current user and clear session."""
    logout_user()
    # flash("You have been logged out.", "is-success")
    return redirect(url_for("home"))

###############################################################################
# === Public Routes ===
###############################################################################

@app.route("/", methods=["GET"])
def home():
    """Display homepage with product listings.
    
    Returns:
        Homepage template with:
        - List of all products
        - Price range filters
        - Category filters
    """
    # Get all products with ordering
    products = Product.query.order_by(Product.created_at.desc()).all()
    
    if request.headers.get('HX-Request'):
        # Return only the product grid for HTMX requests
        return render_template("partials/product_grid.html", products=products)
    
    # Get min and max prices for the price slider
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    
    return render_template("home.html", products=products, user=current_user, 
                         min_price=min_price, max_price=max_price)

@app.route("/product/<int:product_id>")
def product_page(product_id):
    """Display individual product details.
    
    Args:
        product_id: ID of product to display
        
    Returns:
        Product detail page with:
        - Product information
        - Reviews
        - Add to cart/wishlist options
        - Purchase status for current user
    """
    product = Product.query.get_or_404(product_id)
    
    # Get min and max prices for the price slider
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    
    # Get wishlist status
    wishlist = []
    if current_user.is_authenticated:
        wishlist = [item.product_id for item in Wishlist.query.filter_by(user_id=current_user.id).all()]
    
    # Get reviews
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    
    # Check if user has purchased the product
    has_purchased = False
    has_reviewed = False
    if current_user.is_authenticated:
        # Check if user has any completed orders containing this product
        has_purchased = db.session.query(Order).join(OrderItem).filter(
            Order.user_id == current_user.id,
            OrderItem.product_id == product_id,
            Order.status == "Completed"
        ).first() is not None
        
        # Check if user has already reviewed
        has_reviewed = Review.query.filter_by(
            user_id=current_user.id,
            product_id=product_id
        ).first() is not None
    
    return render_template("product_page.html", 
                         product=product, 
                         user=current_user,
                         min_price=min_price,
                         max_price=max_price,
                         wishlist=wishlist,
                         reviews=reviews,
                         has_purchased=has_purchased,
                         has_reviewed=has_reviewed)

###############################################################################
# === User Routes ===
###############################################################################

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Handle user account management.
    
    GET: Display account details and order history
    POST: Update account information
    
    Returns:
        Account page template with user details and orders
    """
    if request.method == "POST":
        # Fetch updated details from the form
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        address = request.form.get("address")

        # Basic validation
        if not all([first_name, last_name, phone_number, address, email]):
            flash("Please fill in all fields.", "error")
            return redirect(url_for("account"))

        # Update user details in the database
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.phone_number = phone_number
        current_user.address = address
        current_user.email = email

        try:
            db.session.commit()
            flash("Account details updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while updating details.", "error")
            print(f"Error: {e}")

    # Sort orders by created_at in descending order
    print(f"User Orders: {current_user.orders}")
    return render_template("user/account.html", user=current_user)

@app.route("/cancel_order/<int:order_id>", methods=["POST"])
@login_required
def cancel_order(order_id):
    """Cancel a pending order."""
    order = Order.query.get_or_404(order_id)

    # Check if order belongs to current user
    if order.user_id != current_user.id:
        flash("You don't have permission to cancel this order.", "error")
        return redirect(url_for("account"))

    # Check if order is pending
    if order.status != "Pending":
        flash("Only pending orders can be cancelled.", "error")
        return redirect(url_for("account"))

    try:
        order.status = "Cancelled"
        db.session.commit()
        flash("Order cancelled successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while cancelling the order.", "error")
        print(f"Error: {e}")

    return redirect(url_for("account"))

@app.route("/cart")
@login_required
def cart():
    """Display user's shopping cart.
    
    Returns:
        Cart page template with:
        - Cart items
        - Order summary
        - Checkout options
    """
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    
    # Calculate order summary
    subtotal = sum(item.quantity * item.product.price for item in cart_items)
    shipping = subtotal * 0.015  # 1.5% shipping fee
    tax = subtotal * 0.18  # 18% tax
    total = subtotal + shipping + tax
    
    # Get min and max prices for the sidebar
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    
    return render_template("cart.html", 
                         cart_items=cart_items,
                         subtotal=subtotal,
                         shipping=shipping,
                         tax=tax,
                         total=total,
                         user=current_user,
                         min_price=min_price,
                         max_price=max_price)

@app.route("/wishlist")
@login_required
def wishlist():
    """Display user's wishlist items.
    
    Returns:
        Wishlist page template with:
        - Wishlist items
        - Add to cart options
        - Remove from wishlist options
    """
    # Get user's wishlist items with product details
    wishlist_items = Wishlist.query.filter_by(user_id=current_user.id)\
        .join(Product, Wishlist.product_id == Product.id)\
        .add_entity(Product)\
        .all()
    
    # Format wishlist items for template
    formatted_items = [{"id": item[0].id, "product": item[1]} for item in wishlist_items]
    
    return render_template("user/wishlist.html", 
                         wishlist_items=formatted_items,
                         user=current_user)

###############################################################################
# === Seller Routes ===
###############################################################################

@app.route("/seller_dashboard")
@login_required
def seller_dashboard():
    """Display seller dashboard with product and order management.
    
    Returns:
        Dashboard template with:
        - Product listings
        - Order management
        - Sales analytics
        - Low stock alerts
        
    Requires seller privileges.
    """
    if not current_user.is_seller:
        flash("You don't have permission to access the seller dashboard.", "error")
        return redirect(url_for("home"))

    # Get page number from query parameters, default to 1
    page = request.args.get('page', 1, type=int)
    per_page = 5  # Number of items per page

    # Get seller's products with pagination, ordered by created_at desc
    products_pagination = Product.query.filter_by(supplier_id=current_user.id)\
        .order_by(Product.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    # Get all products for the edit modals (needed for the full list)
    products = Product.query.filter_by(supplier_id=current_user.id)\
        .order_by(Product.created_at.desc())\
        .all()

    # Get orders containing seller's products
    seller_product_ids = [p.id for p in Product.query.filter_by(supplier_id=current_user.id).all()]
    orders = Order.query.join(OrderItem)\
        .filter(OrderItem.product_id.in_(seller_product_ids))\
        .distinct()\
        .all()

    # Get pending orders
    pending_orders = [order for order in orders if order.status == "Pending"]

    # Get low stock products (less than 10 items)
    low_stock_products = Product.query.filter_by(supplier_id=current_user.id)\
        .filter(Product.stock < 10)\
        .all()

    return render_template(
        "seller/dashboard.html",
        user=current_user,
        products_pagination=products_pagination,
        products=products,  # Add this for the edit modals
        orders=orders,
        pending_orders=pending_orders,
        low_stock_products=low_stock_products,
    )

@app.route("/add_product", methods=["POST"])
@login_required
def add_product():
    if not current_user.is_seller:
        flash("You don't have permission to add products.", "error")
        return redirect(url_for("home"))

    try:
        name = request.form.get("name")
        description = request.form.get("description")
        price = float(request.form.get("price"))
        category = request.form.get("category")
        stock = int(request.form.get("stock"))
        image = request.files.get("image")

        if image and allowed_file(image.filename):
            # Generate a unique filename using timestamp and random number
            timestamp = int(time.time())
            random_number = str(int(time.time() * 1000))[-6:]  # Last 6 digits
            file_extension = image.filename.rsplit(".", 1)[1].lower()
            filename = f"{timestamp}_{random_number}.{file_extension}"

            filename = secure_filename(filename)
            # Save directly to UPLOAD_FOLDER
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image.save(save_path)
            image_path = filename
        else:
            image_path = None

        created_at = datetime.now(timezone("Asia/Kolkata"))

        new_product = Product(
            name=name,
            description=description,
            price=price,
            category=category,
            stock=stock,
            image=image_path,
            supplier_id=current_user.id,
            created_at=created_at,
        )

        db.session.add(new_product)
        db.session.commit()
        flash("Product added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error adding product.", "error")
        print(f"Error: {e}")

    return redirect(url_for("seller_dashboard"))


@app.route("/delete_product/<int:product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    if not current_user.is_seller:
        return jsonify({"error": "Unauthorized"}), 403

    product = Product.query.get_or_404(product_id)
    if product.supplier_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Delete the product image file if it exists
        if product.image:
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], product.image)
            if os.path.exists(image_path):
                os.remove(image_path)

        # Delete the product from database
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Product deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/update_order_status/<int:order_id>", methods=["POST"])
@login_required
def update_order_status(order_id):
    if not current_user.is_seller:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    new_status = data.get("status")

    order = Order.query.get_or_404(order_id)

    # Verify the order contains products from this seller
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    seller_products = [
        item for item in order_items if item.product.supplier_id == current_user.id
    ]

    if not seller_products:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        order.status = new_status
        db.session.commit()
        return jsonify({"message": "Order status updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/edit_product/<product_id>", methods=["POST"])
@login_required
def edit_product(product_id):
    if not current_user.is_seller:
        flash("You don't have permission to edit products.", "error")
        return redirect(url_for("seller_dashboard"))
    product = Product.query.get_or_404(product_id)

    # Verify product belongs to current user
    if product.supplier_id != current_user.id:
        flash("You don't have permission to edit this product.", "error")
        return redirect(url_for("seller_dashboard"))

    # Update product details
    product.name = request.form.get("name")
    product.description = request.form.get("description")
    product.category = request.form.get("category")
    product.price = float(request.form.get("price"))
    product.stock = int(request.form.get("stock"))

    # Handle image upload if provided
    if "image" in request.files and request.files["image"].filename:
        file = request.files["image"]
        if file and allowed_file(file.filename):
            # Delete old image if it exists
            if product.image:
                old_image_path = os.path.join(
                    app.config["UPLOAD_FOLDER"], product.image
                )
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)

            # Save new image
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
            product.image = unique_filename

    db.session.commit()
    flash("Product updated successfully", "success")
    return redirect(url_for("seller_dashboard"))

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    quantity = data.get('quantity', 1)
    
    # Check if product already in cart
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    if cart_item:
        cart_item.quantity = quantity
    else:
        cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    
    try:
        db.session.commit()
        return jsonify({"message": "Product added to cart successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/toggle_wishlist/<int:product_id>", methods=["POST"])
@login_required
def toggle_wishlist(product_id):
    product = Product.query.get_or_404(product_id)
    wishlist_item = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    try:
        if wishlist_item:
            db.session.delete(wishlist_item)
        else:
            wishlist_item = Wishlist(user_id=current_user.id, product_id=product_id)
            db.session.add(wishlist_item)
        
        db.session.commit()
        return jsonify({"message": "Wishlist updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/add_review/<int:product_id>", methods=["POST"])
@login_required
def add_review(product_id):
    # Verify user has purchased the product
    has_purchased = db.session.query(Order).join(OrderItem).filter(
        Order.user_id == current_user.id,
        OrderItem.product_id == product_id,
        Order.status == "Completed"
    ).first() is not None
    
    if not has_purchased:
        flash("You can only review products you have purchased.", "error")
        return redirect(url_for("product_page", product_id=product_id))
    
    # Check if user has already reviewed
    existing_review = Review.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first()
    
    if existing_review:
        flash("You have already reviewed this product.", "error")
        return redirect(url_for("product_page", product_id=product_id))
    
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment")
    
    if not rating or not comment:
        flash("Please provide both rating and comment.", "error")
        return redirect(url_for("product_page", product_id=product_id))
    
    if not 1 <= rating <= 5:
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("product_page", product_id=product_id))
    
    try:
        # Add the review
        review = Review(
            user_id=current_user.id,
            product_id=product_id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        
        # Update product rating
        product = Product.query.get(product_id)
        reviews = Review.query.filter_by(product_id=product_id).all()
        total_rating = sum(r.rating for r in reviews) + rating
        product.rating = total_rating / (len(reviews) + 1)
        
        db.session.commit()
        flash("Review added successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while adding your review.", "error")
        print(f"Error: {e}")
    
    return redirect(url_for("product_page", product_id=product_id))

@app.context_processor
def inject_cart_data():
    cart_items = []
    cart_count = 0
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        cart_count = sum(item.quantity for item in cart_items)
    return dict(cart_items=cart_items, cart_count=cart_count)

@app.route("/update_cart/<int:product_id>", methods=["POST"])
@login_required
def update_cart(product_id):
    data = request.get_json()
    quantity = data.get('quantity', 1)
    
    product = Product.query.get_or_404(product_id)
    if quantity > product.stock:
        return jsonify({
            "error": f"Only {product.stock} items available in stock",
            "available_stock": product.stock
        }), 400
    
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity = quantity
        db.session.commit()
        
        # Recalculate cart totals
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        subtotal = sum(item.quantity * item.product.price for item in cart_items)
        shipping = subtotal * 0.015
        tax = subtotal * 0.18
        total = subtotal + shipping + tax
        
        return jsonify({
            "message": "Cart updated successfully",
            "item_total": cart_item.quantity * cart_item.product.price,
            "subtotal": subtotal,
            "shipping": shipping,
            "tax": tax,
            "total": total,
            "quantity": quantity
        })
    
    return jsonify({"error": "Item not found in cart"}), 404

@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
@login_required
def remove_from_cart(product_id):
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
    
    return jsonify({"message": "Item removed from cart successfully"})

@app.route("/offers")
def offers():
    # Get min and max prices for the sidebar
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    
    return render_template("coming_soon.html", 
                         page_title="Offers & Deals",
                         min_price=min_price,
                         user=current_user,
                         max_price=max_price)

@app.route("/recently-viewed")
def recently_viewed():
    # Get min and max prices for the sidebar
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    
    return render_template("coming_soon.html", 
                         page_title="Recently Viewed",
                         min_price=min_price,
                         user=current_user,
                         max_price=max_price)

@app.route("/place_order", methods=["POST"])
@login_required
def place_order():
    try:
        # Get cart items
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        if not cart_items:
            return jsonify({"error": "Cart is empty"}), 400

        # Calculate totals
        subtotal = sum(item.quantity * item.product.price for item in cart_items)
        shipping = subtotal * 0.015
        tax = subtotal * 0.18
        total = subtotal + shipping + tax

        # Create new order
        order = Order(
            user_id=current_user.id,
            total_price=total,
            status="Pending"
        )
        db.session.add(order)
        db.session.flush()  # Get order ID before committing

        # Create order items and update product stock
        for cart_item in cart_items:
            product = cart_item.product
            if product.stock < cart_item.quantity:
                db.session.rollback()
                return jsonify({
                    "error": f"Not enough stock for {product.name}. Only {product.stock} available."
                }), 400

            # Create order item
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                quantity=cart_item.quantity,
                price=product.price
            )
            db.session.add(order_item)

            # Update product stock
            product.stock -= cart_item.quantity

            # Update product and supplier earnings
            item_total = cart_item.quantity * product.price
            product.earning += item_total
            supplier = UserDatabase.query.get(product.supplier_id)
            supplier.earning += item_total

        # Clear cart
        for item in cart_items:
            db.session.delete(item)

        db.session.commit()
        return jsonify({
            "message": "Order placed successfully",
            "user_name": current_user.first_name + " " + current_user.last_name,
            "address": current_user.address,
            "phone": current_user.phone_number
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error placing order: {str(e)}")
        return jsonify({"error": "An error occurred while placing your order"}), 500

@app.route("/orders")
@login_required
def orders():
    # Get user's orders with items, ordered by most recent first
    user_orders = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc())\
        .all()
    
    # Get min and max prices for the sidebar
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    
    return render_template("user/orders.html", 
                         orders=user_orders,
                         user=current_user,
                         min_price=min_price,
                         max_price=max_price)

###############################################################################################################################################
# === API Routes ===
###############################################################################################################################################

@app.route("/filter_products", methods=["GET", "POST"])
def filter_products():
    """Filter products based on categories, price range, and rating.
    
    Accepts both JSON and form data for filtering criteria.
    
    Returns:
        Filtered product grid partial template for AJAX requests
        Full page template for regular requests
        
    Error Codes:
        500: Server error during filtering
    """
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            categories = data.get('categories', [])
            price_range = data.get('priceRange')
            min_rating = float(data.get('rating')) if data.get('rating') else None
            
            # Convert price range to min and max
            if price_range:
                max_price = float(price_range)
                min_price = 0
            else:
                min_price = None
                max_price = None
        else:
            categories = request.form.getlist('categories[]') or request.args.getlist('categories[]')
            min_price = request.form.get('min_price') or request.args.get('min_price')
            max_price = request.form.get('max_price') or request.args.get('max_price')
            min_rating = request.form.get('rating') or request.args.get('rating')
            
            # Convert numeric values
            min_price = float(min_price) if min_price else None
            max_price = float(max_price) if max_price else None
            min_rating = float(min_rating) if min_rating else None
        
        # Start with base query
        query = Product.query
        
        # Apply category filter if categories are selected
        if categories:
            # Use OR condition for multiple categories
            query = query.filter(Product.category.in_(categories))
            
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)
        if min_rating is not None:
            query = query.filter(Product.rating >= min_rating)
            
        # Get all products with ordering
        products = query.order_by(Product.created_at.desc()).all()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render_template("partials/product_grid.html", products=products)
        
        # Get min and max prices for the price slider
        min_price = db.session.query(func.min(Product.price)).scalar() or 0
        max_price = db.session.query(func.max(Product.price)).scalar() or 10000
        
        return render_template("home.html", products=products, 
                             min_price=min_price, max_price=max_price)
                             
    except Exception as e:
        print(f"Error in filter_products: {str(e)}")
        return jsonify({"error": str(e)}), 500

###############################################################################
# === Helper Functions ===
###############################################################################

@app.context_processor
def inject_cart_data():
    """Inject cart data into all templates.
    
    Returns:
        Dict containing cart items and count
    """
    cart_items = []
    cart_count = 0
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        cart_count = sum(item.quantity for item in cart_items)
    return dict(cart_items=cart_items, cart_count=cart_count)

@app.template_filter("slice")
def slice_filter(iterable, limit):
    """Custom template filter to slice iterables.
    
    Args:
        iterable: Iterable to slice
        limit: Maximum number of items to return
        
    Returns:
        Sliced list
    """
    return list(iterable)[:limit]

###############################################################################
# === Error Handlers ===
###############################################################################

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 Not Found errors.
    
    Returns:
        404 error page with sidebar data
    """
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    return render_template('errors/404.html', 
                         user=current_user,
                         min_price=min_price,
                         max_price=max_price), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 Internal Server errors.
    
    Returns:
        500 error page with sidebar data
    """
    min_price = db.session.query(func.min(Product.price)).scalar() or 0
    max_price = db.session.query(func.max(Product.price)).scalar() or 10000
    return render_template('errors/500.html', 
                         user=current_user,
                         min_price=min_price,
                         max_price=max_price), 500

# Run the application
if __name__ == "__main__":
    app.run(debug=True)
