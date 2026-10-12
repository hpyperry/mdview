/* 中文注释：头文件 */
#ifndef SAMPLE_H
#define SAMPLE_H

struct 配置 {
    const char *名称;
    int 端口;
};

int 启动(const struct 配置 *cfg);

#endif
