// 中文注释：JSX
export default function 按钮({ 文本 }) {
  return <button onClick={() => alert("中文")}>{文本}</button>;
}
