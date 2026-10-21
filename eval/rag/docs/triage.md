Nightly triage

Every day at 17:00 a cron job runs the triage script. It reads the audit log and
recent git activity, asks the model for a summary of anything that needs
attention, and writes the result to a dated markdown report. CRON_HOUR and
CRON_MIN change the schedule.
