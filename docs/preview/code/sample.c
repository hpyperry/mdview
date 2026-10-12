#include <stdio.h>
/* 中文注释：C 语言 */
#define MAX 128

int main(void) {
    int 计数 = 0;
    for (int i = 0; i < MAX; i++) {
        计数 += i;
    }
    printf("结果=%d\n", 计数);
    return 0;
}
