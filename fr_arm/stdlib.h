#ifndef FR_STDLIB_H
#define FR_STDLIB_H
#include <stddef.h>
char *getenv(const char *);       /* never linked: overrides.h turns it into a constant 0 */
#endif
