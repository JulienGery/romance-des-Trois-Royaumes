#ifndef FR_STDIO_H
#define FR_STDIO_H
#include <stddef.h>
typedef struct FR_FILE FILE;
extern FILE *stderr;
int fprintf(FILE *, const char *, ...); int snprintf(char *, size_t, const char *, ...); int fflush(FILE *); FILE *fopen(const char *, const char *);
#endif
