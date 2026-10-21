Scheduling on Windows

Windows has no cron, so the nightly job runs inside WSL. Install it with make cron-install, and make sure the cron service is started in the WSL distribution or the job will silently never fire.
