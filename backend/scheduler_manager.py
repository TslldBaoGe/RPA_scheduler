from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from storage import load_tasks
from task_executor import execute_task


class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
    
    def start(self):
        self.scheduler.start()
        self.reload_all_tasks()
    
    def shutdown(self):
        self.scheduler.shutdown()
    
    def reload_all_tasks(self):
        self.scheduler.remove_all_jobs()
        
        tasks = load_tasks()
        for task in tasks:
            try:
                self.add_task(task)
            except Exception as e:
                print(f"启动任务 {task['name']} 失败: {str(e)}")
    
    def add_task(self, task: dict):
        trigger = CronTrigger.from_crontab(task["cronExpression"].strip())
        self.scheduler.add_job(
            execute_task,
            trigger,
            args=[task],
            id=task["id"],
            replace_existing=True
        )
    
    def remove_task(self, task_id: str):
        self.scheduler.remove_job(task_id)
    
    def update_task(self, task: dict):
        self.add_task(task)


scheduler_manager = SchedulerManager()
