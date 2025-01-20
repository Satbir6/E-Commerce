from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
import time
from sqlalchemy.sql import case
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    send_file,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import pandas as pd
import os
import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from pytz import timezone
import uuid

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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Basic validation
        if not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        # Check if user exists
        user = UserDatabase.query.filter_by(email=email).first()
        if not user:
            flash("Email not registered.", "error")
            return redirect(url_for("login"))

        # Check if user is banned
        if user.is_banned:
            flash("Your account has been banned. Please contact support.", "error")
            return redirect(url_for("login"))

        # Verify password
        if not check_password_hash(user.password, password):
            flash("Incorrect password.", "error")
            return redirect(url_for("login"))

        # Log the user in
        login_user(user)
        # flash("Login successful!", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
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
    logout_user()
    # flash("You have been logged out.", "is-success")
    return redirect(url_for("home"))


@app.route("/", methods=["GET", "POST"])
def home():
    return render_template("home.html", user=current_user)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Account page to display and update user details."""
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

        new_product = Product(
            name=name,
            description=description,
            price=price,
            category=category,
            stock=stock,
            image=image_path,
            supplier_id=current_user.id,
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


@app.route("/seller_dashboard")
@login_required
def seller_dashboard():
    if not current_user.is_seller:
        flash("You don't have permission to access the seller dashboard.", "error")
        return redirect(url_for("home"))

    # Get seller's products
    products = Product.query.filter_by(supplier_id=current_user.id).all()

    # Get orders containing seller's products
    seller_product_ids = [p.id for p in products]
    orders = (
        Order.query.join(OrderItem)
        .filter(OrderItem.product_id.in_(seller_product_ids))
        .distinct()
        .all()
    )

    # Get pending orders
    pending_orders = [order for order in orders if order.status == "Pending"]

    # Get low stock products (less than 10 items)
    low_stock_products = [product for product in products if product.stock < 10]

    return render_template(
        "seller/dashboard.html",
        user=current_user,
        products=products,
        orders=orders,
        pending_orders=pending_orders,
    )


@app.route("/edit_product/<product_id>", methods=["POST"])
@login_required
def edit_product(product_id):
    if current_user.role != "seller":
        flash("Access denied", "error")
        return redirect(url_for("home"))

    product = Product.query.get_or_404(product_id)

    # Verify product belongs to current user
    if product.seller_id != current_user.id:
        flash("Access denied", "error")
        return redirect(url_for("seller_dashboard"))

    # Update product details
    product.name = request.form["name"]
    product.description = request.form["description"]
    product.category = request.form["category"]
    product.price = float(request.form["price"])
    product.stock = int(request.form["stock"])

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


# Run the application
if __name__ == "__main__":
    app.run(debug=True)
