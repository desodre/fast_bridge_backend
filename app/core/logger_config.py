import  sys
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="5 MB",
    retention="7 days",
    compression="zip",
    level="INFO",
)
log = logger