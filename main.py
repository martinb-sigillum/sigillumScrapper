import sys
import asyncio
from fastapi import FastAPI, HTTPException
from app.playwright_scrapper.scrapper import run
import platform

print("Running on:", platform.system())

# CRÍTICO: Configurar la política de event loop ANTES de crear la app FastAPI
if sys.platform == "win32":
    # Usar la política ProactorEventLoop en lugar de SelectorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()

@app.get("/scrapper")
async def scrapper(cas_code: str):
    try:
        result = await run(cas_code)
        if result is None:
            return {"status": "completed", "cas_code": cas_code, "message": "Scraping ejecutado"}
        return result
    except Exception as e:
        print(f"Error en endpoint scrapper: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error durante el scraping: {str(e)}")

@app.get("/")
async def root():
    return {"message": "SigillumScraper API"}

# Para desarrollo local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)  # reload=False importante