// 中文注释：TypeScript（注意 .ts 不能被当成视频）
interface 文档 {
  id: number;
  title: string;
}

const 加载 = async (path: string): Promise<文档> => {
  return { id: 1, title: `中文标题 ${path}` };
};
