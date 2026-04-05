from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGODB_TOKEN")

if not MONGO_URI:
    raise RuntimeError("Secret MONGODB_TOKEN não encontrada.")

client = MongoClient(MONGO_URI)

client.drop_database("instagram_mxp")

print("Banco instagram_mxp apagado com sucesso.")
