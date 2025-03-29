from flask import Blueprint, request, jsonify
from backend.models import *
from backend.models import Product
import uuid
import jwt
import datetime
from functools import wraps

main = Blueprint('main', __name__)


# token_required 装饰器, 用于验证 Token 并获取当前用户信息
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 修正：正确提取 Bearer Token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            token_parts = auth_header.split(' ')
            if len(token_parts) == 2 and token_parts[0] == 'Bearer':
                token = token_parts[1]

        if not token:
            return jsonify({"code": 0, "message": "Token is missing!"}), 401

        try:
            # 解码 Token（现在仅包含 JWT 字符串）
            data = jwt.decode(token, 'your_secret_key', algorithms=['HS256'])
            current_user = User.query.filter_by(userid=data['userid']).first()

            if current_user.role != 'seller':
                return jsonify({"code": 0, "message": "Seller role required!"}), 403

        except jwt.ExpiredSignatureError:
            return jsonify({"code": 0, "message": "Token expired!"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"code": 0, "message": f"Invalid token: {str(e)}"}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# 主界面
@main.route('/', methods=['GET'])
def index():
    return "Welcome to the XD_GO Home", 200


# 测试API
@main.route('/api/test', methods=['GET'])
def test():
    return "Welcome to the API Test", 200


# 测试从数据库读取数据的 API
@main.route('/api/users/get_users', methods=['GET'])
def get_users():
    try:
        # 查询所有用户
        users = User.query.all()

        # 将用户数据转换为字典列表
        user_list = []
        for user in users:
            user_data = {
                'userid': user.userid,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
            user_list.append(user_data)

        # 返回用户数据
        return {
                   'status': 'success',
                   'data': user_list
               }, 200

    except Exception as e:
        # 捕获异常并返回错误信息
        return {
                   'status': 'error',
                   'message': str(e)
               }, 500


# 卖家获取店铺商品列表API[GET]   /api/sell_order/getProduct
@main.route('/api/sell_order/getProduct', methods=['GET'])
@token_required
def get_product(current_user):
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('pageSize', 10))
        search = request.args.get('search')

        # 使用当前卖家的userid来过滤商品
        seller_id = current_user.userid

    except ValueError:
        return jsonify({"code": 400, "message": "参数格式错误"}), 400

    query = Product.query.filter_by(userid=seller_id)

    # 如果提供了搜索条件，则按商品名或描述进行模糊搜索
    if search:
        query = query.filter(
            Product.name.ilike(f'%{search}%') |
            Product.description.ilike(f'%{search}%')
        )

    total = query.count()

    # 获取分页数据
    products = query.order_by(Product.createtime.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    # 构建返回数据
    data = []
    for product in products:
        # 获取商品分类
        category = Category.query.filter_by(catid=product.catid).first()

        product_data = {
            "productId": product.proid,
            "productName": product.name,
            "description": product.description,
            "price": float(product.price),
            "stock": product.stock,
            "createTime": product.createtime.strftime('%Y-%m-%d %H:%M:%S'),
            "updateTime": product.updatetime.strftime('%Y-%m-%d %H:%M:%S'),
            "category": category.name if category else 'N/A',  # 获取商品分类名
            "imageUrl": product.image,  # 返回图床 URL
            "catid": product.catid,
            "sellerId": product.userid,  # 添加商店信息
        }
        data.append(product_data)

    response = {
        "code": 200,
        "message": "获取商品列表成功",
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "pageSize": page_size
        }
    }
    return jsonify(response), 200


# 用户注册接口API[POST]   /api/users/register
@main.route('/api/users/register', methods=['POST'])
def register_user():
    try:
        # 获取请求数据
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        phone = data.get('phone')
        role = data.get('role')

        # 验证输入参数
        if not username or not password or not email or not role:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Missing required fields"
            }), 400

        # 验证角色是否合法
        if role not in ['buyer', 'seller', 'admin']:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Role must be 'buyer', 'seller', or 'admin'"
            }), 400

        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Username already exists"
            }), 400

        # 创建新用户
        new_user = User(
            userid=str(uuid.uuid4()),  # 生成唯一的用户ID
            username=username,
            password=password,  # 注意：实际项目中密码应加密存储
            email=email,
            phone=phone,
            role=role
        )

        # 添加到数据库
        db.session.add(new_user)
        db.session.commit()

        # 返回注册成功信息
        return jsonify({
            "code": 200,
            "message": "User registered successfully",
            "data": {
                "userid": new_user.userid,
                "username": new_user.username,
                "role": new_user.role
            }
        }), 200

    except Exception as e:
        # 捕获异常并返回错误信息
        return jsonify({
            "code": 0,
            "message": str(e)
        }), 400


# 用户登录接口API[GET]   /api/users/login
@main.route('/api/users/login', methods=['GET'])
def login_user():
    try:
        # 获取查询参数
        username = request.args.get('username')
        password = request.args.get('password')

        # 验证输入参数
        if not username or not password:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Missing required fields"
            }), 400

        # 查询用户
        user = User.query.filter_by(username=username, password=password).first()
        if not user:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Incorrect username or password"
            }), 401

        # 生成 JWT Token
        token_payload = {
            'userid': user.userid,
            'username': user.username,
            'role': user.role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token 有效期为 1 小时
        }
        token = jwt.encode(token_payload, 'your_secret_key', algorithm='HS256')  # 使用密钥和算法生成 Token

        # 返回登录成功信息
        return jsonify({
            "code": 200,
            "message": "Login successful",
            "data": {
                "userid": user.userid,
                "username": user.username,
                "role": user.role,
                "token": token  # 返回生成的 Token
            }
        }), 200

    except Exception as e:
        # 捕获异常并返回错误信息
        return jsonify({
            "code": 0,
            "message": str(e)
        }), 400


# 买家首页获取所有商品的API[GET]   /api/product/productList
@main.route('/api/product/productList', methods=['GET'])
def get_all_products():
    try:
        # 查询所有商品
        products = Product.query.all()

        # 将商品数据转换为字典列表
        product_list = []
        for product in products:
            category = Category.query.filter_by(catid=product.catid).first()

            product_data = {
                'productId': product.proid,
                'productName': product.name,
                'price': float(product.price),
                'description': product.description,
                'stock': product.stock,
                'createTime': product.createtime.strftime('%Y-%m-%d %H:%M:%S'),
                'updateTime': product.updatetime.strftime('%Y-%m-%d %H:%M:%S'),
                'category': category.name if category else 'N/A',  # 获取商品分类名
                'imageUrl': product.image,  # 返回图床 URL
                'sellerId': product.userid  # 添加商店信息
            }
            product_list.append(product_data)

        # 返回商品数据
        return jsonify({
            'status': 200,
            'message': '获取商品列表成功',
            'data': {
                'list': product_list
            }
        }), 200

    except Exception as e:
        # 捕获异常并返回错误信息
        return jsonify({
            'status': 500,
            'message': str(e),
        }), 500


@main.route('/api/sell_order/updateProduct', methods=['POST'])
@token_required
def update_products(current_user):
    try:
        # 获取请求数据
        data = request.get_json()

        # 验证必要字段
        if not data or 'products' not in data:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Missing required fields"
            }), 400

        products = data.get('products', [])

        # 验证每个商品数据
        for product_data in products:
            if not all(k in product_data for k in ['proid', 'price', 'stock']):
                return jsonify({
                    "code": 0,
                    "message": "Invalid product data: Missing required fields (proid, price or stock)"
                }), 400

            # 检查价格和库存是否为有效值
            if product_data['price'] <= 0 or product_data['stock'] < 0:
                return jsonify({
                    "code": 0,
                    "message": f"Invalid product data: Price must be positive "
                               f"and stock must be non-negative (proid: {product_data['proid']}) "
                }), 400

        # 批量更新商品
        for product_data in products:
            product = Product.query.filter_by(
                proid=product_data['proid'],
                userid=current_user.userid  # 确保商品属于当前卖家
            ).first()

            if not product:
                return jsonify({
                    "code": 0,
                    "message": f"Product not found or not owned by you (proid: {product_data['proid']})"
                }), 404

            # 检查商品是否存在于未完成的订单中
            pending_order_items = OrderItem.query.join(Order).filter(
                OrderItem.proid == product_data['proid'],
                Order.status != 'delivered'  # 检查非已完成订单
            ).first()

            if pending_order_items:
                return jsonify({
                    "code": 0,
                    "message": f"Cannot update product: {product.name} (proid: {product_data['proid']}) "
                              f"because it exists in pending orders"
                }), 400

            # 记录旧价格用于更新购物车
            old_price = product.price

            # 更新商品信息
            if 'name' in product_data:
                product.name = product_data['name']
            if 'price' in product_data:
                product.price = product_data['price']
            if 'stock' in product_data:
                product.stock = product_data['stock']
            if 'description' in product_data:
                product.description = product_data['description']
            if 'catid' in product_data:
                # 验证分类是否存在
                category = Category.query.get(product_data['catid'])
                if not category:
                    return jsonify({
                        "code": 0,
                        "message": f"Category not found (catid: {product_data['catid']})"
                    }), 404
                product.catid = product_data['catid']

            # 如果价格有变化，更新购物车中的价格信息
            if 'price' in product_data and old_price != product_data['price']:
                # 更新所有包含该商品的购物车项的价格
                cart_items = CartItem.query.filter_by(proid=product_data['proid']).all()
                for item in cart_items:
                    # 这里可以根据业务需求决定是否更新购物车中的价格
                    # 或者只是记录价格变化，让用户确认
                    item.price = product_data['price']  # 假设直接更新价格

        # 提交数据库更改
        db.session.commit()

        return jsonify({
            "code": 200,
            "message": "Products updated successfully",
            "data": {
                "updated_count": len(products)
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 0,
            "message": str(e)
        }), 400

# 卖家增加自己的商品API[POST]   /api/sell_order/addProduct
@main.route('/api/sell_order/addProduct', methods=['POST'])
@token_required
def add_product(current_user):
    try:
        # 1. 获取并验证请求数据
        data = request.get_json()
        if not data:
            return jsonify({
                "code": 0,
                "message": "Invalid input: No JSON data provided"
            }), 400

        # 2. 验证必填字段
        required_fields = ['name', 'price', 'stock', 'catid']
        if not all(field in data for field in required_fields):
            return jsonify({
                "code": 0,
                "message": f"Missing required fields: {', '.join(required_fields)}"
            }), 400

        # 3. 验证数值有效性
        if data['price'] <= 0 or data['stock'] < 0:
            return jsonify({
                "code": 0,
                "message": "Price must be positive and stock must be non-negative"
            }), 400

        # 4. 验证分类是否存在
        category = Category.query.get(data['catid'])
        if not category:
            return jsonify({
                "code": 0,
                "message": f"Category not found: {data['catid']}"
            }), 404

        # 5. 检查商品名称是否重复（同一卖家的商品不允许重名）
        existing_product = Product.query.filter_by(
            name=data['name'],
            userid=current_user.userid  # 只检查当前卖家的商品
        ).first()

        if existing_product:
            return jsonify({
                "code": 0,
                "message": f"Product name '{data['name']}' already exists for your shop"
            }), 409  # HTTP 409 Conflict

        # 6. 创建新商品
        new_product = Product(
            proid=str(uuid.uuid4()),
            name=data['name'],
            price=data['price'],
            stock=data['stock'],
            description=data.get('description', ''),
            catid=data['catid'],
            userid=current_user.userid,
            image=data.get('image', '')
        )

        db.session.add(new_product)
        db.session.commit()

        # 7. 返回成功响应
        return jsonify({
            "code": 200,
            "message": "Product added successfully",
            "data": {
                "proid": new_product.proid,
                "name": new_product.name,
                "price": float(new_product.price)
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500


# 卖家删除自己的商品API[DELETE]   /api/sell_order/deleteProduct
@main.route('/api/sell_order/deleteProduct', methods=['DELETE'])
@token_required
def delete_product(current_user):
    try:
        # 1. 获取商品ID
        data = request.get_json()
        if not data or 'proid' not in data:
            return jsonify({
                "code": 0,
                "message": "Product ID (proid) is required"
            }), 400

        # 2. 检查商品是否存在
        product = Product.query.filter_by(proid=data['proid']).first()
        if not product:
            return jsonify({
                "code": 0,
                "message": f"Product not found with proid: {data['proid']}"
            }), 404

        # 3. 验证所有权
        if product.userid != current_user.userid:
            return jsonify({
                "code": 0,
                "message": f"No permission to delete product: {product.name} (proid: {data['proid']})"
            }), 403

        # 4. 检查商品是否存在于未完成的订单中
        pending_order_items = OrderItem.query.join(Order).filter(
            OrderItem.proid == data['proid'],
            Order.status != 'delivered'  # 检查非已完成订单
        ).first()

        if pending_order_items:
            return jsonify({
                "code": 0,
                "message": f"Cannot delete product: {product.name} (proid: {data['proid']}) because it exists in pending orders"
            }), 400

        # 5. 记录待删除的商品名称（提交前获取）
        deleted_product_name = product.name

        # 6. 删除相关数据（使用事务保证原子性）
        with db.session.begin_nested():
            # 删除购物车项
            CartItem.query.filter_by(proid=data['proid']).delete()

            # 删除已完成订单中的订单项（可选，根据业务需求）
            # OrderItem.query.filter_by(proid=data['proid']).delete()

            # 删除商品
            db.session.delete(product)

        db.session.commit()

        # 7. 返回成功响应
        return jsonify({
            "code": 200,
            "message": "Product and related items deleted successfully",
            "data": {
                "deleted_proid": data['proid'],
                "deleted_name": deleted_product_name
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(e)
        return jsonify({
            "code": 0,
            "message": f"Deletion failed: {str(e)}"
        }), 500


# 卖家获取商品详情API[GET]   /api/product/seller_detail
@main.route('/api/product/seller_detail', methods=['GET'])
def seller_product_detail():
    goods_id = request.args.get('goodsId')

    if not goods_id:
        return jsonify({"status": 1, "message": "商品ID不能为空", "data": {}})

    product = Product.query.filter_by(proid=goods_id).first()

    if not product:
        return jsonify({"status": 1, "message": "商品不存在", "data": {}})

    seller = User.query.filter_by(userid=product.userid).first()

    data = {
        "goods_id": product.proid,
        "goods_name": product.name,
        "price": str(product.price),
        "stock": product.stock,
        "description": product.description,
        "category_id": product.catid,
        "image": product.image,
        "seller_info": {
            "seller_id": seller.userid,
            "seller_name": seller.username,
            "contact": seller.phone
        },
        "createtime": product.createtime.strftime("%Y-%m-%d %H:%M:%S"),
        "updatetime": product.updatetime.strftime("%Y-%m-%d %H:%M:%S")
    }

    return jsonify({"status": 0, "message": "成功", "data": {"detail": data}})


# 买家/卖家获取用户个人信息API[GET]   /api/users/info
@main.route('/api/users/info', methods=['GET'])
@token_required
def get_user_info(current_user):
    try:
        # 根据用户角色返回不同的信息
        if current_user.role == 'buyer':
            user_info = {
                'userid': current_user.userid,
                'username': current_user.username,
                'email': current_user.email,
                'phone': current_user.phone,
                'role': current_user.role,
                'shipping_address': current_user.shipping_address
            }
        elif current_user.role == 'seller':
            user_info = {
                'userid': current_user.userid,
                'username': current_user.username,
                'email': current_user.email,
                'phone': current_user.phone,
                'role': current_user.role
            }
        else:
            return jsonify({
                "code": 0,
                "message": "Invalid user role"
            }), 400

        return jsonify({
            "code": 200,
            "message": "User info retrieved successfully",
            "data": user_info
        }), 200

    except Exception as e:
        return jsonify({
            "code": 0,
            "message": str(e)
        }), 500


# 买家修改用户个人地址API[PUT]   /api/users/address_edit
@main.route('/api/users/address_edit', methods=['PUT'])
@token_required
def update_shipping_address(current_user):
    try:
        # 验证用户角色
        if current_user.role != 'buyer':
            return jsonify({
                "code": 0,
                "message": "Access denied: Only buyers can update shipping address"
            }), 403

        # 获取请求数据
        data = request.get_json()
        if not data or 'shipping_address' not in data:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Missing required field 'shipping_address'"
            }), 400

        # 更新收货地址
        current_user.shipping_address = data['shipping_address']
        db.session.commit()

        return jsonify({
            "code": 200,
            "message": "Shipping address updated successfully",
            "data": {
                "userid": current_user.userid,
                "username": current_user.username,
                "new_shipping_address": current_user.shipping_address
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 0,
            "message": str(e)
        }), 500


# 买家获取某个商品的详细信息API[GET]   /api/product/detail
@main.route('/api/product/detail', methods=['GET'])
def get_product_detail():
    try:
        # 获取商品ID
        goods_id = request.args.get('goodsId')
        if not goods_id:
            return jsonify({
                "code": 0,
                "message": "Invalid input: Missing required field 'goodsId'"
            }), 400

        # 查询商品
        product = Product.query.filter_by(proid=goods_id).first()
        if not product:
            return jsonify({
                "code": 0,
                "message": f"Product not found with proid: {goods_id}"
            }), 404

        # 查询商品分类
        category = Category.query.filter_by(catid=product.catid).first()

        # 组装数据
        data = {
            "goods_id": product.proid,
            "goods_name": product.name,
            "price": str(product.price),  # 转换为字符串，前端显示时会自动转换回数字
            "stock": product.stock,
            "description": product.description,
            "category_id": product.catid,
            "category_name": category.catname,
            "image": product.image,
            "createtime": product.createtime.strftime("%Y-%m-%d %H:%M:%S"),
            "updatetime": product.updatetime.strftime("%Y-%m-%d %H:%M:%S")
        }

        return jsonify({
            "code": 200,
            "message": "Product detail retrieved successfully",
            "data": data
        }), 200

    except Exception as e:
        return jsonify({
            "code": 0,
            "message": str(e)
        }), 500  # 500 Internal Server Error


# 买家创建订单发送给卖家API[POST]   /api/buy_order/submit
@main.route('/api/buy_order/submit', methods=['POST'])
@token_required
def submit_order(current_user):
    try:
        # 确保用户是买家
        if current_user.role != 'buyer':
            return jsonify({
                "code": 403,
                "message": "Access denied: Only buyers can submit orders"
            }), 403

        # 获取购物车信息
        cart = Cart.query.filter_by(userid=current_user.userid).first()
        if not cart:
            return jsonify({
                "code": 400,
                "message": "Cart is empty"
            }), 400

        cart_items = CartItem.query.filter_by(carid=cart.carid).all()
        if not cart_items:
            return jsonify({
                "code": 400,
                "message": "No items in the cart"
            }), 400

        # 按卖家分组商品
        grouped_items = {}
        for item in cart_items:
            product = Product.query.filter_by(proid=item.proid).first()
            if not product:
                return jsonify({
                    "code": 404,
                    "message": f"Product not found: {item.proid}"
                }), 404

            if item.quantity > product.stock:
                return jsonify({
                    "code": 400,
                    "message": f"Insufficient stock for product: {product.name}"
                }), 400

            if product.userid not in grouped_items:
                grouped_items[product.userid] = []
            grouped_items[product.userid].append((item, product))

        # 开始数据库事务
        total_orders = []
        try:
            for seller_id, items in grouped_items.items():
                # 创建新订单
                order_id = str(uuid.uuid4())
                totalprice = 0
                order_items = []

                for item, product in items:
                    totalprice += product.price * item.quantity
                    order_items.append(OrderItem(
                        orderid=order_id,
                        proid=product.proid,
                        productname=product.name,
                        price=product.price,
                        quantity=item.quantity
                    ))
                    # 减少库存
                    product.stock -= item.quantity

                # 创建订单记录
                order = Order(
                    orderid=order_id,
                    userid=current_user.userid,
                    sellerid=seller_id,
                    status='pending',
                    totalprice=totalprice
                )
                db.session.add(order)
                db.session.add_all(order_items)
                total_orders.append({
                    "orderid": order_id,
                    "sellerid": seller_id,
                    "totalprice": totalprice
                })

            # 提交订单和库存更新
            db.session.commit()

            # 清空购物车
            CartItem.query.filter_by(carid=cart.carid).delete()
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 500,
                "message": f"Database error: {str(e)}"
            }), 500

        # 支付处理
        payment_results = []
        for order in total_orders:
            payment_status = initiate_payment(order["orderid"], order["totalprice"])
            if payment_status == "success":
                # 更新订单状态为已支付
                order_record = Order.query.filter_by(orderid=order["orderid"]).first()
                order_record.status = 'paid'
                db.session.commit()
                payment_results.append({
                    "orderid": order["orderid"],
                    "totalprice": str(order["totalprice"]),
                    "status": "paid"
                })
            else:
                payment_results.append({
                    "orderid": order["orderid"],
                    "totalprice": str(order["totalprice"]),
                    "status": "payment_failed"
                })

        return jsonify({
            "code": 200,
            "message": "Order submission complete",
            "data": payment_results
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 500,
            "message": f"Server error: {str(e)}"
        }), 500


# 支付接口模拟函数，仅供参考
def initiate_payment(order_id, totalprice):
    # This function would interact with a payment gateway like PayPal, Stripe, etc.
    # For now, we simulate a successful payment process
    # Here you would send a request to a payment gateway API, then return success/failure status

    # Example (mocked) payment status: returning success directly.
    return "success"


# 买家添加商品到购物车API[PUT]  /api/cart/add_product
@main.route('/api/cart/add_product', methods=['PUT'])
@token_required
def add_product_to_cart(current_user):
    try:
        # Ensure the user is a buyer
        if current_user.role != 'buyer':
            return jsonify({
                "code": 403,
                "message": "Access denied: Only buyers can add products to cart"
            }), 403

        # Get the product ID and quantity from the request
        data = request.get_json()
        if not data or 'proid' not in data or 'quantity' not in data:
            return jsonify({
                "code": 400,
                "message": "Invalid input: Missing required fields 'proid' and 'quantity'"
            }), 400

        # Check if the product exists
        product = Product.query.filter_by(proid=data['proid']).first()
        if not product:
            return jsonify({
                "code": 404,
                "message": f"Product not found with proid: {data['proid']}"
            }), 404

        # Check if the user already has the product in their cart
        cart_item = CartItem.query.filter_by(userid=current_user.userid, proid=data['proid']).first()
        if cart_item:
            # Update the quantity if the product is already in the cart
            cart_item.quantity += data['quantity']
            db.session.commit()
        else:
            # Add the product to the cart if it's not already there
            cart_item = CartItem(
                carid=str(uuid.uuid4()),
                userid=current_user.userid,
                proid=data['proid'],
                quantity=data['quantity']
            )
            db.session.add(cart_item)
            db.session.commit()

        return jsonify({
            "code": 200,
            "message": "Product added to cart successfully",
            "data": {
                "proid": data['proid'],
                "quantity": data['quantity']
            }
        }), 200  # OK

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 500,
            "message": f"Error: {str(e)}"
        }), 500  # Internal Server Error


# 买家获取购物车列表API[GET]   /api/cart/list
@main.route('/api/cart/list', methods=['GET'])
@token_required
def get_cart_list(current_user):
    try:
        # Ensure the user is a buyer
        if current_user.role != 'buyer':
            return jsonify({
                "code": 0,
                "message": "Access denied: Only buyers can view their cart"
            }), 403

        # Get the user's cart
        cart = Cart.query.filter_by(userid=current_user.userid).first()
        if not cart:
            return jsonify({
                "code": 0,
                "message": "Cart is empty"
            }), 400

        # Get the cart items
        cart_items = CartItem.query.filter_by(carid=cart.carid).all()
        if not cart_items:
            return jsonify({
                "code": 0,
                "message": "Cart is empty"
            }), 400

        # Get the product details for each item
        products = []
        for item in cart_items:
            product = Product.query.filter_by(proid=item.proid).first()
            if not product:
                return jsonify({
                    "code": 0,
                    "message": f"Product not found: {item.proid}"
                }), 404

            products.append({
                "proid": product.proid,
                "name": product.name,
                "price": str(product.price),
                "quantity": item.quantity,
                "image": product.image
            })

        # Return the cart list
        return jsonify({
            "code": 200,
            "message": "Cart list retrieved successfully",
            "data": {
                "products": products
            }
        }), 200  # OK

    except Exception as e:
        return jsonify({
            "code": 0,
            "message": f"Error: {str(e)}"
        }), 500  # Internal Server Error


# 买家获取订单列表与详情API[GET]    /api/buy_order/list
@main.route('/api/buy_order/list', methods=['GET'])
@token_required
def get_order_list(current_user):
    try:
        # Ensure the user is a buyer
        if current_user.role != 'buyer':
            return jsonify({
                "code": 403,
                "message": "Access denied: Only buyers can view their orders"
            }), 403

        # Get the user's orders
        orders = Order.query.filter_by(userid=current_user.userid).all()
        if not orders:
            return jsonify({
                "code": 404,
                "message": "No orders found"
            }), 404

        # Get the order details for each order
        order_list = []
        for order in orders:
            order_items = OrderItem.query.filter_by(orderid=order.orderid).all()
            order_items_data = []
            for item in order_items:
                product = Product.query.filter_by(proid=item.proid).first()
                if not product:
                    return jsonify({
                        "code": 0,
                        "message": f"Product not found: {item.proid}"
                    }), 404

                order_items_data.append({
                    "proid": product.proid,
                    "name": product.name,
                    "price": str(product.price),
                    "quantity": item.quantity,
                    "image": product.image
                })

            order_list.append({
                "orderid": order.orderid,
                "totalprice": str(order.totalprice),
                "status": order.status,
                "createtime": order.createtime.strftime("%Y-%m-%d %H:%M:%S"),
                "order_items": order_items_data
            })

        # Return the order list
        return jsonify({
            "code": 200,
            "message": "Order list retrieved successfully",
            "data": {
                "orders": order_list
            }
        }), 200  # OK

    except Exception as e:
        print(e)
        return jsonify({
            "code": 0,
            "message": f"Error: {str(e)}"
        }), 500  # Internal Server Error


# 卖家获取所有订单列表API[GET]   /api/sell_order/getList
@main.route('/api/sell_order/list', methods=['GET'])
@token_required
def get_sell_order_list(current_user):
    try:
        # Ensure the user is a seller
        if current_user.role != 'seller':
            return jsonify({
                "code": 403,
                "message": "Access denied: Only sellers can view their orders"
            }), 403

        # Get the seller's orders
        orders = Order.query.filter_by(sellerid=current_user.userid).all()
        print(orders)
        if not orders:
            return jsonify({
                "code": 404,
                "message": "No orders found"
            }), 404

        # Get the order details for each order
        order_list = []
        for order in orders:
            order_items = OrderItem.query.filter_by(orderid=order.orderid).all()
            order_items_data = []
            for item in order_items:
                product = Product.query.filter_by(proid=item.proid).first()
                if not product:
                    return jsonify({
                        "code": 404,
                        "message": f"Product not found: {item.proid}"
                    }), 404

                order_items_data.append({
                    "proid": product.proid,
                    "name": product.name,
                    "price": str(product.price),
                    "quantity": item.quantity,
                    "image": product.image
                })

            order_list.append({
                "orderid": order.orderid,
                "totalprice": str(order.totalprice),
                "status": order.status,
                "createtime": order.createtime.strftime("%Y-%m-%d %H:%M:%S"),
                "order_items": order_items_data
            })

        # Return the order list
        return jsonify({
            "code": 200,
            "message": "Order list retrieved successfully",
            "data": {
                "orders": order_list
            }
        }), 200  # OK

    except Exception as e:
        print(e)
        return jsonify({
            "code": 500,
            "message": f"Error: {str(e)}"
        }), 500  # Internal Server Error


# 卖家修改订单状态[PUT]   /api/sell_order/updateStatus
@main.route('/api/sell_order/updateStatus', methods=['PUT'])
@token_required
def update_order_status(current_user):
    try:
        # Ensure the user is a seller
        if current_user.role != 'seller':
            return jsonify({
                "code": 403,
                "message": "Access denied: Only sellers can update order status"
            }), 403

        # Get the order ID and status from the request
        data = request.get_json()
        if not data or 'orderid' not in data or 'status' not in data:
            return jsonify({
                "code": 400,
                "message": "Invalid input: Missing required fields 'orderid' and'status'"
            }), 400

        # Check if the order exists
        order = Order.query.filter_by(orderid=data['orderid']).first()
        if not order:
            return jsonify({
                "code": 0,
                "message": f"Order not found with orderid: {data['orderid']}"
            }), 404

        # Check if the status is valid
        if data['status'] not in ['pending', 'delivered', 'shipped']:
            return jsonify({
                "code": 0,
                "message": f"Invalid status: {data['status']}"
            }), 400

        # Update the order status
        order.status = data['status']
        db.session.commit()

        return jsonify({
            "code": 200,
            "message": "Order status updated successfully",
            "data": {
                "orderid": data['orderid'],
                "status": data['status']
            }
        }), 200  # OK

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 500,
            "message": f"Error: {str(e)}"
        }), 500  # Internal Server Error


# 卖家修改商品API[PUT]   /api/product/seller_modify_product
@main.route('/api/product/seller_modify_product', methods=['PUT'])
@token_required
def modify_product(current_user):
    try:
        # Ensure the user is a seller
        if current_user.role != 'seller':
            return jsonify({
                "code": 0,
                "message": "Access denied: Only sellers can modify products"
            }), 403

        # Get the product ID and data from the request
        data = request.get_json()
        if not data or 'proid' not in data:  # or any other required fields
            return jsonify({
                "code": 0,
                "message": "Invalid input: Missing required field 'proid'"
            }), 400

        # Check if the product exists
        product = Product.query.filter_by(proid=data['proid']).first()
        if not product:
            return jsonify({
                "code": 0,
                "message": f"Product not found with proid: {data['proid']}"
            }), 404

        # Update the product data
        product.name = data.get('name', product.name)
        product.price = data.get('price', product.price)
        product.description = data.get('description', product.description)
        product.image = data.get('image', product.image)
        product.stock = data.get('stock', product.stock)
        db.session.commit()

        return jsonify({
            "code": 200,
            "message": "Product modified successfully",
            "data": {
                "proid": data['proid']
            }
        }), 200  # OK

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "code": 0,
            "message": f"Error: {str(e)}"
        }), 500  # Internal Server Error


# 获取所有商品类别API[GET]   /api/product/category
@main.route('/api/product/category', methods=['GET'])
def get_all_categories():
    try:
        # 查询所有商品类别
        categories = Category.query.all()

        # 将商品类别数据转换为字典列表
        category_list = []
        for category in categories:
            category_data = {
                'categoryId': category.catid,
                'categoryName': category.name,
                'createTime': category.createtime.strftime('%Y-%m-%d %H:%M:%S'),
                'updateTime': category.updatetime.strftime('%Y-%m-%d %H:%M:%S')
            }
            category_list.append(category_data)

        # 返回商品类别数据
        return jsonify({
            'code': 200,
            'message': '获取商品类别列表成功',
            'data': {
                'categories': category_list
            }
        }), 200  # OK

    except Exception as e:
        # 捕获异常并返回错误信息
        return jsonify({
            'code': 500,
            'message': f"Error: {str(e)}"
        }), 500  # Internal Server Error
