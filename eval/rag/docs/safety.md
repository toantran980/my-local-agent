Agent safety limits

The agent may run at most ten tool steps per request. Files larger than 32 KB
are truncated on read and writes above 1 MB are rejected. Anything that looks
like a credential, such as dotenv files or private keys, is blocked, and secrets
are redacted before entries reach the audit log.
