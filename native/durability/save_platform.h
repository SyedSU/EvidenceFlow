#ifndef GENESIS_SAVE_PLATFORM_H
#define GENESIS_SAVE_PLATFORM_H
#ifdef _WIN32
#define GENESIS_EXPORT __declspec(dllexport)
#else
#define GENESIS_EXPORT __attribute__((visibility("default")))
#endif
/* 0 durable success; 1 failure before rename; 2 rename succeeded, sync uncertain. */
GENESIS_EXPORT int genesis_sync_file(const char *path);
GENESIS_EXPORT int genesis_replace_file(const char *source, const char *destination);
/* Nonblocking process-held transaction leases. Lock files are never deleted. */
GENESIS_EXPORT int genesis_lock_file(const char *path);
GENESIS_EXPORT int genesis_unlock_file(const char *path);
#endif
