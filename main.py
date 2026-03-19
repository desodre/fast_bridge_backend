from app.routes.device import router as device_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

app = FastAPI(title='Fast Bridge API', description='API para controle de dispositivos Android via ADB e uiautomator2', version='1.0.0')
app.include_router(device_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], # TODO: quando for pra produção, colocar somente a url do site
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
