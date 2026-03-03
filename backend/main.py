from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from storage import init_storage
from scheduler_manager import scheduler_manager
from api_routes import router


app = FastAPI(
    title="定时任务调度系统 API",
    description="用于管理和执行定时任务的后端 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("shutdown")
def shutdown_event():
    scheduler_manager.shutdown()


if __name__ == "__main__":
    import uvicorn
    import logging
    
    init_storage()
    scheduler_manager.start()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cron_scheduler.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_config=None,
        access_log=False
    )
