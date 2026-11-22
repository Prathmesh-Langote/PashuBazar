
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, request, send_from_directory, session
from functools import wraps
import os
import re
import uuid
import certifi
import cloudinary
import cloudinary.uploader


load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production"
)

frontend_url = os.getenv("FRONTEND_URL", "")

allowed_origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500"
]

if frontend_url:
    allowed_origins.append(frontend_url.rstrip("/"))

CORS(
    app,
    supports_credentials=True,
    origins=allowed_origins
)

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# MongoDB connection
mongo_uri = os.getenv("MONGO_URI")

client = None
db = None
users_collection = None
animals_collection = None

if not mongo_uri:
    raise RuntimeError("MONGO_URI environment variable is missing")

client = MongoClient(
    mongo_uri,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=10000
)

db = client["pashubazar"]
users_collection = db["users"]
animals_collection = db["animals"]

# Check admin authentication
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({
                "message": "Admin login required."
            }), 401

        return f(*args, **kwargs)

    return decorated_function


# Separate Admin Login API
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_username or not admin_password or not app.secret_key:
        return jsonify({
            "message": "Admin configuration is missing."
        }), 500

    if username != admin_username or password != admin_password:
        return jsonify({
            "message": "Invalid admin username or password."
        }), 401

    session.clear()
    session["is_admin"] = True

    return jsonify({
        "status": "success",
        "message": "Admin login successful."
    }), 200


# Check current admin session
@app.route("/api/admin/check", methods=["GET"])
@admin_required
def admin_check():
    return jsonify({
        "status": "success",
        "isAdmin": True
    }), 200


# Admin Logout API
@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()

    return jsonify({
        "status": "success",
        "message": "Admin logged out."
    }), 200


# Home route
@app.route("/")
def home():
    return jsonify({
        "message": "PashuBazar Backend is running successfully!"
    })


# Test API
@app.route("/api/test")
def test():
    return jsonify({
        "status": "success",
        "message": "PashuBazar API is working!"
    })


# Test MongoDB connection
@app.route("/api/test-db")
def test_db():
    if client is None:
        return jsonify({
            "status": "error",
            "message": "MONGO_URI is missing in the .env file."
        }), 500

    try:
        client.admin.command("ping")

        return jsonify({
            "status": "success",
            "message": "MongoDB connected successfully!"
        })

    except Exception:
        app.logger.exception("MongoDB connection failed")

        return jsonify({
            "status": "error",
            "message": "MongoDB connection failed."
        }), 500


# Register user
@app.route("/api/register", methods=["POST"])
def register():
    if users_collection is None:
        return jsonify({
            "message": "Database is not configured."
        }), 500

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "message": "Please provide registration details."
        }), 400

    name = str(data.get("name", "")).strip()
    mobile = str(data.get("mobile", "")).strip()
    password = str(data.get("password", ""))

    if not name or not mobile or not password:
        return jsonify({
            "message": "Name, mobile and password are required."
        }), 400

    if not re.fullmatch(r"[0-9]{10}", mobile):
        return jsonify({
            "message": "Enter a valid 10-digit mobile number."
        }), 400

    if len(password) < 8:
        return jsonify({
            "message": "Password must contain at least 8 characters."
        }), 400

    try:
        existing_user = users_collection.find_one({
            "mobile": mobile
        })

        if existing_user:
            return jsonify({
                "message": "This mobile number is already registered."
            }), 409

        user = {
            "name": name,
            "mobile": mobile,
            "password": generate_password_hash(password)
        }

        result = users_collection.insert_one(user)

        return jsonify({
            "status": "success",
            "message": "Registration successful!",
            "userId": str(result.inserted_id)
        }), 201

    except Exception:
        app.logger.exception("Registration failed")

        return jsonify({
            "message": "Registration failed. Please try again."
        }), 500


# Login user
@app.route("/api/login", methods=["POST"])
def login():
    if users_collection is None:
        return jsonify({
            "message": "Database is not configured."
        }), 500

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "message": "Please provide login details."
        }), 400

    mobile = str(data.get("mobile", "")).strip()
    password = str(data.get("password", ""))

    if not mobile or not password:
        return jsonify({
            "message": "Mobile number and password are required."
        }), 400

    try:
        user = users_collection.find_one({
            "mobile": mobile
        })

        if (
            user is None
            or not check_password_hash(
                user.get("password", ""),
                password
            )
        ):
            return jsonify({
                "message": "Invalid mobile number or password."
            }), 401

        return jsonify({
            "status": "success",
            "message": "Login successful!",
            "user": {
                "id": str(user["_id"]),
                "name": user["name"],
                "mobile": user["mobile"]
            }
        }), 200

    except Exception:
        app.logger.exception("Login failed")

        return jsonify({
            "message": "Login failed. Please try again."
        }), 500


# Get all animals from MongoDB
@app.route("/api/animals", methods=["GET"])
def get_animals():
    if animals_collection is None:
        return jsonify({
            "status": "error",
            "message": "Database is not configured."
        }), 500

    try:
        animals = []

        cursor = animals_collection.find({}).sort("_id", -1)

        for animal in cursor:
            seller_id = animal.get("sellerId")
            seller = None

            if seller_id and users_collection is not None:
                try:
                    seller = users_collection.find_one(
                        {"_id": ObjectId(seller_id)},
                        {"mobile": 1}
                    )
                except Exception:
                    seller = None

            animal["sellerMobile"] = (
                seller.get("mobile", "") if seller else ""
            )

            animal["_id"] = str(animal["_id"])
            animals.append(animal)

        return jsonify({
            "status": "success",
            "animals": animals
        }), 200

    except Exception:
        app.logger.exception("Fetching animals failed")

        return jsonify({
            "status": "error",
            "message": "Could not fetch animals."
        }), 500


# Get all animals for Admin Dashboard
@app.route("/api/admin/animals", methods=["GET"])
@admin_required
def admin_get_animals():
    if animals_collection is None:
        return jsonify({
            "status": "error",
            "message": "Database is not configured."
        }), 500

    try:
        animals = []

        cursor = animals_collection.find({}).sort("_id", -1)

        for animal in cursor:
            seller_id = animal.get("sellerId")
            seller = None

            if seller_id and users_collection is not None:
                try:
                    seller = users_collection.find_one(
                        {"_id": ObjectId(seller_id)},
                        {"mobile": 1, "name": 1}
                    )
                except Exception:
                    seller = None

            animal["sellerMobile"] = (
                seller.get("mobile", "") if seller else ""
            )
            animal["sellerName"] = (
                seller.get("name", "") if seller else ""
            )
            animal["_id"] = str(animal["_id"])
            animals.append(animal)

        return jsonify({
            "status": "success",
            "animals": animals
        }), 200

    except Exception:
        app.logger.exception("Admin fetching animals failed")
        return jsonify({
            "status": "error",
            "message": "Could not fetch animal listings."
        }), 500


# Delete animal listing - admin only
@app.route("/api/admin/animals/<animal_id>", methods=["DELETE"])
@admin_required
def admin_delete_animal(animal_id):
    if animals_collection is None:
        return jsonify({
            "status": "error",
            "message": "Database is not configured."
        }), 500

    if not ObjectId.is_valid(animal_id):
        return jsonify({
            "status": "error",
            "message": "Invalid animal ID."
        }), 400

    try:
        result = animals_collection.delete_one({
            "_id": ObjectId(animal_id)
        })

        if result.deleted_count == 0:
            return jsonify({
                "status": "error",
                "message": "Animal listing not found."
            }), 404

        return jsonify({
            "status": "success",
            "message": "Animal listing deleted successfully."
        }), 200

    except Exception:
        app.logger.exception("Admin deleting animal failed")
        return jsonify({
            "status": "error",
            "message": "Could not delete animal listing."
        }), 500

# Add animal listing
@app.route("/api/animals", methods=["POST"])
def add_animal():
    if animals_collection is None:
        return jsonify({
            "status": "error",
            "message": "Database is not configured."
        }), 500

    category = request.form.get("category", "").strip()
    breed = request.form.get("breed", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "").strip()
    health = request.form.get("health", "").strip()
    vaccination = request.form.get("vaccination", "").strip()
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()
    seller_id = request.form.get("sellerId", "").strip()

    try:
        price = float(request.form.get("price", ""))
    except (ValueError, TypeError):
        return jsonify({
            "status": "error",
            "message": "Please enter a valid price."
        }), 400

    if not category or not breed or not age or not location:
        return jsonify({
            "status": "error",
            "message": "Category, breed, age and location are required."
        }), 400

    if price <= 0:
        return jsonify({
            "status": "error",
            "message": "Price must be greater than zero."
        }), 400

    if not seller_id:
        return jsonify({
            "status": "error",
            "message": "Please login before listing an animal."
        }), 401

    try:
        seller = None

        if users_collection is not None:
            try:
                seller = users_collection.find_one({
                    "_id": ObjectId(seller_id)
                })
            except Exception:
                seller = None

        if not seller:
            return jsonify({
                "status": "error",
                "message": "Seller account not found. Please login again."
            }), 401

        # Save animal photo to Cloudinary
        photo = request.files.get("photo")
        photo_path = None

        if photo and photo.filename:
            allowed_extensions = {"jpg", "jpeg", "png", "webp"}

            original_name = secure_filename(photo.filename)

            if "." not in original_name:
                return jsonify({
                    "status": "error",
                    "message": "Upload a JPG, PNG or WEBP image."
                }), 400

            extension = original_name.rsplit(".", 1)[-1].lower()

            if extension not in allowed_extensions:
                return jsonify({
                    "status": "error",
                "message": "Upload a JPG, PNG or WEBP image."
                }), 400

            upload_result = cloudinary.uploader.upload(
                photo,
                folder="pashubazar/animals",
                resource_type="image"
            )

            photo_path = upload_result.get("secure_url")

        animal = {
            "category": category,
            "breed": breed,
            "age": age,
            "gender": gender,
            "health": health,
            "vaccination": vaccination,
            "location": location,
            "price": price,
            "description": description,
            "photo": photo_path,
            "sellerId": seller_id
        }

        result = animals_collection.insert_one(animal)

        return jsonify({
            "status": "success",
            "message": "Animal listed successfully!",
            "animalId": str(result.inserted_id)
        }), 201

    except Exception:
        app.logger.exception("Animal listing failed")

        return jsonify({
            "status": "error",
            "message": "Could not list the animal. Please try again."
        }), 500

# Edit animal listing - seller only
@app.route("/api/animals/<animal_id>", methods=["PUT"])
def edit_my_animal(animal_id):
    if animals_collection is None:
        return jsonify({"message": "Database is not configured."}), 500

    if not ObjectId.is_valid(animal_id):
        return jsonify({"message": "Invalid animal ID."}), 400

    seller_id = request.form.get("sellerId", "").strip()

    if not seller_id or not ObjectId.is_valid(seller_id):
        return jsonify({"message": "Please login again."}), 401

    animal = animals_collection.find_one({
        "_id": ObjectId(animal_id),
        "sellerId": seller_id
    })

    if not animal:
        return jsonify({
            "message": "Listing not found or you do not own it."
        }), 404

    fields = [
        "category", "breed", "age", "gender",
        "health", "vaccination", "location", "description"
    ]

    updates = {}

    for field in fields:
        value = request.form.get(field)
        if value is not None:
            updates[field] = value.strip()

    if "price" in request.form:
        try:
            price = float(request.form.get("price", ""))
            if price <= 0:
                raise ValueError
            updates["price"] = price
        except (ValueError, TypeError):
            return jsonify({"message": "Please enter a valid price."}), 400

    photo = request.files.get("photo")

    if photo and photo.filename:
        allowed_extensions = {"jpg", "jpeg", "png", "webp"}
        filename = secure_filename(photo.filename)

        if "." not in filename or filename.rsplit(".", 1)[-1].lower() not in allowed_extensions:
            return jsonify({
                "message": "Upload a JPG, PNG or WEBP image."
            }), 400

        upload_result = cloudinary.uploader.upload(
        photo,
        folder="pashubazar/animals",
        resource_type="image"
        )

        updates["photo"] = upload_result.get("secure_url")

    if updates:
        animals_collection.update_one(
            {"_id": ObjectId(animal_id), "sellerId": seller_id},
            {"$set": updates}
        )

    return jsonify({
        "status": "success",
        "message": "Listing updated successfully."
    }), 200


# Delete animal listing - seller only
@app.route("/api/animals/<animal_id>", methods=["DELETE"])
def delete_my_animal(animal_id):
    if animals_collection is None:
        return jsonify({"message": "Database is not configured."}), 500

    if not ObjectId.is_valid(animal_id):
        return jsonify({"message": "Invalid animal ID."}), 400

    data = request.get_json(silent=True) or {}
    seller_id = str(data.get("sellerId", "")).strip()

    if not seller_id or not ObjectId.is_valid(seller_id):
        return jsonify({"message": "Please login again."}), 401

    result = animals_collection.delete_one({
        "_id": ObjectId(animal_id),
        "sellerId": seller_id
    })

    if result.deleted_count == 0:
        return jsonify({
            "message": "Listing not found or you do not own it."
        }), 404

    return jsonify({
        "status": "success",
        "message": "Listing deleted successfully."
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
