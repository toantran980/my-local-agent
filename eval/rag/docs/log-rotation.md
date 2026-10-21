Log rotation

The cron logs under logs/ are compressed every Sunday and deleted after 30 days. The audit trail in .agent/audit is never rotated automatically. make clean-logs clears the cron logs by hand.
