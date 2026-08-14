from fastapi import APIRouter

from apps.printer.controller import printer_router

api_router = APIRouter()

api_router.include_router(printer_router)