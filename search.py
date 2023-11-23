from dotenv import load_dotenv
from utils.logger import logger
import os
from utils.mysqlLib import MySQL
from utils.leakix import search_all as leakix_search
from utils.dirsearch import search_all as dirsearch_all

load_dotenv()

db = MySQL(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT')),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

if __name__ == "__main__":
    logger.info("======= start leakix search ========")
    leakix_search(db)
    logger.info("======= end leakix search ========")
    logger.info("======= start dirsearch search ========")
    dirsearch_all(db)
    logger.info("======= end dirsearch search ========")