import discord
from discord.ext import commands, tasks
import os
import asyncio
from pymongo import MongoClient
import datetime
import traceback
from dotenv import load_dotenv

# -------------------------
# Config
# -------------------------
load_dotenv()
MONGODB_CONNECTION_STRING = os.getenv('MONGODB_TOKEN')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'instagram_mxp')
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN') or os.getenv('DISCORD_TOKEN')

# -------------------------
# Global State & Locks
# -------------------------
is_saving = asyncio.Lock()

# -------------------------
# MongoDB Singleton & Direct Helpers
# -------------------------
mongo_client = None
db = None

def init_mongodb():
    global mongo_client, db
    if not MONGODB_CONNECTION_STRING:
        print("❌ MONGODB_TOKEN não encontrado!")
        return False
    try:
        mongo_client = MongoClient(MONGODB_CONNECTION_STRING, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')
        db = mongo_client[MONGODB_DB_NAME]
        print(f"✅ MongoDB conectado: {db.name}")
        return True
    except Exception as e:
        print(f"❌ Erro MongoDB: {e}")
        return False

# Persistent Stores
user_data = {}
economy_data = {}
follow_data = {}
brand_posts_data = {}
inventory_data = {}
missions_data = {}
reset_data = {}
celebrations_data = {}

def get_collection_data(coll_name):
    mapping = {
        "user_data": user_data,
        "economy_data": economy_data,
        "follow_data": follow_data,
        "brand_posts_data": brand_posts_data,
        "inventory_data": inventory_data,
        "missions_data": missions_data,
        "reset_data": reset_data,
        "celebrations_data": celebrations_data
    }
    return mapping.get(coll_name)

async def load_all_from_mongo():
    if db is None: return
    print("📥 Carregando todos os dados do MongoDB...")
    colls = ["user_data", "economy_data", "follow_data", "brand_posts_data", "inventory_data", "missions_data", "reset_data", "celebrations_data"]
    for cname in colls:
        target_dict = get_collection_data(cname)
        target_dict.clear() # Limpa memória antes de carregar
        coll = db[cname]
        count = 0
        for doc in coll.find({}):
            did = doc.pop("_id")
            doc.pop("updated_at", None)
            target_dict[str(did)] = doc
            count += 1
        print(f"   -> {cname}: {count} documentos")
    print("✅ Dados carregados.")

async def save_everything_to_mongo():
    if db is None: return
    async with is_saving:
        print("💾 Iniciando salvamento global no MongoDB...")
        from pymongo import ReplaceOne
        colls = ["user_data", "economy_data", "follow_data", "brand_posts_data", "inventory_data", "missions_data", "reset_data", "celebrations_data"]
        
        for cname in colls:
            source_dict = get_collection_data(cname)
            # Nota: Permitimos salvar dicionários vazios para refletir o "reset" se necessário, 
            # mas o bulk_write falha com lista vazia.
            
            ops = []
            for uid, data in source_dict.items():
                doc = data.copy() if isinstance(data, dict) else {"value": data}
                doc["updated_at"] = datetime.datetime.utcnow()
                ops.append(ReplaceOne({"_id": str(uid)}, doc, upsert=True))
            
            if ops:
                try:
                    await asyncio.to_thread(db[cname].bulk_write, ops, ordered=False)
                except Exception as e:
                    print(f"❌ Erro ao salvar {cname}: {e}")
            else:
                # Se a memória está vazia e queremos resetar o banco, poderíamos dar drop ou delete_many
                pass
        print("✅ Salvamento concluído.")

@tasks.loop(minutes=5.0)
async def auto_save_task():
    await save_everything_to_mongo()

async def schedule_save(collections=None):
    await save_everything_to_mongo()

async def enqueue_save(collections=None):
    await save_everything_to_mongo()

def mark_collection_dirty(name):
    pass

# -------------------------
# Bot Setup
# -------------------------
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='m!', intents=intents, help_command=None)
        
    async def setup_hook(self):
        if init_mongodb():
            await load_all_from_mongo()
            auto_save_task.start()
        
        # Injetar referências globais
        self.user_data = user_data
        self.economy_data = economy_data
        self.follow_data = follow_data
        self.brand_posts_data = brand_posts_data
        self.inventory_data = inventory_data
        self.missions_data = missions_data
        self.reset_data = reset_data
        self.celebrations_data = celebrations_data
        self.schedule_save = schedule_save
        self.enqueue_save = enqueue_save
        self.mark_collection_dirty = mark_collection_dirty
        self.save_everything_to_mongo = save_everything_to_mongo

        # Load Cogs
        loaded_cogs = set()
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    cog_name = f'cogs.{filename[:-3]}'
                    if cog_name in loaded_cogs:
                        continue
                    try:
                        await self.load_extension(cog_name)
                        loaded_cogs.add(cog_name)
                        print(f"✅ Cog carregada: {filename}")
                    except Exception as e:
                        print(f"❌ Erro ao carregar {filename}: {e}")

    async def on_ready(self):
        print(f"🚀 Bot online como {self.user}")

    async def on_command(self, ctx):
        pass

bot = MyBot()

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN não encontrado!")
    else:
        bot.run(DISCORD_TOKEN)
