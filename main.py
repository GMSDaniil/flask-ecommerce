from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, Boolean
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import math


stripe_keys = {
    "secret_key": "sk_test_51OyGgf06QP1tclJ1iovmDblZe9FBmEJxwSjGyI0Z8nSuaCU6fF6JM4JD6C2E5TzdwwSZw81pyJKU7TeaB5t2YWYB00EsNSnqYl",
    "publishable_key": "pk_test_51OyGgf06QP1tclJ1oRy23pRzi4VkCmBv51uzVKMVmJ0VgbGDd2p9lAP083EPswJkvdd8MvUqlXDSTviYtTYUhgj70009Y4u1th",
}

stripe.api_key = stripe_keys["secret_key"]

app = Flask(__name__)
app.config['SECRET_KEY'] = "adfsm54g5423glhk54glhlgh5423"

login_manager = LoginManager()
login_manager.init_app(app)

class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///shop-collection.db"
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    img_src: Mapped[str] = mapped_column(String(250), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    product_type: Mapped[str] = mapped_column(String(250)) #tshirt, hoodie
    discount: Mapped[int] = mapped_column(Integer, nullable=True)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))

class Wish(Base):
    __tablename__ = 'wishlist'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(Integer)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)



with app.app_context():
    db.create_all()



def get_cart():
    cart_quantity = 0
    cart = []
    cart_total = 0
    cart_total_discount = 0
    if 'cart' in session:
        print(session['cart'])
        
        for product in session['cart']:
            prdct = db.get_or_404(Product, int(list(product.keys())[0]))
            quantity = list(product.values())[0]
            cart_quantity += quantity
            if prdct.discount:
                cart_total_discount += math.floor(((prdct.price-prdct.price*prdct.discount/100) * 100))/100*quantity
            else:
                cart_total_discount += prdct.price*quantity
            cart_total += prdct.price*quantity
            cart.append((prdct, quantity))
    cart_total = round(cart_total, 2)
    # cart_total_discount = cart_total_discount, 2)
    return (cart_quantity, cart, cart_total, cart_total_discount)


@app.route('/')
def home():
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()
    
    products = list(db.session.execute(db.select(Product)).scalars())
    products = sorted(products, key=lambda d: d.available)[::-1]
    page = request.args.get('page', 1, type=int)
    per_page = 16
    start = (page - 1) * per_page
    end = start + per_page
    total_pages = (len(products) + per_page - 1) // per_page
    
    return render_template("index.html", products = products, start=start, end=end,
                           total_pages = total_pages, page = page, cart_quantity= cart_quantity, cart= cart, cart_total=cart_total, cart_total_discount=cart_total_discount)

@app.route('/add_to_cart_index/<id>', methods=["POST"])
def add_to_cart_index(id):
    product = db.get_or_404(Product, id)
    if not product.available:
        return redirect(url_for('home'))

    if 'cart' not in session:
        session['cart'] = []
    for d in session['cart']:
        if id in d:
            d[id] += 1
            session.modified = True
            return redirect(url_for('home'))
    session['cart'].append({id: 1})
    session.modified = True

    return redirect(url_for('home'))


@app.route('/remove_from_cart/<id>')
def remove_from_cart(id):
    for i, product in enumerate(session['cart']):
        print(list(product.keys())[0], id)
        if list(product.keys())[0] == id:
            del session['cart'][i]
            session.modified = True
            redirect(url_for('cart'))
    
    return redirect(url_for('cart'))

@app.route('/product/<id>')
def show_product(id):
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()

    product = db.get_or_404(Product, id)
    return render_template('product.html',  product = product,
                           cart_quantity= cart_quantity, cart= cart, cart_total=cart_total, cart_total_discount=cart_total_discount)

@app.route('/add_to_cart_product/<id>', methods=["POST"])
def add_to_cart_product(id):
    product = db.get_or_404(Product, id)
    if not product.available:
        return redirect(url_for('show_product', id = id))

    if 'cart' not in session:
        session['cart'] = []
    for d in session['cart']:
        if id in d:
            d[id] += int(request.form['quantity'])
            session.modified = True
            return redirect(url_for('show_product', id = id))
    session['cart'].append({id: int(request.form['quantity'])})
    session.modified = True

    return redirect(url_for('show_product', id = id))


@app.route('/change_quantity/<id>?change=<change>')
def change_quantity(id, change):
    if 'cart' not in session:
        session['cart'] = []
        return redirect(url_for('home'))
    for d in session['cart']:
        if id in d:
            d[id] += int(change)
            if d[id] == 0:
                return redirect(url_for('remove_from_cart', id = id))
            session.modified = True
            return redirect(url_for('cart'))
    return redirect(url_for('cart'))



@app.route('/login', methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()
    if request.method == "POST":
        user = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar()
        if not user:
            flash("Invalid E-Mail.")
            return redirect(url_for('login'))
        
        if check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash("Invalid Password.")
            return redirect(url_for('login'))
    return render_template('login.html', 
                           cart_quantity= cart_quantity, cart= cart, cart_total=cart_total, cart_total_discount=cart_total_discount)


@app.route('/register', methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()
    if request.method == "POST":
        user_exists = db.session.execute(db.select(User).where(User.email == request.form["email"])).scalar()
        if user_exists:
            flash("You've already signed up with that email")
            return redirect(url_for('login'))
        new_user = User(name = request.form["name"],
                        email = request.form["email"],
                        password = generate_password_hash(request.form['password'], method="pbkdf2:sha256", salt_length=10))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('home'))
    return render_template('register.html', 
                           cart_quantity= cart_quantity, cart= cart, cart_total=cart_total, cart_total_discount=cart_total_discount)

@app.route('/profile')
@login_required
def profile():
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()
    user = db.get_or_404(User, current_user.get_id())
    user_wishes = list(db.session.execute(db.select(Wish).where(Wish.user_id == user.id)).scalars())
    wishes = []
    for wish in user_wishes:
        
        wishes.append(db.get_or_404(Product, wish.product_id))
    return render_template('profile.html', user = user, wishes = wishes,
                           cart_quantity= cart_quantity, cart= cart, cart_total=cart_total, cart_total_discount=cart_total_discount)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/add_to_wishlist/<id>')
@login_required
def add_to_wishlist(id):
    user_id = current_user.get_id()
    wishes = list(db.session.execute(db.select(Wish).where(Wish.user_id == user_id)).scalars())
    wish_exists = False
    for wish in wishes:
        if wish.product_id == int(id):
            wish_exists = True
            break

    if wish_exists:
        print("wish exists")
        return redirect(url_for('home'))
    new_wish = Wish(user_id = user_id,
                    product_id = id)
    print('added wish')
    db.session.add(new_wish)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/remove_wish/<id>')
@login_required
def remove_wish(id):
    user_id = current_user.get_id()
    wishes = list(db.session.execute(db.select(Wish).where(Wish.user_id == user_id)).scalars())
    for wish in wishes:
        if wish.product_id == int(id):
            db.session.delete(wish)
            db.session.commit()
            break
    return redirect(url_for('profile'))

@app.route('/cart')
def cart():
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()
    return render_template('cart.html',
                        cart_quantity= cart_quantity, cart= cart, cart_total=cart_total, cart_total_discount=cart_total_discount)


@app.route('/order')
def order():
    cart_quantity, cart, cart_total, cart_total_discount = get_cart()
    line_items=[]
    for product, quantity in cart:
        if product.discount:
            price = int(product.price*100 - product.discount*product.price)
        else:
            price = int(product.price*100)

        line_items.append({
            'price_data': {
                    'product_data': {
                        'name': product.name,
                    },
                    'unit_amount': price,
                    'currency': 'eur',
                },
                'quantity': quantity,
        })
    checkout_session = stripe.checkout.Session.create(
        line_items=line_items,
        payment_method_types=['card'],
        mode='payment',
        success_url=request.host_url + 'order/success',
        cancel_url=request.host_url + 'order/cancel',
    )
    return redirect(checkout_session.url)


if __name__ == "__main__":
    app.run(debug=True, port=32004)