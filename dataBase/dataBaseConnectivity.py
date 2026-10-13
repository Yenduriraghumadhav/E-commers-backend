from pymongo import MongoClient

client = MongoClient(
    "mongodb+srv://Ecommers_project:raghumadhav2002@cluster0.yl15mil.mongodb.net/EcommersWebSite"
)
db = client["EcommersWebSite"]

print("DB CONNECTED:", db.name)