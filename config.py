from envparse import env

env.read_envfile()

API_TOKEN = env.str('BOT_TOKEN')
CODEWARS_BASE_URL = 'https://www.codewars.com/api/v1/users'
POSTGRES_URI = env.str('DATABASE_URI')
WEBHOOK_URL = env.str('WEBHOOK_URL')
CODEWARS_BASE_KATA_URL = 'https://www.codewars.com/kata'

# webhook settings
WEBHOOK_HOST = env.str('WEBHOOK_HOST')
WEBHOOK_PATH = '/'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = 'localhost'  # or ip
WEBAPP_PORT = 3000

MIN_RATE = 1
MAX_RATE = 5

CREATOR_ID = env.str("CREATOR_ID")