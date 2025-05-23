from functools import wraps
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask import jsonify
from models import Admin  # Ensure correct import

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        admin = Admin.query.get(current_user_id)

        if not admin:
            return jsonify({"msg": "Admin privileges required."}, 403)

        return fn(*args, **kwargs)

    return wrapper

def superadmin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        admin = Admin.query.get(current_user_id)

        if not admin or not admin.is_superadmin:  # Ensure is_superadmin exists in the model
            return jsonify({"msg": "Superadmin privileges required."}, 403)

        return fn(*args, **kwargs)

    return wrapper

def admin_or_superadmin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user_id = get_jwt_identity()
        admin = Admin.query.get(current_user_id)
        if not admin:
            return jsonify({"msg": "Admin or superadmin privileges required."}), 403
        return fn(*args, **kwargs)
    return wrapper
