from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess

def run_daily():
    subprocess.run(["python", "-m", "app.runner", "--group", "daily"])

if __name__ == "__main__":
    sched = BlockingScheduler(timezone="Europe/Madrid")
    sched.add_job(run_daily, "cron", hour=6)  # cada día a las 6:00
    sched.start()